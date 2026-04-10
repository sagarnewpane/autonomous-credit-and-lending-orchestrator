
import pytesseract
import cv2
from groq import Groq
import json
import numpy as np
from PIL import Image
from dotenv import load_dotenv
import re
from dataclasses import dataclass
from typing import Optional,Dict,List
import os

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
load_dotenv()



def run_ocr(image_path, lang='nep+eng'):
    """Try multiple rotations/flips, return best OCR text"""
    img = cv2.imread(image_path)
    if img is None:
        return "OCR_ERROR: Could not load image"
    
    best_text = ""
    
    # Try 4 rotations × 2 flips = 8 combinations
    rotations = [0, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE, cv2.ROTATE_180]
    
    for rot in rotations:
        if rot == 0:
            rotated = img.copy()
        else:
            rotated = cv2.rotate(img, rot)
        
        for flip in [False, True]:
            test_img = rotated.copy()
            if flip:
                test_img = cv2.flip(test_img, 1)
            
            gray = cv2.cvtColor(test_img, cv2.COLOR_BGR2GRAY)
            text = pytesseract.image_to_string(gray, lang=lang)
            
            if len(text) > len(best_text):
                best_text = text
    
    return best_text.strip()
    


    
def extract_citizenship_fields(raw_text: str) -> Dict:
    """Use LLM to extract fields from messy OCR text"""
    
    # Initialize Groq client (use your existing key)
    client = Groq(api_key=os.getenv("GROQ_API_KEY")) 
    
    prompt = f"""You are parsing a Nepali Citizenship Certificate.
    
OCR extracted this text (mix of Nepali and English field labels):

---OCR TEXT---
{raw_text}
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
  "citizenship_number": "number with dashes like 37-02-75-05633",
  "date_of_birth": "date in any format found",
  "issued_district": "district name",
  "father_name": "father's name",
  "grandfather_name": "grandfather's name",
  "issued_date": "date if found, else null"
}}

Rules:
- Convert Nepali numbers to English if needed (०=0, १=1, २=2, etc.)
- If field not found, use null
- Return ONLY the JSON object, no extra text"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Fast and cheap
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        llm_output = response.choices[0].message.content
        
        llm_output = llm_output.strip()
        if llm_output.startswith("```json"):
            llm_output = llm_output[7:]  # Remove ```json
        if llm_output.startswith("```"):
            llm_output = llm_output[3:]  # Remove ```
        if llm_output.endswith("```"):
            llm_output = llm_output[:-3]  # Remove trailing ```
        llm_output = llm_output.strip()
        
        # print(f"Cleaned LLM output:\n{llm_output}\n{'='*50}")
        # Parse LLM JSON response
        try:
            extracted = json.loads(llm_output)
        except:
            # Fallback if LLM returns non-JSON
            extracted = {
                "full_name": None,
                "citizenship_number": None,
                "date_of_birth": None,
                "issued_district": None,
                "father_name": None,
                "grandfather_name": None,
                "issued_date": None
            }
        
        # Calculate confidence based on filled fields
        filled = sum(1 for v in extracted.values() if v is not None)
        confidence = filled / 7  # 7 total fields
        
        return {
            "document_type": "citizenship",
            "status": "verified" if confidence >= 0.5 else "low_confidence",
            "confidence_score": round(confidence, 2),
            "extracted_fields": extracted,
            "flags": [] if confidence >= 0.5 else ["low_confidence"],
            "raw_ocr_text": raw_text
        }
        
    except Exception as e:
        # Fallback to empty result if LLM fails
        return {
            "document_type": "citizenship",
            "status": "failed",
            "confidence_score": 0.0,
            "extracted_fields": {
                "full_name": None,
                "citizenship_number": None,
                "date_of_birth": None,
                "issued_district": None,
                "father_name": None,
                "grandfather_name": None,
                "issued_date": None
            },
            "flags": ["llm_error", str(e)],
            "raw_ocr_text": raw_text
        }

    

def extract_lalpurja_fields(raw_text: str) -> Dict:
    """Use LLM to extract fields from Lalpurja (land deed)"""
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    prompt = f"""You are parsing a Nepali Land Revenue Office document (मालपोत कार्यालय / Lalpurja).
    
OCR extracted this text (table format may be jumbled):

---OCR TEXT---
{raw_text}
---END---

CRITICAL FIELDS FOR LOAN SCORING:
1. स्वामीको नाम / Owner's Name = person who owns the land
2. नागरिकता नं. / Citizenship No = owner's ID (format: XX-XX-XX-XXXXX)
3. बाबु/पतिको नाम / Father or Husband's Name
4. जारी मिति / Issue Date = when document was issued
5. जारी गर्ने कार्यालय / Issuing Office = which office issued this

LAND DETAILS (look in table section):
6. कित्ता नं. / Plot Number = usually format like "123-क" or just "123" (look for numbers near "कित्ता")
7. क्षेत्रफल / Land Area = number like "324.96" (area in sq meters or ropani/aana)
8. ब्यहोरा / Transaction Type = e.g., "करोबार ब्यहोरा राजिनामा" (inheritance/sale)

LOCATION:
9. जिल्ला / District = from address section
10. वडा नं. / Ward Number = ward number

Return ONLY valid JSON:
{{
  "owner_name": "owner's full name",
  "citizenship_number": "XX-XX-XX-XXXXX",
  "father_or_husband_name": "father or husband name",
  "issued_date": "date",
  "issuing_office": "office name",
  "plot_number": "plot number like 123 or 123-क",
  "land_area": "area number like 324.96",
  "transaction_type": "transaction description",
  "location_district": "district name",
  "ward_number": "ward number"
}}

Rules:
- Extract numbers even if mixed with Nepali text (e.g., "123-क" → "123-क" or "123")
- Look for area numbers near "क्षेत्रफल" or in table right side
- If field not found, use null
- Return ONLY JSON, no extra text"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        llm_output = response.choices[0].message.content
        
        # Clean markdown if present
        llm_output = llm_output.strip()
        if llm_output.startswith("```json"):
            llm_output = llm_output[7:]
        if llm_output.startswith("```"):
            llm_output = llm_output[3:]
        if llm_output.endswith("```"):
            llm_output = llm_output[:-3]
        llm_output = llm_output.strip()
        
        try:
            extracted = json.loads(llm_output)
        except:
            extracted = {
                "owner_name": None,
                "plot_number": None,
                "land_area": None,
                "district": None,
                "municipality": None,
                "ward_number": None,
                "old_address": None
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
        
    except Exception as e:
        return {
            "document_type": "lalpurja",
            "status": "failed",
            "confidence_score": 0.0,
            "extracted_fields": {
                "owner_name": None,
                "plot_number": None,
                "land_area": None,
                "district": None,
                "municipality": None,
                "ward_number": None,
                "old_address": None
            },
            "flags": ["llm_error", str(e)],
            "raw_ocr_text": raw_text
        }


def extract_tax_clearance_fields(raw_text: str) -> Dict:
    """Use LLM to extract fields from Nepali Tax Clearance Certificate (कर चुक्ता प्रमाण पत्र)"""
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    prompt = f"""You are parsing a Nepali Tax Clearance Certificate (कर चुक्ता प्रमाण पत्र) from the Inland Revenue Department (आन्तरिक राजस्व विभाग).

OCR extracted this text (mix of Nepali and English):

---OCR TEXT---
{raw_text}
---END---

CRITICAL FIELDS TO EXTRACT:
1. कर चुक्ता नं. / Tax Clearance No = certificate number (e.g., "९२३५५" or "92355")
2. करदाताको नाम / Taxpayer Name = person's full name (e.g., "राम बहादुर थापा")
3. स्थायी लेखा नं. / Permanent Account Number (PAN) = number like "२५२५२५२२२" or "252525222"
4. नागरिकता नं. / Citizenship No = format XX-XX-XX-XXXXX (e.g., "३७-०२-७५-०१७३३" or "37-02-75-01733")
5. जारी मिति / Issue Date = date when certificate was issued (e.g., "२०८२.१२.२५" or "2082.12.25")
6. यो विवरण मिति / Statement Date = date of tax statement (e.g., "२०८२.१२.२०" or "2082.12.20")
7. आय विवरण पेश गरेको मिति / Income Statement Filed Date = date in table (e.g., "२०७९.५२.२०" or "2079.52.20")
8. जम्मा आय (कारोबार) रकम रु. / Total Income/Business Amount = amount like "५०,००,०००.००" or "50,00,000.00"
9. कर योग्य आय रु. / Taxable Income = amount like "२९,४१६.००" or "29,416.00"
10. दाखिला गरेको कर रकम रु. / Tax Paid Amount = amount like "२५,२५०.००" or "25,250.00"
11. कर अधिकृत / Tax Officer Name = name at bottom (e.g., "रामकृष्ण महर्जन")
12. कार्यालय / Issuing Office = office name (e.g., "आन्तरिक राजस्व कार्यालय काठमाडौं")

Return ONLY valid JSON:
{{
  "tax_clearance_number": "certificate number",
  "taxpayer_name": "full name",
  "pan_number": "PAN number",
  "citizenship_number": "XX-XX-XX-XXXXX",
  "issue_date": "YYYY.MM.DD format",
  "statement_date": "YYYY.MM.DD format",
  "income_statement_filed_date": "YYYY.MM.DD format",
  "total_income_amount": "amount in rupees",
  "taxable_income": "amount in rupees",
  "tax_paid_amount": "amount in rupees",
  "tax_officer_name": "officer name",
  "issuing_office": "office name"
}}

Rules:
- Convert Nepali numbers to English digits (०=0, १=1, २=2, ३=3, ४=4, ५=5, ६=6, ७=7, ८=8, ९=9)
- Keep amounts as strings with commas and decimals preserved
- If field not found, use null
- Return ONLY the JSON object, no extra text"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        llm_output = response.choices[0].message.content
        
        # Clean markdown if present
        llm_output = llm_output.strip()
        if llm_output.startswith("```json"):
            llm_output = llm_output[7:]
        if llm_output.startswith("```"):
            llm_output = llm_output[3:]
        if llm_output.endswith("```"):
            llm_output = llm_output[:-3]
        llm_output = llm_output.strip()
        
        try:
            extracted = json.loads(llm_output)
        except:
            extracted = {
                "tax_clearance_number": None,
                "taxpayer_name": None,
                "pan_number": None,
                "citizenship_number": None,
                "issue_date": None,
                "statement_date": None,
                "income_statement_filed_date": None,
                "total_income_amount": None,
                "taxable_income": None,
                "tax_paid_amount": None,
                "tax_officer_name": None,
                "issuing_office": None
            }
        
        filled = sum(1 for v in extracted.values() if v is not None)
        confidence = filled / 12  # 12 total fields
        
        return {
            "document_type": "tax_clearance",
            "status": "verified" if confidence >= 0.5 else "low_confidence",
            "confidence_score": round(confidence, 2),
            "extracted_fields": extracted,
            "flags": [] if confidence >= 0.5 else ["low_confidence"],
            "raw_ocr_text": raw_text
        }
        
    except Exception as e:
        return {
            "document_type": "tax_clearance",
            "status": "failed",
            "confidence_score": 0.0,
            "extracted_fields": {
                "tax_clearance_number": None,
                "taxpayer_name": None,
                "pan_number": None,
                "citizenship_number": None,
                "issue_date": None,
                "statement_statement_date": None,
                "income_statement_filed_date": None,
                "total_income_amount": None,
                "taxable_income": None,
                "tax_paid_amount": None,
                "tax_officer_name": None,
                "issuing_office": None
            },
            "flags": ["llm_error", str(e)],
            "raw_ocr_text": raw_text
        }

def format_for_scoring(extracted_data: dict, doc_type: str) -> dict:
    """
    Format Document Agent output for Scoring Agent
    Minimal format: citizenship_number + agent_source + features
    """
    
    # Parse amount helper
    def parse_amount(amount_str):
        if not amount_str:
            return None
        cleaned = str(amount_str).replace(",", "").replace("रू.", "").replace("Rs.", "").strip()
        try:
            return float(cleaned)
        except:
            return None
    
    # Get citizenship number (from any doc type)
    citizenship_number = (
        extracted_data.get("citizenship_number") or 
        extracted_data.get("extracted_fields", {}).get("citizenship_number")
    )
    
    # Build features based on document type
    features = {}
    
    if doc_type == "tax_clearance":
        annual_income = parse_amount(
            extracted_data.get("total_income_amount") or 
            extracted_data.get("extracted_fields", {}).get("total_income_amount")
        )
        tax_paid = parse_amount(
            extracted_data.get("tax_paid_amount") or 
            extracted_data.get("extracted_fields", {}).get("tax_paid_amount")
        )
        
        features = {
            "doc_annual_income": annual_income,
            "doc_monthly_income": round(annual_income / 12, 2) if annual_income else None,
            "tax_compliance_flag": 1 if tax_paid and tax_paid > 0 else 0,
            "tax_paid_amount": tax_paid,
            "effective_tax_rate": round(tax_paid / annual_income, 5) if annual_income and annual_income > 0 else None
        }
        
    elif doc_type == "citizenship":
        # Identity only — no financial features
        features = {
            "doc_annual_income": None,
            "doc_monthly_income": None,
            "tax_compliance_flag": 0,
            "tax_paid_amount": None,
            "effective_tax_rate": None
        }
        
    elif doc_type == "lalpurja":
        # Skip for now — land data goes to Compliance later
        return None  # Don't send to Scoring Agent
    
    return {
        "citizenship_number": citizenship_number,
        "agent_source": "document",
        "features": features
    }

def detect_document_type(raw_text: str) -> str:
        text_lower = raw_text.lower()
        citizenship_keywords = ['नागरिकता', 'citizenship', 'जन्म मिति', 'नागरिकता प्रमाणपत्र']
        lalpurja_keywords = ['जग्गाधनी', 'लालपुर्जा', 'कित्ता', 'जग्गा', 'जमिन', 'land owner', 
                        'मालपोत', 'स्वामीको नाम', 'ब्यहोरा', 'rajshima']
        tax_keywords = ['कर चुक्ता', 'tax clearance', 'पान नं', 'pan no', 'आय कर']
        cit_score = sum(1 for k in citizenship_keywords if k in text_lower)
        lal_score = sum(1 for k in lalpurja_keywords if k in text_lower)
        tax_score = sum(1 for k in tax_keywords if k in text_lower)

        # print(f"Detection scores - Citizenship: {cit_score}, Lalpurja: {lal_score}, Tax: {tax_score}")
    
        scores = {
        "citizenship": cit_score,
        "lalpurja": lal_score,
        "tax_clearance": tax_score
    }
    
        detected = max(scores, key=scores.get)
        return detected if scores[detected] > 0 else "unknown"

def parse_documents(image_paths: List[str], document_types: List[str] = None, debug: bool = False) -> Dict:
    """
    Process multiple documents from CMD, extract citizenship from any doc,
    prioritize tax clearance for financial features.
    Returns single merged output for Scoring Agent.
    """
    
    if document_types is None:
        document_types = ["auto"] * len(image_paths)
    
    # Normalize types
    normalized_types = []
    for dt in document_types:
        dt_lower = dt.lower()
        if dt_lower in ["tax", "tax_clearance"]:
            normalized_types.append("tax_clearance")
        elif dt_lower in ["cit", "citizenship"]:
            normalized_types.append("citizenship")
        elif dt_lower in ["lalpurja", "land", "malpot"]:
            normalized_types.append("lalpurja")
        else:
            normalized_types.append(dt)
    
    # Storage for extracted data
    citizenship_from_cit = None
    citizenship_from_lal = None
    citizenship_from_tax = None
    all_citizenship_numbers = []  # Track all for mismatch detection
    tax_result = None
    
    # Process all documents
    for idx, (image_path, doc_type) in enumerate(zip(image_paths, normalized_types)):
        raw_text = run_ocr(image_path)
        if raw_text.startswith("OCR_ERROR"):
            continue
        
        # Auto-detect if needed
        if doc_type == "auto":
            doc_type = detect_document_type(raw_text)
        
        # Extract based on type
        if doc_type == "citizenship":
            result = extract_citizenship_fields(raw_text)
            extracted = result.get("extracted_fields", {})
            cit_num = extracted.get("citizenship_number")
            if cit_num:
                citizenship_from_cit = cit_num
                all_citizenship_numbers.append(("citizenship", cit_num))
                
        elif doc_type == "tax_clearance":
            result = extract_tax_clearance_fields(raw_text)
            extracted = result.get("extracted_fields", {})
            
            cit_num = extracted.get("citizenship_number")
            if cit_num:
                citizenship_from_tax = cit_num
                all_citizenship_numbers.append(("tax_clearance", cit_num))
            
            tax_result = result
            
        elif doc_type == "lalpurja":
            result = extract_lalpurja_fields(raw_text)
            extracted = result.get("extracted_fields", {})
            cit_num = extracted.get("citizenship_number")
            if cit_num:
                citizenship_from_lal = cit_num
                all_citizenship_numbers.append(("lalpurja", cit_num))
    
    # Priority: tax clearance > citizenship doc > lalpurja
    citizenship_number = citizenship_from_tax or citizenship_from_cit or citizenship_from_lal
    
    # Check for citizenship number mismatches
    unique_cit_nums = set([num for _, num in all_citizenship_numbers])
    mismatch_flag = len(unique_cit_nums) > 1
    
    # Parse amount helper (FIXED for colon)
    def parse_amount(amount_str):
        if not amount_str:
            return None
        cleaned = str(amount_str)
        cleaned = cleaned.replace("रू.", "").replace("Rs.", "").replace("रु", "")
        cleaned = cleaned.replace(":", ".")  # FIX: colon to dot
        cleaned = cleaned.replace(",", "")  # Remove thousands separator
        cleaned = cleaned.strip()
        
        try:
            return float(cleaned)
        except:
            return None
    
    # Extract from tax_result
    if tax_result:
        extracted = tax_result.get("extracted_fields", {})
        annual_income = parse_amount(extracted.get("total_income_amount"))
        tax_paid = parse_amount(extracted.get("tax_paid_amount"))
    else:
        annual_income = None
        tax_paid = None
    
    # Calculate effective tax rate safely
    effective_tax_rate = None
    if annual_income and annual_income > 0 and tax_paid is not None:
        effective_tax_rate = round(tax_paid / annual_income, 5)
    
    # Build flags
    flags = []
    if mismatch_flag:
        flags.append("citizenship_mismatch_across_documents")
    if not tax_paid:
        flags.append("tax_paid_not_found")
    
    return {
        "citizenship_number": citizenship_number,
        "agent_source": "document",
        "features": {
            "doc_annual_income": annual_income,
            "doc_monthly_income": round(annual_income / 12, 2) if annual_income else None,
            "tax_compliance_flag": 1 if tax_paid and tax_paid > 0 else 0,
            "tax_paid_amount": tax_paid,
            "effective_tax_rate": effective_tax_rate
        },
        "flags": flags,
        "all_citizenship_numbers_found": all_citizenship_numbers if mismatch_flag else None
    }


if __name__ == "__main__":
    import sys
    import json
    
    # Check if files provided
    if len(sys.argv) < 2:
        print("Usage: python parser_agent.py <image_path1> [type1] <image_path2> [type2] ...")
        print("Types: citizenship, lalpurja, tax_clearance, auto")
        print("Example: python parser_agent.py cit.jpg citizenship lal.jpg lalpurja tax.jpg tax_clearance")
        sys.exit(1)
    
    # Parse arguments: file1 type1 file2 type2 ...
    image_paths = []
    document_types = []
    
    i = 1
    while i < len(sys.argv):
        image_paths.append(sys.argv[i])
        # Check if next arg is a type
        if i + 1 < len(sys.argv) and sys.argv[i + 1] in ["citizenship", "lalpurja", "tax_clearance", "auto"]:
            document_types.append(sys.argv[i + 1])
            i += 2
        else:
            document_types.append("auto")
            i += 1
    
    # Process all documents, get single merged output
    result = parse_documents(image_paths, document_types)
    
    # Print ONLY final JSON
    print(json.dumps(result, indent=2, ensure_ascii=False))


    










    

