
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
        
        print(f"Cleaned LLM output:\n{llm_output}\n{'='*50}")
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
    
    prompt = f"""You are parsing a Nepali Lalpurja (Land Ownership Certificate).
    
OCR extracted this text:

---OCR TEXT---
{raw_text}
---END---

The field labels in Nepali mean:
- "जग्गाधनी" or "Owner" = land owner's name
- "कित्ता नं." or "Plot No" = plot/kitta number
- "क्षेत्रफल" or "Area" = land area (in Ropani/Aana or Bigaha/Kattha/Dhur)
- "जिल्ला" or "District" = district
- "गा.पा." or "VDC/Municipality" = local body
- "वडा नं." or "Ward No" = ward number
- "साबिक ठेगाना" or "Old Address" = previous address

Extract these fields and return ONLY valid JSON:
{{
  "owner_name": "owner's full name",
  "plot_number": "kitta/plot number",
  "land_area": "area with unit like '5-3-2 Ropani' or '10 Bigaha'",
  "district": "district name",
  "municipality": "VDC or municipality name",
  "ward_number": "ward number",
  "old_address": "old/sabik address if found"
}}

Rules:
- Convert Nepali numbers to English if needed
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
                "owner_name": None,
                "plot_number": None,
                "land_area": None,
                "district": None,
                "municipality": None,
                "ward_number": None,
                "old_address": None
            }
        
        filled = sum(1 for v in extracted.values() if v is not None)
        confidence = filled / 7
        
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





def detect_document_type(raw_text: str) -> str:
        text_lower = raw_text.lower()
        citizenship_keywords = ['नागरिकता', 'citizenship', 'जन्म मिति', 'नागरिकता प्रमाणपत्र']
        lalpurja_keywords = ['जग्गाधनी', 'लालपुर्जा', 'कित्ता', 'जग्गा', 'जमिन', 'land owner']
        tax_keywords = ['कर चुक्ता', 'tax clearance', 'पान नं', 'pan no', 'आय कर']
        cit_score = sum(1 for k in citizenship_keywords if k in text_lower)
        lal_score = sum(1 for k in lalpurja_keywords if k in text_lower)
        tax_score = sum(1 for k in tax_keywords if k in text_lower)
    
        scores = {
        "citizenship": cit_score,
        "lalpurja": lal_score,
        "tax_clearance": tax_score
    }
    
        detected = max(scores, key=scores.get)
        return detected if scores[detected] > 0 else "unknown"

def parse_document(image_path: str, document_type: str="auto") -> Dict:
    # step 1 - run ocr
    raw_text=run_ocr(image_path)
    if raw_text.startswith("OCR_ERROR"):
        return {
            "document_type": document_type,
            "status": "failed",
            "confidence_score": 0.0,
            "extracted_fields": {},
            "flags": ["ocr_failed"],
            "raw_ocr_text": raw_text,
            "error": raw_text
        }
    

    
    #step 2 auto detect document
    if document_type == "auto":
        document_type = detect_document_type(raw_text)

    #step 3 - route to extractor
    if document_type == "citizenship":
        result = extract_citizenship_fields(raw_text)
    elif document_type == "lalpurja":
        #result = extract_lalpurja_fields(raw_text)  # We'll build this next
    #elif document_type == "tax_clearance":
        #result = extract_tax_clearance_fields(raw_text)  # We'll build this next
    else:
        return {
            "document_type": "unknown",
            "status": "failed",
            "confidence_score": 0.0,
            "extracted_fields": {},
            "flags": ["unknown_document_type"],
            "raw_ocr_text": raw_text
        }
    
    #step 4 - metadata
    result["image_path"] = image_path
    result["processing_timestamp"] = __import__('datetime').datetime.now().isoformat()
    
    return result



if __name__=="__main__":
    import sys
    import json
    if len(sys.argv) > 1:
        image_file = sys.argv[1]
        doc_type = sys.argv[2] if len(sys.argv) > 2 else "auto"
        
        print(f"Processing: {image_file}")
        print(f"Document type: {doc_type}")
        print("=" * 60)
        
        result = parse_document(image_file, doc_type)
        
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Usage: python parser_agent.py <image_path> [document_type]")
        print("Document types: citizenship, lalpurja, tax_clearance, auto")


    










    

