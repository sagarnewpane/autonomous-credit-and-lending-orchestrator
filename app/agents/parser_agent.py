"""
Unified Document Parsing Agent
==============================
Handles all document types from the GIBL Hackathon dataset:
- Citizenship Certificate
- Lalpurja (Land Deed) - uses PaddleOCR for tables
- KYC Form - uses PaddleOCR for complex layout
- Utility Bill
- Remittance Receipt
- Cooperative Passbook (dummy - to be implemented)

Input Format:
{
    "doc_type": "path/to/document.jpg",
    "doc_type2": "path/to/document2.jpg",
    ...
}

Supported doc_types: citizenship, lalpurja, kyc_form,
                     utility_bill, remittance_receipt, cooperative_passbook
"""

import pytesseract
import cv2
import json
import numpy as np
import re
import os
import shutil
from pathlib import Path
from PIL import Image
from groq import Groq
from dataclasses import dataclass
from typing import Optional, Dict, List, Any, Tuple, Callable
from dotenv import load_dotenv
from app.models.state import AgentState

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

def _find_tesseract() -> str:
    found = shutil.which("tesseract")
    if found:
        return found
    for p in ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"]:
        if Path(p).exists():
            return p
    raise RuntimeError("tesseract not found. Install with: brew install tesseract")

pytesseract.pytesseract.tesseract_cmd = _find_tesseract()

# Document types that use PaddleOCR (complex docs with tables)
PADDLEOCR_DOC_TYPES = {"lalpurja", "kyc_form"}

# Document types that use Tesseract
TESSERACT_DOC_TYPES = {"citizenship_certificate", "utility_bill", "remittance_receipt"}

# Dummy types (to be implemented later)
DUMMY_DOC_TYPES = {"cooperative_passbook"}

# Debug output directory
DEBUG_DIR = Path("/Users/sagarnewpane/autonomous-credit-and-lending-orchestrator/ocr_output/debug")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def parse_amount(amount_str):
    if amount_str in (None, ""):
        return None
    cleaned = str(amount_str)
    cleaned = cleaned.replace("रू.", "").replace("Rs.", "").replace("रु", "")
    cleaned = cleaned.replace(":", ".")
    cleaned = cleaned.replace(",", "")
    cleaned = cleaned.strip()
    try:
        return float(cleaned)
    except Exception:
        return None


def optimize_image_for_ocr(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return thresh


def resize_if_large(img: np.ndarray, max_side: int = 2000) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= max_side:
        return img
    scale = max_side / max(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def clean_json_response(raw: str) -> dict:
    raw = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start: end + 1]
    return json.loads(raw.strip())


def devanagari_to_english_digits(text: str) -> str:
    if not text:
        return text
    mapping = {
        '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
        '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'
    }
    result = text
    for np_digit, en_digit in mapping.items():
        result = result.replace(np_digit, en_digit)
    return result


def save_debug_image(img: np.ndarray, doc_type: str, suffix: str = "preprocessed"):
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{doc_type}_{suffix}.jpg"
        cv2.imwrite(str(DEBUG_DIR / filename), img)
    except Exception:
        pass


def call_llm(prompt: str) -> str:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content.strip()


# ============================================================================
# OCR ENGINES
# ============================================================================

def _is_front_back_image(img: np.ndarray) -> bool:
    """Detect if image contains front+back of citizenship (portrait with ~2:1 height:width ratio)."""
    h, w = img.shape[:2]
    if h < 1500:
        return False
    aspect = h / w
    return aspect > 1.4


def _split_front_back(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Split a front+back citizenship image into two halves."""
    h, w = img.shape[:2]
    mid = h // 2
    return img[:mid, :], img[mid:, :]


def _ocr_half(img: np.ndarray, lang: str = 'nep+eng') -> str:
    """Run OCR on a single half with enhanced preprocessing for Nepali text."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Upscale for better OCR on small text
    scale = 2
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Adaptive threshold for uneven lighting
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 31, 10)

    # Denoise
    denoised = cv2.fastNlMeansDenoising(binary, h=15)

    # Try multiple PSM modes and combine results
    texts = []
    for psm in [6, 4, 3]:
        config = f'--oem 3 --psm {psm}'
        text = pytesseract.image_to_string(denoised, lang=lang, config=config)
        if text.strip():
            texts.append(text.strip())

    # Also try on original gray with different config
    for psm in [6, 3]:
        config = f'--oem 3 --psm {psm}'
        text = pytesseract.image_to_string(gray, lang=lang, config=config)
        if text.strip():
            texts.append(text.strip())

    # Return longest result
    if texts:
        return max(texts, key=len)
    return ""


def run_tesseract_ocr(image_path: str, lang: str = 'nep+eng') -> Tuple[str, bool, float]:
    """Run Tesseract OCR. Returns (text, was_rotated, rotation_angle)."""
    img = cv2.imread(image_path)
    if img is None:
        return "", False, 0.0

    was_rotated = False
    rotation_angle = 0.0

    try:
        osd = pytesseract.image_to_osd(img)
        detected_angle = int(re.search(r'(?<=Rotate: )\d+', osd).group(0))
        if detected_angle != 0:
            was_rotated = True
            rotation_angle = float(detected_angle)
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, -rotation_angle, 1.0)
            img = cv2.warpAffine(img, M, (w, h))
    except Exception:
        pass

    # Check if image is front+back combined (portrait citizenship)
    if _is_front_back_image(img):
        front, back = _split_front_back(img)
        save_debug_image(front, Path(image_path).stem, "front")
        save_debug_image(back, Path(image_path).stem, "back")

        text_front = _ocr_half(front, lang)
        text_back = _ocr_half(back, lang)

        combined = f"=== FRONT ===\n{text_front}\n\n=== BACK ===\n{text_back}"
        return combined.strip(), was_rotated, rotation_angle

    # Standard single-page OCR
    processed_img = optimize_image_for_ocr(img)
    save_debug_image(processed_img, Path(image_path).stem, "tesseract_preprocessed")

    custom_config = r'--oem 3 --psm 3'
    text = pytesseract.image_to_string(processed_img, lang=lang, config=custom_config)
    return text.strip(), was_rotated, rotation_angle


def create_paddlevl_pipeline():
    """Create PaddleOCR-VL pipeline with mlx-vlm-server backend."""
    try:
        from paddleocr import PaddleOCRVL
        return PaddleOCRVL(
            vl_rec_backend="mlx-vlm-server",
            vl_rec_server_url="http://localhost:8111/",
            vl_rec_api_model_name="PaddlePaddle/PaddleOCR-VL-1.6",
            use_doc_orientation_classify=True,
        )
    except ImportError:
        print("[warn] PaddleOCR-VL not installed")
        return None
    except Exception as e:
        print(f"[warn] PaddleOCR-VL init failed: {e}")
        return None


_paddlevl_pipeline = None

def get_paddlevl_pipeline():
    global _paddlevl_pipeline
    if _paddlevl_pipeline is None:
        _paddlevl_pipeline = create_paddlevl_pipeline()
    return _paddlevl_pipeline


def run_paddleocr_ocr(image_path: str) -> Tuple[str, bool, float]:
    """Run PaddleOCR-VL for complex docs. Returns (text, was_rotated, rotation_angle)."""
    # Try PaddleOCR-VL first
    pipeline = get_paddlevl_pipeline()
    if pipeline is not None:
        try:
            result = pipeline.predict(input=image_path)
            all_text = []
            was_rotated = False
            rotation_angle = 0.0
            
            for res in result:
                if hasattr(res, 'rec_texts') and res.rec_texts:
                    all_text.extend(res.rec_texts)
                elif hasattr(res, 'text_blocks') and res.text_blocks:
                    for block in res.text_blocks:
                        if hasattr(block, 'text'):
                            all_text.append(block.text)
                # Check if VL corrected rotation
                if hasattr(res, 'doc_preprocessor_res') and res.doc_preprocessor_res:
                    if hasattr(res.doc_preprocessor_res, 'rotation') and res.doc_preprocessor_res.rotation:
                        was_rotated = True
                        rotation_angle = res.doc_preprocessor_res.rotation
            
            if all_text:
                return "\n".join(all_text), was_rotated, rotation_angle
        except Exception as e:
            print(f"[warn] PaddleOCR-VL failed: {e}")

    # Fallback to basic PaddleOCR
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        print("[warn] PaddleOCR not installed - falling back to Tesseract")
        text, rotated, angle = run_tesseract_ocr(image_path)
        return text, rotated, angle

    try:
        ocr = PaddleOCR(
            use_doc_orientation_classify=True,
            use_doc_unwarping=False,
            use_textline_orientation=True,
            lang="hi",
        )

        img = cv2.imread(image_path)
        was_rotated = False
        rotation_angle = 0.0
        
        if img is not None:
            img = resize_if_large(img)
            temp_path = str(DEBUG_DIR / "paddleocr_temp.jpg")
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(temp_path, img)
            result = ocr.predict(input=temp_path)
        else:
            result = ocr.predict(input=image_path)

        all_text = []
        for res in result:
            if isinstance(res, dict):
                if 'rec_texts' in res and res['rec_texts']:
                    all_text.extend(res['rec_texts'])
                # Check rotation from dict result
                if 'doc_preprocessor_res' in res and res['doc_preprocessor_res']:
                    if 'rotation' in res['doc_preprocessor_res'] and res['doc_preprocessor_res']['rotation']:
                        was_rotated = True
                        rotation_angle = res['doc_preprocessor_res']['rotation']
            elif hasattr(res, 'rec_texts') and res.rec_texts:
                all_text.extend(res.rec_texts)
            elif hasattr(res, 'text_blocks') and res.text_blocks:
                for block in res.text_blocks:
                    if hasattr(block, 'text'):
                        all_text.append(block.text)

        return "\n".join(all_text), was_rotated, rotation_angle

    except Exception as e:
        print(f"[warn] PaddleOCR failed: {e} - falling back to Tesseract")
        text, rotated, angle = run_tesseract_ocr(image_path)
        return text, rotated, angle


def run_ppstructure_ocr(image_path: str) -> Tuple[str, str]:
    """Run PPStructure for table-heavy docs. Returns (text, table_html)."""
    try:
        from paddleocr import PPStructureV3
    except ImportError:
        return run_paddleocr_ocr(image_path), ""

    try:
        pipeline = PPStructureV3(
            use_region_detection=True,
            use_table_recognition=True,
            use_chart_recognition=False,
            use_formula_recognition=False,
            ocr_version="PP-OCRv3",
            lang="hi"
        )

        output = pipeline.predict(input=image_path)

        all_text = []
        tables = []
        for res in output:
            if hasattr(res, 'save_to_markdown'):
                md_content = res.save_to_markdown(save_path=str(DEBUG_DIR))
                all_text.append(str(md_content))
            if hasattr(res, 'table'):
                tables.append(str(res.table))

        return "\n".join(all_text), "\n".join(tables)

    except Exception as e:
        print(f"[warn] PPStructure failed: {e}")
        return run_paddleocr_ocr(image_path), ""


def get_ocr_for_doc_type(doc_type: str) -> Tuple[Callable, str]:
    if doc_type in PADDLEOCR_DOC_TYPES:
        return run_paddleocr_ocr, "paddleocr"
    else:
        return run_tesseract_ocr, "tesseract"


# ============================================================================
# DOCUMENT TYPE DETECTION
# ============================================================================

def detect_document_type(raw_text: str) -> str:
    text_lower = raw_text.lower()

    citizenship_keywords = ['नागरिकता', 'citizenship', 'जन्म मिति', 'नागरिकता प्रमाणपत्र']
    lalpurja_keywords = ['जग्गाधनी', 'लालपुर्जा', 'कित्ता', 'जग्गा', 'जमिन', 'land owner',
                         'मालपोत', 'स्वामीको नाम', 'ब्यहोरा', 'rajshima']
    kyc_keywords = ['kyc', 'know your customer', 'ग्राहक पहिचान', 'global ime']
    utility_keywords = ['electricity', 'नेपाल विद्युत', 'nea', 'ncell', 'utility bill']
    remittance_keywords = ['western union', 'ime money', 'prabhu money', 'himal remit', 'remittance']
    cooperative_keywords = ['cooperative', 'सहकारी', 'passbook', 'सदस्यता']

    scores = {
        "citizenship_certificate": sum(1 for k in citizenship_keywords if k in text_lower),
        "lalpurja": sum(1 for k in lalpurja_keywords if k in text_lower),
        "kyc_form": sum(1 for k in kyc_keywords if k in text_lower),
        "utility_bill": sum(1 for k in utility_keywords if k in text_lower),
        "remittance_receipt": sum(1 for k in remittance_keywords if k in text_lower),
        "cooperative_passbook": sum(1 for k in cooperative_keywords if k in text_lower),
    }

    detected = max(scores, key=scores.get)
    return detected if scores[detected] > 0 else "unknown"


# ============================================================================
# LLM-BASED FIELD EXTRACTION PROMPTS
# ============================================================================

CITIZENSHIP_PROMPT = """You are parsing a Nepali Citizenship Certificate.

OCR extracted this text (mix of Nepali and English field labels):

---OCR TEXT---
{text}
---END---

The field labels in Nepali mean:
- "ना-प्र.नं." or "Citizenship No" = citizenship number (format: XX-XX-XX-XXXXX)
- "नाम थर" or "Name" = full name
- "जन्म मिति" or "Date of Birth" = date of birth
- "जन्म स्थान" or "Birth Place" = birth place
- "बाबुको नाम थर" or "Father" = father's name
- "बाजेको नाम थर" or "Grandfather" = grandfather's name
- "जिल्ला" or "District" = district name
- "स्थायी बासस्थान" or "Permanent Address" = permanent address

Extract these fields and return ONLY valid JSON:
{{
  "full_name": "person's full name",
  "citizenship_number_np": "original devanagari number",
  "citizenship_number": "number with dashes like 37-02-75-05633 (MUST be English digits)",
  "date_of_birth_np": "original devanagari date",
  "date_of_birth": "date in any format found (MUST be English digits)",
  "issued_district": "district name",
  "father_name": "father's name",
  "grandfather_name": "grandfather's name",
  "issued_date_np": "original devanagari date",
  "issued_date": "date (MUST be English digits) if found, else null"
}}

Rules:
- Always include the original Nepali/Devanagari values in the _np fields.
- Convert Nepali numbers to English digits for the main fields (०=0, १=1, २=2, ३=3, ४=4, ५=5, ६=6, ७=7, ८=8, ९=9).
- If field not found, use null
- Return ONLY the JSON object, no extra text"""


LALPURJA_PROMPT = """You are parsing a Nepali Land Revenue Office document (मालपोत कार्यालय / Lalpurja).

OCR extracted this text (table format may be jumbled):

---OCR TEXT---
{text}
---END---

CRITICAL FIELDS FOR LOAN SCORING:
1. स्वामीको नाम / Owner's Name = person who owns the land
2. नागरिकता नं. / Citizenship No = owner's ID (format: XX-XX-XX-XXXXX)
3. बाबु/पतिको नाम / Father or Husband's Name
4. जारी मिति / Issue Date = when document was issued
5. जारी गर्ने कार्यालय / Issuing Office = which office issued this

LAND DETAILS (look in table section):
6. कित्ता नं. / Plot Number = usually format like "123-क" or just "123"
7. क्षेत्रफल / Land Area = number like "324.96" (area in sq meters or ropani/aana)
8. ब्यहोरा / Transaction Type = e.g., "करोबार ब्यहोरा राजिनामा"

LOCATION:
9. जिल्ला / District = from address section
10. वडा नं. / Ward Number = ward number

Return ONLY valid JSON:
{{
  "owner_name": "owner's full name",
  "citizenship_number_np": "original devanagari number",
  "citizenship_number": "XX-XX-XX-XXXXX (MUST be English digits)",
  "father_or_husband_name": "father or husband name",
  "issued_date_np": "original devanagari date",
  "issued_date": "date (MUST be English digits)",
  "issuing_office": "office name",
  "plot_number_np": "original devanagari plot number",
  "plot_number": "plot number like 123 or 123-A (MUST be English digits)",
  "land_area": "area number like 324.96",
  "transaction_type": "transaction description",
  "location_district": "district name",
  "ward_number_np": "original devanagari ward number",
  "ward_number": "ward number (MUST be English digits)"
}}

Rules:
- Always include the original Nepali/Devanagari values in the _np fields.
- Convert Nepali numbers to English digits for the main fields (०=0, १=1, २=2, ३=3, ४=4, ५=5, ६=6, ७=7, ८=8, ९=9).
- Look for area numbers near "क्षेत्रफल" or in table right side
- If field not found, use null
- Return ONLY JSON, no extra text"""


KYC_FORM_PROMPT = """You are parsing a Nepali KYC (Know Your Customer) Form.

OCR extracted this text (mix of Nepali and English):

---OCR TEXT---
{text}
---END---

EXTRACT AS JSON:
{{
  "customer_id": "string",
  "account_number": "string",
  "full_name_np": "Nepali name",
  "full_name_en": "English name",
  "marital_status": "Married/Unmarried",
  "gender": "Male/Female",
  "purpose_of_account": "Saving/Salary",
  "permanent_address": {{
    "house_no": "string",
    "street": "string",
    "ward_number": "string",
    "municipality": "string",
    "district": "string"
  }},
  "present_address": {{
    "house_no": "string",
    "street": "string",
    "ward_number": "string",
    "municipality": "string",
    "district": "string"
  }},
  "phone_mobile": "string",
  "email": "string",
  "date_of_birth_ad": "DD/MM/YYYY",
  "date_of_birth_bs": "DD/MM/YYYY",
  "citizenship_number": "XX-XX-XX-XXXXX",
  "citizenship_place_of_issue": "string",
  "citizenship_date_of_issue": "DD/MM/YYYY",
  "pan_number": "string or null",
  "nationality": "string"
}}

RULES:
1. Convert ALL Devanagari digits to English
2. Return ONLY valid JSON, no explanation
3. If a field is not found, use null"""


UTILITY_BILL_PROMPT = """You are parsing a Nepali Utility Bill (Electricity/Mobile).

OCR extracted this text:

---OCR TEXT---
{text}
---END---

EXTRACT AS JSON:
{{
  "utility_type": "electricity/mobile",
  "provider": "NEA/Ncell",
  "consumer_number": "string",
  "customer_name": "string",
  "billing_period": "YYYY-MM",
  "bill_amount": "amount in rupees",
  "due_date": "YYYY-MM-DD",
  "payment_status": "paid/unpaid",
  "payment_date": "YYYY-MM-DD or null",
  "payment_method": "esewa/khalti/bank or null"
}}

RULES:
1. Convert ALL Devanagari digits to English
2. Return ONLY valid JSON
3. If a field is not found, use null"""


REMITTANCE_PROMPT = """You are parsing a Remittance Receipt (Western Union/IME/Prabhu/Himal).

OCR extracted this text:

---OCR TEXT---
{text}
---END---

EXTRACT AS JSON:
{{
  "service_provider": "Western Union/IME/Prabhu/Himal",
  "reference_number": "string",
  "sender_name": "string",
  "sender_country": "string",
  "receiver_name": "string",
  "amount_foreign": "amount in foreign currency",
  "foreign_currency": "USD/QAR/SAR/etc",
  "amount_nrs": "amount in Nepali Rupees",
  "exchange_rate": "rate",
  "transfer_date": "YYYY-MM-DD",
  "disbursement_mode": "bank_deposit/mobile_wallet/cash_pickup"
}}

RULES:
1. Convert ALL Devanagari digits to English
2. Return ONLY valid JSON
3. If a field is not found, use null"""


COOPERATIVE_PASSBOOK_PROMPT = """This is a cooperative passbook document.

---OCR TEXT---
{text}
---END---

Note: Cooperative passbook parsing is not yet implemented.
Return a placeholder JSON:
{{
  "cooperative_name": "to be implemented",
  "member_id": "to be implemented",
  "share_count": null,
  "total_share_value": null,
  "status": "not_implemented"
}}"""


# ============================================================================
# FIELD EXTRACTION FUNCTIONS
# ============================================================================

def extract_citizenship_certificate_fields(raw_text: str) -> Dict:
    try:
        llm_output = call_llm(CITIZENSHIP_PROMPT.format(text=raw_text))
        llm_output = clean_json_response(llm_output)
        extracted = llm_output
    except Exception as e:
        extracted = {
            "full_name": None, "citizenship_number_np": None, "citizenship_number": None,
            "date_of_birth_np": None, "date_of_birth": None, "issued_district": None,
            "father_name": None, "grandfather_name": None, "issued_date_np": None, "issued_date": None
        }

    filled = sum(1 for v in extracted.values() if v is not None)
    confidence = filled / 7

    return {
        "document_type": "citizenship_certificate",
        "status": "verified" if confidence >= 0.5 else "low_confidence",
        "confidence_score": round(confidence, 2),
        "extracted_fields": extracted,
        "flags": [] if confidence >= 0.5 else ["low_confidence"],
        "raw_ocr_text": raw_text
    }


def extract_lalpurja_fields(raw_text: str) -> Dict:
    try:
        llm_output = call_llm(LALPURJA_PROMPT.format(text=raw_text))
        extracted = clean_json_response(llm_output)
    except Exception as e:
        extracted = {
            "owner_name": None, "citizenship_number_np": None, "citizenship_number": None,
            "father_or_husband_name": None, "issued_date_np": None, "issued_date": None,
            "issuing_office": None, "plot_number_np": None, "plot_number": None,
            "land_area": None, "transaction_type": None, "location_district": None,
            "ward_number_np": None, "ward_number": None
        }

    filled = sum(1 for v in extracted.values() if v is not None)
    confidence = filled / 10

    return {
        "document_type": "lalpurja",
        "status": "verified" if confidence >= 0.5 else "low_confidence",
        "confidence_score": round(confidence, 2),
        "extracted_fields": extracted,
        "flags": [] if confidence >= 0.5 else ["low_confidence"],
        "raw_ocr_text": raw_text
    }


def extract_kyc_form_fields(raw_text: str) -> Dict:
    try:
        llm_output = call_llm(KYC_FORM_PROMPT.format(text=raw_text))
        extracted = clean_json_response(llm_output)
    except Exception as e:
        extracted = {
            "customer_id": None, "account_number": None, "full_name_np": None,
            "full_name_en": None, "marital_status": None, "gender": None,
            "purpose_of_account": None, "permanent_address": {}, "present_address": {},
            "phone_mobile": None, "email": None, "date_of_birth_ad": None,
            "date_of_birth_bs": None, "citizenship_number": None,
            "citizenship_place_of_issue": None, "citizenship_date_of_issue": None,
            "pan_number": None, "nationality": None
        }

    filled = sum(1 for v in extracted.values() if v is not None)
    confidence = filled / 15

    return {
        "document_type": "kyc_form",
        "status": "verified" if confidence >= 0.5 else "low_confidence",
        "confidence_score": round(confidence, 2),
        "extracted_fields": extracted,
        "flags": [] if confidence >= 0.5 else ["low_confidence"],
        "raw_ocr_text": raw_text
    }


def extract_utility_bill_fields(raw_text: str) -> Dict:
    try:
        llm_output = call_llm(UTILITY_BILL_PROMPT.format(text=raw_text))
        extracted = clean_json_response(llm_output)
    except Exception as e:
        extracted = {
            "utility_type": None, "provider": None, "consumer_number": None,
            "customer_name": None, "billing_period": None, "bill_amount": None,
            "due_date": None, "payment_status": None, "payment_date": None,
            "payment_method": None
        }

    filled = sum(1 for v in extracted.values() if v is not None)
    confidence = filled / 8

    return {
        "document_type": "utility_bill",
        "status": "verified" if confidence >= 0.5 else "low_confidence",
        "confidence_score": round(confidence, 2),
        "extracted_fields": extracted,
        "flags": [] if confidence >= 0.5 else ["low_confidence"],
        "raw_ocr_text": raw_text
    }


def extract_remittance_receipt_fields(raw_text: str) -> Dict:
    try:
        llm_output = call_llm(REMITTANCE_PROMPT.format(text=raw_text))
        extracted = clean_json_response(llm_output)
    except Exception as e:
        extracted = {
            "service_provider": None, "reference_number": None, "sender_name": None,
            "sender_country": None, "receiver_name": None, "amount_foreign": None,
            "foreign_currency": None, "amount_nrs": None, "exchange_rate": None,
            "transfer_date": None, "disbursement_mode": None
        }

    filled = sum(1 for v in extracted.values() if v is not None)
    confidence = filled / 9

    return {
        "document_type": "remittance_receipt",
        "status": "verified" if confidence >= 0.5 else "low_confidence",
        "confidence_score": round(confidence, 2),
        "extracted_fields": extracted,
        "flags": [] if confidence >= 0.5 else ["low_confidence"],
        "raw_ocr_text": raw_text
    }


def extract_cooperative_passbook_fields(raw_text: str) -> Dict:
    """Dummy implementation for cooperative passbook - to be implemented later."""
    return {
        "document_type": "cooperative_passbook",
        "status": "not_implemented",
        "confidence_score": 0.0,
        "extracted_fields": {
            "cooperative_name": None, "member_id": None, "share_count": None,
            "total_share_value": None, "status": "not_implemented"
        },
        "flags": ["not_implemented"],
        "raw_ocr_text": raw_text
    }


# ============================================================================
# MAIN PARSING FUNCTION
# ============================================================================

EXTRACTORS = {
    "citizenship_certificate": extract_citizenship_certificate_fields,
    "lalpurja": extract_lalpurja_fields,
    "kyc_form": extract_kyc_form_fields,
    "utility_bill": extract_utility_bill_fields,
    "remittance_receipt": extract_remittance_receipt_fields,
    "cooperative_passbook": extract_cooperative_passbook_fields,
}


def parse_single_document(doc_type: str, image_path: str, debug: bool = False, 
                          applicant_id: str = None, document_id: str = None) -> Dict:
    """Parse a single document and return extracted fields with full metadata."""
    if doc_type in DUMMY_DOC_TYPES:
        result = extract_cooperative_passbook_fields("")
        result["metadata"] = _build_metadata(doc_type, image_path, applicant_id, document_id)
        return result

    ocr_func, ocr_engine = get_ocr_for_doc_type(doc_type)
    raw_text, ocr_corrected_rotation, ocr_rotation_angle = ocr_func(image_path)

    # Detect image properties from original
    img = cv2.imread(image_path)
    original_is_rotated, original_rotation_angle = _detect_rotation(img) if img is not None else (False, 0.0)
    scan_dpi = _estimate_dpi(img) if img is not None else 96
    
    # Detect complexity
    ocr_complexity_tag = _detect_complexity(img) if img is not None else "clean"
    
    # Detect document features (stamps, signatures, handwriting)
    doc_features = _detect_document_features(img) if img is not None else {
        "has_stamp": None, "has_signature": None, "has_handwritten_fields": None
    }
    
    # Detect languages
    language_primary, language_secondary = _detect_languages(doc_type)

    if not raw_text:
        return {
            "document_type": doc_type,
            "status": "ocr_failed",
            "confidence_score": 0.0,
            "extracted_fields": {},
            "flags": ["ocr_no_text"],
            "raw_ocr_text": "",
            "ocr_engine": ocr_engine,
            "metadata": _build_metadata(doc_type, image_path, applicant_id, document_id,
                                        scan_dpi=scan_dpi, ocr_complexity_tag=ocr_complexity_tag,
                                        language_primary=language_primary, language_secondary=language_secondary,
                                        is_rotated=ocr_corrected_rotation, 
                                        rotation_angle=ocr_rotation_angle if ocr_corrected_rotation else 0.0,
                                        original_rotation=original_rotation_angle,
                                        doc_features=doc_features)
        }

    extractor = EXTRACTORS.get(doc_type)
    if not extractor:
        return {
            "document_type": doc_type,
            "status": "unknown_type",
            "confidence_score": 0.0,
            "extracted_fields": {},
            "flags": ["unsupported_document_type"],
            "raw_ocr_text": raw_text,
            "ocr_engine": ocr_engine,
            "metadata": _build_metadata(doc_type, image_path, applicant_id, document_id,
                                        scan_dpi=scan_dpi, ocr_complexity_tag=ocr_complexity_tag,
                                        language_primary=language_primary, language_secondary=language_secondary,
                                        is_rotated=ocr_corrected_rotation,
                                        rotation_angle=ocr_rotation_angle if ocr_corrected_rotation else 0.0,
                                        original_rotation=original_rotation_angle,
                                        doc_features=doc_features)
        }

    result = extractor(raw_text)
    result["ocr_engine"] = ocr_engine
    result["metadata"] = _build_metadata(doc_type, image_path, applicant_id, document_id,
                                         scan_dpi=scan_dpi, ocr_complexity_tag=ocr_complexity_tag,
                                         language_primary=language_primary, language_secondary=language_secondary,
                                         is_rotated=ocr_corrected_rotation,
                                         rotation_angle=ocr_rotation_angle if ocr_corrected_rotation else 0.0,
                                         original_rotation=original_rotation_angle,
                                         verified_by_agent=result.get("status") == "verified",
                                         verification_confidence=result.get("confidence_score", 0.0),
                                         anomaly_flag="low_confidence" in result.get("flags", []),
                                         doc_features=doc_features)

    if debug:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        debug_file = DEBUG_DIR / f"{Path(image_path).stem}_{doc_type}_debug.json"
        with open(debug_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    return result


def _build_metadata(doc_type: str, image_path: str, applicant_id: str = None, document_id: str = None,
                    scan_dpi: int = 96, ocr_complexity_tag: str = "clean",
                    language_primary: str = "nepali", language_secondary: str = None,
                    is_rotated: bool = False, rotation_angle: float = 0.0,
                    original_rotation: float = 0.0,
                    verified_by_agent: bool = False, verification_confidence: float = 0.0,
                    anomaly_flag: bool = False, doc_features: Dict = None) -> Dict:
    """Build document registry metadata according to data dictionary."""
    file_path = str(Path(image_path).relative_to(Path(image_path).parent.parent)) if "/" in image_path else image_path
    file_format = Path(image_path).suffix.lstrip(".").lower() or "jpg"
    
    if doc_features is None:
        doc_features = {"has_stamp": None, "has_signature": None, "has_handwritten_fields": None}
    
    return {
        "document_id": document_id,
        "applicant_id": applicant_id,
        "file_path": file_path,
        "file_format": file_format,
        "page_count": 2 if doc_type == "cooperative_passbook" else 1,
        "scan_dpi": scan_dpi,
        "ocr_complexity_tag": ocr_complexity_tag,
        "language_primary": language_primary,
        "language_secondary": language_secondary,
        "has_stamp": doc_features.get("has_stamp"),
        "has_signature": doc_features.get("has_signature"),
        "has_handwritten_fields": doc_features.get("has_handwritten_fields"),
        "is_rotated": is_rotated,
        "rotation_angle_degrees": rotation_angle,
        "original_rotation_degrees": original_rotation,
        "ocr_model_baseline_cer": None,  # From dataset if available
        "verified_by_agent": verified_by_agent,
        "verification_confidence": verification_confidence,
        "anomaly_flag": anomaly_flag
    }


def _detect_document_features(img: np.ndarray) -> Dict:
    """Detect stamps, signatures, and handwritten fields using CV."""
    if img is None:
        return {"has_stamp": None, "has_signature": None, "has_handwritten_fields": None}
    
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Detect stamps (red/orange rubber stamps)
    has_stamp = _detect_stamps(hsv)
    
    # Detect signatures (blue/black ink strokes)
    has_signature = _detect_signatures(hsv, gray)
    
    # Detect handwritten fields (irregular strokes vs uniform printed text)
    has_handwritten = _detect_handwriting(gray)
    
    return {
        "has_stamp": has_stamp,
        "has_signature": has_signature,
        "has_handwritten_fields": has_handwritten
    }


def _detect_stamps(hsv: np.ndarray) -> bool:
    """Detect red/orange rubber stamps in document."""
    # Red stamp mask (HSV ranges for red)
    lower_red1 = np.array([0, 70, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 70, 50])
    upper_red2 = np.array([180, 255, 255])
    
    mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)
    
    # Orange stamp mask
    lower_orange = np.array([10, 100, 100])
    upper_orange = np.array([25, 255, 255])
    mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)
    
    # Combine masks
    mask_stamp = cv2.bitwise_or(mask_red, mask_orange)
    
    # Clean up mask
    kernel = np.ones((5, 5), np.uint8)
    mask_stamp = cv2.morphologyEx(mask_stamp, cv2.MORPH_CLOSE, kernel)
    mask_stamp = cv2.morphologyEx(mask_stamp, cv2.MORPH_OPEN, kernel)
    
    # Find contours
    contours, _ = cv2.findContours(mask_stamp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Check for stamp-like contours (circular/rectangular with sufficient area)
    img_area = hsv.shape[0] * hsv.shape[1]
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > img_area * 0.005:  # At least 0.5% of image
            # Check circularity or rectangularity
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                # Stamps are often circular or rectangular
                if circularity > 0.3 or cv2.boundingRect(contour)[2] > 50:
                    return True
    return False


def _detect_signatures(hsv: np.ndarray, gray: np.ndarray) -> bool:
    """Detect handwritten signatures (blue/black ink)."""
    # Blue ink mask (signatures are often in blue)
    lower_blue = np.array([100, 50, 50])
    upper_blue = np.array([130, 255, 255])
    mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
    
    # Black/dark ink mask
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, 255, 50])
    mask_black = cv2.inRange(hsv, lower_black, upper_black)
    
    # Combine ink masks
    mask_ink = cv2.bitwise_or(mask_blue, mask_black)
    
    # Clean up
    kernel = np.ones((3, 3), np.uint8)
    mask_ink = cv2.morphologyEx(mask_ink, cv2.MORPH_CLOSE, kernel)
    
    # Find contours
    contours, _ = cv2.findContours(mask_ink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Signatures have elongated, connected strokes
    img_area = hsv.shape[0] * hsv.shape[1]
    signature_candidates = 0
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if 100 < area < img_area * 0.05:  # Reasonable size for signature
            # Check aspect ratio (signatures are often wider than tall)
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            
            # Check for elongated shape
            if aspect_ratio > 1.5 or (w > 30 and h < 50):
                # Check for stroke-like pattern (not solid block)
                hull = cv2.convexHull(contour)
                hull_area = cv2.contourArea(hull)
                if hull_area > 0:
                    solidity = area / hull_area
                    if solidity < 0.7:  # Signatures have irregular shapes
                        signature_candidates += 1
    
    return signature_candidates >= 1


def _detect_handwriting(gray: np.ndarray) -> bool:
    """Detect handwritten text vs printed text."""
    # Edge detection
    edges = cv2.Canny(gray, 50, 150)
    
    # Dilate to connect edges
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=1)
    
    # Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Analyze stroke characteristics
    irregular_strokes = 0
    total_strokes = 0
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if 50 < area < 5000:  # Text-like size
            total_strokes += 1
            
            # Check for irregularity (handwritten strokes vary more)
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                # Circularity - handwritten text is less uniform
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                
                # Check bounding box variation
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h if h > 0 else 0
                
                # Handwritten text often has:
                # - Varying aspect ratios
                # - Less circular/uniform shapes
                if circularity < 0.3 or aspect_ratio > 3 or aspect_ratio < 0.3:
                    irregular_strokes += 1
    
    # If significant portion of strokes are irregular, likely handwritten
    if total_strokes > 10:
        irregular_ratio = irregular_strokes / total_strokes
        return irregular_ratio > 0.3
    
    return False


def _detect_rotation(img: np.ndarray) -> Tuple[bool, float]:
    """Detect if image is rotated and return angle."""
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
        
        if lines is not None and len(lines) > 0:
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.degrees(np.arctan2(y2-y1, x2-x1))
                if abs(angle) < 15:  # Only consider near-horizontal lines
                    angles.append(angle)
            
            if angles:
                median_angle = np.median(angles)
                if abs(median_angle) > 1.0:
                    return True, median_angle
    except Exception:
        pass
    return False, 0.0


def _estimate_dpi(img: np.ndarray) -> int:
    """Estimate DPI based on image dimensions and quality."""
    if img is None:
        return 96
    h, w = img.shape[:2]
    # Simple heuristic: larger images likely have higher DPI
    if max(h, w) > 3000:
        return 300
    elif max(h, w) > 2000:
        return 200
    elif max(h, w) > 1000:
        return 150
    else:
        return 96


def _detect_complexity(img: np.ndarray) -> str:
    """Detect OCR complexity based on image quality."""
    if img is None:
        return "clean"
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Check for blur
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < 100:
        return "blur"
    
    # Check for shadows (high contrast variance)
    std_dev = np.std(gray)
    if std_dev > 80:
        return "shadow"
    
    # Check for compression artifacts
    # Simple heuristic: if image is very small
    h, w = gray.shape
    if h * w < 500000:
        return "compression"
    
    return "clean"


def _detect_languages(doc_type: str) -> Tuple[str, str]:
    """Detect primary and secondary languages based on document type."""
    lang_map = {
        "citizenship_certificate": ("nepali", "english"),
        "lalpurja": ("nepali", None),
        "kyc_form": ("nepali", "english"),
        "tax_clearance": ("nepali", "english"),
        "utility_bill": ("nepali", "english"),
        "remittance_receipt": ("english", "nepali"),
        "cooperative_passbook": ("nepali", None)
    }
    return lang_map.get(doc_type, ("nepali", None))
    """Detect if image is rotated and return angle."""
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
        
        if lines is not None and len(lines) > 0:
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.degrees(np.arctan2(y2-y1, x2-x1))
                if abs(angle) < 15:  # Only consider near-horizontal lines
                    angles.append(angle)
            
            if angles:
                median_angle = np.median(angles)
                if abs(median_angle) > 1.0:
                    return True, median_angle
    except Exception:
        pass
    return False, 0.0


def _estimate_dpi(img: np.ndarray) -> int:
    """Estimate DPI based on image dimensions and quality."""
    if img is None:
        return 96
    h, w = img.shape[:2]
    # Simple heuristic: larger images likely have higher DPI
    if max(h, w) > 3000:
        return 300
    elif max(h, w) > 2000:
        return 200
    elif max(h, w) > 1000:
        return 150
    else:
        return 96


def _detect_complexity(img: np.ndarray) -> str:
    """Detect OCR complexity based on image quality."""
    if img is None:
        return "clean"
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Check for blur
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < 100:
        return "blur"
    
    # Check for shadows (high contrast variance)
    std_dev = np.std(gray)
    if std_dev > 80:
        return "shadow"
    
    # Check for compression artifacts
    # Simple heuristic: if image is very small
    h, w = gray.shape
    if h * w < 500000:
        return "compression"
    
    return "clean"


def parse_documents(file_paths: Dict[str, str], debug: bool = False, 
                    applicant_id: str = None) -> Dict:
    """
    Parse all documents from input JSON.
    
    Args:
        file_paths: Dict mapping doc_type to file path
                   e.g., {"citizenship_certificate": "/path/to/cit.jpg", "lalpurja": "/path/to/lal.jpg"}
        debug: If True, save debug images and extracted data
        applicant_id: Optional applicant ID to attach to metadata
    
    Returns:
        Combined result with all extracted documents
    """
    results = {}
    citizenship_numbers = []

    for doc_type, image_path in file_paths.items():
        doc_type_lower = doc_type.lower().strip()

        if doc_type_lower in ["cit", "citizenship", "citizenship_certificate"]:
            doc_type_lower = "citizenship_certificate"
        elif doc_type_lower in ["lalpurja", "land", "malpot"]:
            doc_type_lower = "lalpurja"
        elif doc_type_lower in ["kyc", "kyc_form"]:
            doc_type_lower = "kyc_form"
        elif doc_type_lower in ["utility", "utility_bill", "electricity", "mobile"]:
            doc_type_lower = "utility_bill"
        elif doc_type_lower in ["remittance", "remittance_receipt", "receipt"]:
            doc_type_lower = "remittance_receipt"
        elif doc_type_lower in ["cooperative", "passbook", "cooperative_passbook"]:
            doc_type_lower = "cooperative_passbook"

        result = parse_single_document(doc_type_lower, image_path, debug, applicant_id)
        results[doc_type_lower] = result

        cit_num = result.get("extracted_fields", {}).get("citizenship_number")
        if cit_num:
            citizenship_numbers.append((doc_type_lower, cit_num))

    unique_cit_nums = set([num for _, num in citizenship_numbers])
    mismatch_flag = len(unique_cit_nums) > 1

    primary_citizenship = None
    for dtype in ["citizenship_certificate", "kyc_form", "lalpurja"]:
        if dtype in results:
            cit = results[dtype].get("extracted_fields", {}).get("citizenship_number")
            if cit:
                primary_citizenship = cit
                break

    lalpurja_fields = results.get("lalpurja", {}).get("extracted_fields", {})
    land_area = parse_amount(lalpurja_fields.get("land_area"))

    flags = []
    if mismatch_flag:
        flags.append("citizenship_mismatch_across_documents")

    return {
        "citizenship_number": primary_citizenship,
        "agent_source": "document",
        "features": {
            "asset_backing": {
                "has_lalpurja": "lalpurja" in results,
                "asset_type": "land" if "lalpurja" in results else None,
                "ownership_documented": bool(lalpurja_fields.get("owner_name") or lalpurja_fields.get("citizenship_number")),
                "land_area": land_area,
                "plot_number": lalpurja_fields.get("plot_number"),
                "district": lalpurja_fields.get("location_district"),
                "owner_name": lalpurja_fields.get("owner_name"),
                "document_confidence": results.get("lalpurja", {}).get("confidence_score")
            }
        },
        "flags": flags,
        "all_citizenship_numbers_found": citizenship_numbers if mismatch_flag else None,
        "raw_extracted_data": results
    }


# ============================================================================
# LANGGRAPH NODE
# ============================================================================

def parser_node(state: AgentState):
    file_paths = state.get("file_paths", {})
    if not file_paths:
        return {
            "status": "parser_complete_no_files",
            "extracted_docs": {}
        }

    try:
        applicant_id = state.get("applicant_id")
        result = parse_documents(file_paths, debug=True, applicant_id=applicant_id)

        if not result.get("citizenship_number"):
            errors = state.get("errors", [])
            return {
                "status": "parser_failed",
                "errors": errors + ["Parsing error: Citizenship number not found in the provided documents."]
            }

        return {
            "extracted_docs": result,
            "status": "parser_complete"
        }
    except Exception as e:
        errors = state.get("errors", [])
        return {
            "status": "parser_failed",
            "errors": errors + [f"Parsing error: {str(e)}"]
        }


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parser_agent.py <json_input>")
        print("\nJSON Input Format:")
        print('  {"citizenship": "/path/to/cit.jpg", "lalpurja": "/path/to/lal.jpg"}')
        print("\nSupported doc_types:")
        print("  - citizenship: Nepali Citizenship Certificate")
        print("  - lalpurja: Land Deed (uses PaddleOCR)")
        print("  - kyc_form: Bank KYC Form (uses PaddleOCR)")
        print("  - tax_clearance: Tax Clearance Certificate")
        print("  - utility_bill: Electricity/Mobile Bill")
        print("  - remittance_receipt: International Money Transfer Receipt")
        print("  - cooperative_passbook: Cooperative Passbook (not yet implemented)")
        sys.exit(1)

    json_input = sys.argv[1]
    try:
        file_paths = json.loads(json_input)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input - {e}")
        sys.exit(1)

    result = parse_documents(file_paths, debug=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))
