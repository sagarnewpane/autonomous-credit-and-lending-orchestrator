"""
Unified Document Parsing Agent (Upgraded)
=========================================
Handles all document types from the GIBL Hackathon dataset with advanced
preprocessing, layout-aware OCR, and robust LLM extraction.

Upgrades:
- Universal Preprocessing (Deskewing + Shadow Removal via CLAHE)
- Adaptive Thresholding for Tesseract
- Structured Markdown Prompting for Chandra-OCR
- Dynamic Language Detection from extracted text
- Smarter Stamp Detection (HoughCircles + Strict Circularity)
- Region-Restricted Signature Detection (Bottom 40% of document)
- LLM Prompts immunized against OCR noise/digit-mixing
"""

import pytesseract
import cv2
import json
import numpy as np
import re
import os
import shutil
import requests
import base64
from pathlib import Path
from PIL import Image
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

# ---- Ollama config ----
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:8081/api/generate")
OLLAMA_OCR_MODEL = "fredrezones55/chandra-ocr-2"
OLLAMA_CLEANUP_MODEL = "gemma4:e4b"

# Document types that use Chandra-OCR-2
CHANDRA_OCR_DOC_TYPES = {"citizenship_certificate", "lalpurja", "kyc_form", "utility_bill"}

# Document types that use Tesseract
TESSERACT_DOC_TYPES = {"remittance_receipt"}

# Dummy types
DUMMY_DOC_TYPES = {"cooperative_passbook"}

# Debug output directory
DEBUG_DIR = Path("/Users/sagarnewpane/autonomous-credit-and-lending-orchestrator/ocr_output/debug")

# ============================================================================
# UNIVERSAL PREPROCESSING & UTILITY FUNCTIONS
# ============================================================================

def preprocess_for_ocr(img: np.ndarray) -> np.ndarray:
    """
    Universal preprocessing: deskews minor tilts and removes shadows 
    using CLAHE (Contrast Limited Adaptive Histogram Equalization).
    """
    if img is None:
        return img
        
    # 1. Shadow Removal & Contrast Enhancement (CLAHE)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl, a, b))
    enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

    # 2. Deskewing (Straightening minor tilts up to 15 degrees)
    gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    gray_inv = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray_inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # Only correct if tilt is noticeable but not a 90-degree flip
        if 1.0 < abs(angle) < 15.0:
            (h, w) = enhanced.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            enhanced = cv2.warpAffine(enhanced, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    return enhanced

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
    """Adaptive thresholding handles shadows and uneven lighting far better than Otsu."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    thresh = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY, 31, 10)
    return thresh

def resize_if_large(img: np.ndarray, max_side: int = 4000) -> np.ndarray:
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
    """Text-only cleanup/extraction call routed through Ollama."""
    payload = {
        "model": OLLAMA_CLEANUP_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1}
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()
    result = response.json()
    text = result.get("response", "") or result.get("thinking", "")
    return text.strip()

# ============================================================================
# OCR ENGINES
# ============================================================================

def _is_front_back_image(img: np.ndarray) -> bool:
    h, w = img.shape[:2]
    if h < 1500:
        return False
    aspect = h / w
    return aspect > 1.4

def _split_front_back(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    h, w = img.shape[:2]
    mid = h // 2
    return img[:mid, :], img[mid:, :]

def _ocr_half(img: np.ndarray, lang: str = 'nep+eng') -> str:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    scale = 2
    gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 31, 10)
    denoised = cv2.fastNlMeansDenoising(binary, h=15)

    texts = []
    for psm in [6, 4, 3]:
        config = f'--oem 3 --psm {psm}'
        text = pytesseract.image_to_string(denoised, lang=lang, config=config)
        if text.strip():
            texts.append(text.strip())

    for psm in [6, 3]:
        config = f'--oem 3 --psm {psm}'
        text = pytesseract.image_to_string(gray, lang=lang, config=config)
        if text.strip():
            texts.append(text.strip())

    if texts:
        return max(texts, key=len)
    return ""

def run_tesseract_ocr(image_path: str, lang: str = 'nep+eng') -> Tuple[str, bool, float]:
    img = cv2.imread(image_path)
    if img is None:
        return "", False, 0.0

    # Apply Universal Preprocessing
    img = preprocess_for_ocr(img)

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

    if _is_front_back_image(img):
        front, back = _split_front_back(img)
        save_debug_image(front, Path(image_path).stem, "front")
        save_debug_image(back, Path(image_path).stem, "back")
        text_front = _ocr_half(front, lang)
        text_back = _ocr_half(back, lang)
        combined = f"=== FRONT ===\n{text_front}\n\n=== BACK ===\n{text_back}"
        return combined.strip(), was_rotated, rotation_angle

    processed_img = optimize_image_for_ocr(img)
    save_debug_image(processed_img, Path(image_path).stem, "tesseract_preprocessed")
    custom_config = r'--oem 3 --psm 3'
    text = pytesseract.image_to_string(processed_img, lang=lang, config=custom_config)
    return text.strip(), was_rotated, rotation_angle

def run_chandra_ocr(image_path: str) -> Tuple[str, bool, float]:
    img = cv2.imread(image_path)
    if img is None:
        return "", False, 0.0

    # Apply Universal Preprocessing before sending to LLM OCR
    img = preprocess_for_ocr(img)
    img = resize_if_large(img)
    
    temp_path = str(DEBUG_DIR / f"{Path(image_path).stem}_chandra_temp.jpg")
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(temp_path, img)

    try:
        with open(temp_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode('utf-8')

        # Upgraded Prompt: Forces structural markdown preservation
        ocr_prompt = (
            "You are an expert OCR system. Extract all text from this document image. "
            "Preserve the document's layout and structure. "
            "If there are tables or key-value pairs, format them using Markdown tables. "
            "Include all fields, labels, and values exactly as they appear. Do not omit anything."
        )

        payload = {
            "model": OLLAMA_OCR_MODEL,
            "prompt": ocr_prompt,
            "images": [encoded_image],
            "stream": False
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()

        raw_text = result.get("response", "") or result.get("thinking", "")
        save_debug_image(img, Path(image_path).stem, "chandra_preprocessed")

        return raw_text.strip(), False, 0.0

    except Exception as e:
        print(f"[warn] Chandra-OCR-2 failed: {e} - falling back to Tesseract")
        text, rotated, angle = run_tesseract_ocr(image_path)
        return text, rotated, angle

def get_ocr_for_doc_type(doc_type: str) -> Tuple[Callable, str]:
    if doc_type in CHANDRA_OCR_DOC_TYPES:
        return run_chandra_ocr, "chandra_ocr"
    else:
        return run_tesseract_ocr, "tesseract"

# ============================================================================
# DOCUMENT TYPE & LANGUAGE DETECTION
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

def _detect_languages_from_text(raw_text: str) -> Tuple[str, Optional[str]]:
    """Dynamically detect primary and secondary languages from extracted text."""
    if not raw_text:
        return "unknown", None
    has_devanagari = bool(re.search(r'[\u0900-\u097F]', raw_text))
    has_latin = bool(re.search(r'[a-zA-Z]', raw_text))
    
    if has_devanagari and has_latin:
        dev_count = len(re.findall(r'[\u0900-\u097F]', raw_text))
        lat_count = len(re.findall(r'[a-zA-Z]', raw_text))
        return ("nepali", "english") if dev_count > lat_count else ("english", "nepali")
    elif has_devanagari:
        return "nepali", None
    elif has_latin:
        return "english", None
    return "unknown", None

# ============================================================================
# LLM-BASED FIELD EXTRACTION PROMPTS (IMMUNIZED AGAINST OCR NOISE)
# ============================================================================

CITIZENSHIP_PROMPT = """
You are an expert document parser specializing in Nepali Citizenship Certificates. 

OCR extracted this text:
---OCR TEXT---
{text}
---END---

Your task is to parse this into a valid JSON object. Follow these instructions strictly:

1. FIELD IDENTIFICATION:
   - Identify fields based on their semantic meaning, not just exact label matching, as formatting can vary.
   - For "Father/Mother" fields: Some documents list "बाबुको नाम" (Father) and "आमाको नाम" (Mother). Identify these based on the prefix words regardless of order.
   - For Date of Birth (जन्म मिति): This is often structured as "Year (साल), Month (महिना), Day (गते)". Extract the numeric values for each and normalize them.
   - Gender/Sex: Look for "लिङ्ग" or "Sex" field.
   - Birth Place: Look for "जन्म स्थान" or "Birth Place" - extract district and municipality.
   - Permanent Address: Look for "स्थायी बासस्थान" or "Permanent Address" - extract district, municipality, and ward number.
   - Citizenship Type: Look for "नागरिकता किसिम" (e.g., वंशज, वैदेशिक, जन्मतः).
   - Issuing Office: Look for "जिल्ला प्रशासन कार्यालय" or the office name.
   - Issuing Officer: Look for the officer name near signature/seal area.

2. NORMALIZATION RULES:
   - Always return original values in the "_np" fields (keep Devanagari numerals).
   - Convert ALL main fields (without _np suffix) to English digits/format.
   - If a date is in "Year: X, Month: Y, Day: Z" format, combine them into "YYYY-MM-DD" for the main field.
   - For Citizenship Number, ensure it is formatted as "DD-DD-DD-DDDDD".
   - For BS (Bikram Sambat) dates, keep as-is in _bs fields.

3. OUTPUT:
   Return ONLY a valid JSON object. Use `null` if a field is absolutely not present.

{{
  "full_name_np": "Full name in original Devanagari",
  "full_name": "Full name in English",
  "sex": "Male/Female",
  "citizenship_number_np": "Original Devanagari string",
  "citizenship_number": "Normalized English digit string (e.g., 65-02-79-00396)",
  "citizenship_type": "Type in English e.g. descendant, foreign, by_birth",
  "date_of_birth_np": "Original Devanagari string",
  "date_of_birth": "Normalized YYYY-MM-DD (AD)",
  "date_of_birth_bs": "Date of Birth in BS (Bikram Sambat) format YYYY-MM-DD if available",
  "birth_district": "District of birth",
  "birth_municipality": "Municipality of birth",
  "father_name_np": "Father's full name in Devanagari",
  "father_name": "Father's full name in English",
  "mother_name_np": "Mother's full name in Devanagari",
  "mother_name": "Mother's full name in English",
  "grandfather_name_np": "Grandfather's full name in Devanagari",
  "grandfather_name": "Grandfather's full name in English",
  "permanent_address_district": "District of permanent address",
  "permanent_address_municipality": "Municipality of permanent address",
  "permanent_address_ward": "Ward number of permanent address",
  "issued_district": "District where issued",
  "issued_date_np": "Original Devanagari string",
  "issued_date": "Normalized YYYY-MM-DD",
  "issuing_office": "Office that issued the certificate",
  "issuing_officer_name": "Name of issuing officer"
}}
"""

LALPURJA_PROMPT = """You are parsing a Nepali Land Revenue Office document (मालपोत कार्यालय / Lalpurja).

OCR extracted this text (table format may be jumbled):
---OCR TEXT---
{text}
---END---

CRITICAL FIELDS FOR LOAN SCORING:
1. स्वामीको नाम / Owner's Name = person who owns the land
2. नागरिकता नं. / Citizenship No = owner's ID (format: DDD-DDD-DDDDD)
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
  "citizenship_number": "DDD-DDD-DDDDD (MUST be English digits)",
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

RULES:
- The OCR text may contain noise, typos, or misread characters (e.g., mixing English and Devanagari digits like '३७-0२').
- Use your contextual understanding of Nepali documents to fix obvious OCR errors and infer the correct value.
- Always include the original Nepali/Devanagari values in the _np fields.
- Convert ALL numbers to English digits for the main fields (०=0, १=1, २=2, ३=3, ४=4, ५=5, ६=6, ७=7, ८=8, ९=9).
- Look for area numbers near "क्षेत्रफल" or in table right side.
- If field not found, use null.
- Return ONLY JSON, no extra text."""

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
  "citizenship_number": "DDD-DDD-DDDDD",
  "citizenship_place_of_issue": "string",
  "citizenship_date_of_issue": "DD/MM/YYYY",
  "pan_number": "string or null",
  "nationality": "string"
}}

RULES:
- The OCR text may contain noise, typos, or misread characters (e.g., mixing English and Devanagari digits like '३७-0२').
- Use your contextual understanding of Nepali documents to fix obvious OCR errors and infer the correct value.
- Convert ALL Devanagari digits to English.
- Return ONLY valid JSON, no explanation.
- If a field is not found, use null."""

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
- The OCR text may contain noise, typos, or misread characters.
- Use your contextual understanding to fix obvious OCR errors and infer the correct value.
- Convert ALL Devanagari digits to English.
- Return ONLY valid JSON.
- If a field is not found, use null."""

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
- The OCR text may contain noise, typos, or misread characters.
- Use your contextual understanding to fix obvious OCR errors and infer the correct value.
- Convert ALL Devanagari digits to English.
- Return ONLY valid JSON.
- If a field is not found, use null."""

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
        extracted = clean_json_response(llm_output)
    except Exception:
        extracted = {
            "full_name_np": None, "full_name": None, "sex": None,
            "citizenship_number_np": None, "citizenship_number": None,
            "citizenship_type": None, "date_of_birth_np": None, "date_of_birth": None,
            "date_of_birth_bs": None, "birth_district": None, "birth_municipality": None,
            "father_name_np": None, "father_name": None,
            "mother_name_np": None, "mother_name": None,
            "grandfather_name_np": None, "grandfather_name": None,
            "permanent_address_district": None, "permanent_address_municipality": None,
            "permanent_address_ward": None, "issued_district": None,
            "issued_date_np": None, "issued_date": None,
            "issuing_office": None, "issuing_officer_name": None
        }

    filled = sum(1 for v in extracted.values() if v is not None)
    total = len(extracted)
    confidence = filled / total if total > 0 else 0.0
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
    except Exception:
        extracted = {
            "owner_name": None, "citizenship_number_np": None, "citizenship_number": None,
            "father_or_husband_name": None, "issued_date_np": None, "issued_date": None,
            "issuing_office": None, "plot_number_np": None, "plot_number": None,
            "land_area": None, "transaction_type": None, "location_district": None,
            "ward_number_np": None, "ward_number": None
        }

    filled = sum(1 for v in extracted.values() if v is not None)
    total = len(extracted)
    confidence = filled / total if total > 0 else 0.0
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
    except Exception:
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
    total = len(extracted)
    confidence = filled / total if total > 0 else 0.0
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
    except Exception:
        extracted = {
            "utility_type": None, "provider": None, "consumer_number": None,
            "customer_name": None, "billing_period": None, "bill_amount": None,
            "due_date": None, "payment_status": None, "payment_date": None,
            "payment_method": None
        }

    filled = sum(1 for v in extracted.values() if v is not None)
    total = len(extracted)
    confidence = filled / total if total > 0 else 0.0
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
    except Exception:
        extracted = {
            "service_provider": None, "reference_number": None, "sender_name": None,
            "sender_country": None, "receiver_name": None, "amount_foreign": None,
            "foreign_currency": None, "amount_nrs": None, "exchange_rate": None,
            "transfer_date": None, "disbursement_mode": None
        }

    filled = sum(1 for v in extracted.values() if v is not None)
    total = len(extracted)
    confidence = filled / total if total > 0 else 0.0
    return {
        "document_type": "remittance_receipt",
        "status": "verified" if confidence >= 0.5 else "low_confidence",
        "confidence_score": round(confidence, 2),
        "extracted_fields": extracted,
        "flags": [] if confidence >= 0.5 else ["low_confidence"],
        "raw_ocr_text": raw_text
    }

def extract_cooperative_passbook_fields(raw_text: str) -> Dict:
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
# SMART CV FEATURE DETECTION
# ============================================================================

def _detect_document_features(img: np.ndarray) -> Dict:
    """Detect stamps, signatures, and handwritten fields using CV."""
    if img is None:
        return {"has_stamp": None, "has_signature": None, "has_handwritten_fields": None}

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    has_stamp = _detect_stamps(hsv)
    has_signature = _detect_signatures(img)
    has_handwritten = _detect_handwriting(gray)

    return {
        "has_stamp": has_stamp,
        "has_signature": has_signature,
        "has_handwritten_fields": has_handwritten
    }

def _detect_stamps(hsv: np.ndarray) -> bool:
    """Detect red/orange circular rubber stamps in document."""
    lower_red1 = np.array([0, 70, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 70, 50])
    upper_red2 = np.array([180, 255, 255])
    mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask_red = cv2.bitwise_or(mask_red1, mask_red2)

    lower_orange = np.array([10, 100, 100])
    upper_orange = np.array([25, 255, 255])
    mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)

    mask_stamp = cv2.bitwise_or(mask_red, mask_orange)

    kernel = np.ones((5, 5), np.uint8)
    mask_stamp = cv2.morphologyEx(mask_stamp, cv2.MORPH_CLOSE, kernel)
    mask_stamp = cv2.morphologyEx(mask_stamp, cv2.MORPH_OPEN, kernel)

    # Use HoughCircles to detect circular seal shapes
    gray_mask = cv2.cvtColor(cv2.bitwise_and(hsv, hsv, mask=mask_stamp), cv2.COLOR_HSV2BGR)
    gray_mask = cv2.cvtColor(gray_mask, cv2.COLOR_BGR2GRAY)
    circles = cv2.HoughCircles(gray_mask, cv2.HOUGH_GRADIENT, dp=1.2, minDist=50,
                               param1=50, param2=30, minRadius=30, maxRadius=0)
    if circles is not None:
        return True

    # Fallback to contour area/circularity check
    contours, _ = cv2.findContours(mask_stamp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = hsv.shape[0] * hsv.shape[1]
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > img_area * 0.005:
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                if circularity > 0.4:  # Stricter circularity threshold
                    return True
    return False

def _detect_signatures(img: np.ndarray) -> bool:
    """Detect handwritten signatures in the bottom 40% of the document (blue/black ink)."""
    h, w = img.shape[:2]
    # Signatures are almost always in the bottom 40% of a document
    bottom_img = img[int(h * 0.6):, :]
    
    hsv = cv2.cvtColor(bottom_img, cv2.COLOR_BGR2HSV)
    
    # Look for dark ink (blue/black) in the bottom section
    lower_dark = np.array([0, 0, 0])
    upper_dark = np.array([180, 255, 100])
    mask_ink = cv2.inRange(hsv, lower_dark, upper_dark)

    kernel = np.ones((3, 3), np.uint8)
    mask_ink = cv2.morphologyEx(mask_ink, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask_ink, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    signature_candidates = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        # Signatures are usually within this size range
        if 200 < area < 50000:
            x, y, rw, rh = cv2.boundingRect(contour)
            aspect_ratio = rw / float(rh)
            if aspect_ratio > 1.5:  # Signatures are wider than they are tall
                signature_candidates += 1
                
    return signature_candidates >= 1

def _detect_handwriting(gray: np.ndarray) -> bool:
    """Detect handwritten text vs printed text."""
    edges = cv2.Canny(gray, 50, 150)
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    irregular_strokes = 0
    total_strokes = 0
    for contour in contours:
        area = cv2.contourArea(contour)
        if 50 < area < 5000:
            total_strokes += 1
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h if h > 0 else 0
                if circularity < 0.3 or aspect_ratio > 3 or aspect_ratio < 0.3:
                    irregular_strokes += 1

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
                if abs(angle) < 15:
                    angles.append(angle)
            if angles:
                median_angle = np.median(angles)
                if abs(median_angle) > 1.0:
                    return True, median_angle
    except Exception:
        pass
    return False, 0.0

def _estimate_dpi(img: np.ndarray) -> int:
    if img is None:
        return 96
    h, w = img.shape[:2]
    if max(h, w) > 3000: return 300
    elif max(h, w) > 2000: return 200
    elif max(h, w) > 1000: return 150
    else: return 96

def _detect_complexity(img: np.ndarray) -> str:
    if img is None:
        return "clean"
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < 100: return "blur"
    std_dev = np.std(gray)
    if std_dev > 80: return "shadow"
    h, w = gray.shape
    if h * w < 500000: return "compression"
    return "clean"

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

    img = cv2.imread(image_path)
    original_is_rotated, original_rotation_angle = _detect_rotation(img) if img is not None else (False, 0.0)
    scan_dpi = _estimate_dpi(img) if img is not None else 96
    ocr_complexity_tag = _detect_complexity(img) if img is not None else "clean"
    
    # Use preprocessed image for feature detection
    img_processed = preprocess_for_ocr(img) if img is not None else None
    doc_features = _detect_document_features(img_processed) if img_processed is not None else {
        "has_stamp": None, "has_signature": None, "has_handwritten_fields": None
    }

    # Dynamic Language Detection
    language_primary, language_secondary = _detect_languages_from_text(raw_text)

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


def parse_single_document_from_text(doc_type: str, raw_text: str, ocr_engine: str,
                                     ocr_corrected_rotation: bool, ocr_rotation_angle: float,
                                     image_path: str, debug: bool = False,
                                     applicant_id: str = None, document_id: str = None) -> Dict:
    """Parse a document when OCR text is already extracted (e.g., from multiple images)."""
    img = cv2.imread(image_path)
    original_is_rotated, original_rotation_angle = _detect_rotation(img) if img is not None else (False, 0.0)
    scan_dpi = _estimate_dpi(img) if img is not None else 96
    ocr_complexity_tag = _detect_complexity(img) if img is not None else "clean"

    img_processed = preprocess_for_ocr(img) if img is not None else None
    doc_features = _detect_document_features(img_processed) if img_processed is not None else {
        "has_stamp": None, "has_signature": None, "has_handwritten_fields": None
    }

    language_primary, language_secondary = _detect_languages_from_text(raw_text)

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
        "ocr_model_baseline_cer": None,
        "verified_by_agent": verified_by_agent,
        "verification_confidence": verification_confidence,
        "anomaly_flag": anomaly_flag
    }

def _run_ocr_on_images(image_paths: List[str], ocr_func: Callable) -> Tuple[str, bool, float]:
    """Run OCR on multiple images and combine the text."""
    all_texts = []
    was_rotated = False
    rotation_angle = 0.0

    for path in image_paths:
        text, rotated, angle = ocr_func(path)
        if text.strip():
            all_texts.append(text.strip())
        if rotated:
            was_rotated = True
            rotation_angle = angle

    combined = "\n\n".join(all_texts)
    return combined, was_rotated, rotation_angle


def parse_documents(file_paths: Dict[str, Any], debug: bool = False,
                     applicant_id: str = None) -> Dict:
    results = {}
    citizenship_numbers = []
    SKIP_DOC_TYPES = {"bank_statement"}

    for doc_type, image_path in file_paths.items():
        doc_type_lower = doc_type.lower().strip()

        if doc_type_lower in SKIP_DOC_TYPES:
            continue

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

        # Support multiple images per doc type (e.g., citizenship front + back)
        if isinstance(image_path, list):
            image_paths_list = [p for p in image_path if p]
            if not image_paths_list:
                continue
            ocr_func, ocr_engine = get_ocr_for_doc_type(doc_type_lower)
            raw_text, ocr_corrected_rotation, ocr_rotation_angle = _run_ocr_on_images(image_paths_list, ocr_func)
            result = parse_single_document_from_text(
                doc_type_lower, raw_text, ocr_engine, ocr_corrected_rotation, ocr_rotation_angle,
                image_paths_list[0], debug, applicant_id
            )
        else:
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
        print("  - lalpurja: Land Deed (uses Chandra-OCR-2 via Ollama)")
        print("  - kyc_form: Bank KYC Form (uses Chandra-OCR-2 via Ollama)")
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