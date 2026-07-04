"""Test citizenship_certificate with Chandra-OCR-2 instead of Tesseract."""
import sys
import time
import json
from pathlib import Path

from app.agents.parser_agent import run_chandra_ocr, extract_citizenship_certificate_fields

IMAGE_PATH = "/Users/sagarnewpane/autonomous-credit-and-lending-orchestrator/data/front.jpeg"

def main():
    image_path = sys.argv[1] if len(sys.argv) >= 2 else IMAGE_PATH
    if not Path(image_path).exists():
        print(f"File not found: {image_path}")
        sys.exit(1)

    print("=" * 70)
    print("TESTING Chandra-OCR-2 on citizenship_certificate")
    print(f"  Image: {image_path}")
    print("=" * 70)

    start = time.time()
    raw_text, rotated, angle = run_chandra_ocr(image_path)
    ocr_time = time.time() - start
    print(f"\nChandra-OCR-2 completed in {ocr_time:.2f}s")

    print("\n--- Raw OCR Text (first 2000 chars) ---")
    print(raw_text[:2000] + ("..." if len(raw_text) > 2000 else ""))
    print("-----------------------------------------")

    start2 = time.time()
    result = extract_citizenship_certificate_fields(raw_text)
    extract_time = time.time() - start2

    print(f"\nField extraction completed in {extract_time:.2f}s")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  OCR engine:       chandra_ocr")
    print(f"  Document type:    citizenship_certificate")
    print(f"  Status:           {result.get('status')}")
    print(f"  Confidence score: {result.get('confidence_score')}")
    filled = sum(1 for v in result.get("extracted_fields", {}).values() if v not in (None, "", {}))
    total = len(result.get("extracted_fields", {}))
    print(f"  Fields filled:    {filled}/{total}")
    print(f"  Flags:            {result.get('flags')}")
    print(f"  Total time:       {ocr_time + extract_time:.2f}s")
    print("=" * 70)

    print("\nExtracted fields:")
    print(json.dumps(result.get("extracted_fields", {}), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
