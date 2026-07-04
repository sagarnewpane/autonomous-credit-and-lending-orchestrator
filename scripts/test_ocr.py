"""
Standalone Test Script — Uses parser_agent.py directly
=========================================================
Runs the ACTUAL parse_single_document() function from your parser_agent.py
(Chandra-OCR-2 + Gemma pipeline) against one image and reports timing +
extraction quality.

USAGE:
    1. Edit IMAGE_PATH and DOC_TYPE below.
    2. Run: python test_ocr_pipeline.py

    Or pass them as CLI args:
    python test_ocr_pipeline.py /path/to/image.jpg lalpurja

NOTE: Adjust the import below to match wherever parser_agent.py actually
lives in your project (e.g. `from app.agents.parser_agent import ...`).
Place this script in the same directory as parser_agent.py, or add that
directory to your PYTHONPATH, for the import to resolve.
"""

import sys
import time
import json
from pathlib import Path

# Add project root to sys.path so `app` module is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# IMPORT YOUR ACTUAL PARSER AGENT
# Adjust this path to match your project structure.
# e.g. if parser_agent.py is in app/agents/, use:
#   from app.agents.parser_agent import parse_single_document, parse_documents
# ---------------------------------------------------------------------------
from app.agents.parser_agent import parse_single_document

# ============================================================================
# CONFIG — edit these or pass as CLI args
# ============================================================================

IMAGE_PATH = "/Users/sagarnewpane/autonomous-credit-and-lending-orchestrator/data/front.jpeg"
DOC_TYPE = "citizenship_certificate"  # options: citizenship_certificate, lalpurja, kyc_form,
                                       #          utility_bill, remittance_receipt

VALID_DOC_TYPES = {
    "citizenship_certificate", "lalpurja", "kyc_form",
    "utility_bill", "remittance_receipt", "cooperative_passbook"
}

# ============================================================================
# MAIN
# ============================================================================

def main():
    image_path = IMAGE_PATH
    doc_type = DOC_TYPE

    if len(sys.argv) >= 2:
        image_path = sys.argv[1]
    if len(sys.argv) >= 3:
        doc_type = sys.argv[2]

    if not Path(image_path).exists():
        print(f"❌ File not found: {image_path}")
        sys.exit(1)

    if doc_type not in VALID_DOC_TYPES:
        print(f"❌ Unknown doc_type '{doc_type}'. Options: {sorted(VALID_DOC_TYPES)}")
        sys.exit(1)

    print("=" * 70)
    print("TESTING parser_agent.py")
    print(f"  Image:    {image_path}")
    print(f"  Doc type: {doc_type}")
    print("=" * 70)

    start = time.time()
    result = parse_single_document(doc_type, image_path, debug=True)
    elapsed = time.time() - start

    print(f"\n✅ parse_single_document() completed in {elapsed:.2f}s")

    print("\n--- Raw OCR Text (first 1000 chars) ---")
    raw_text = result.get("raw_ocr_text", "")
    print(raw_text[:1000] + ("..." if len(raw_text) > 1000 else ""))
    print("-----------------------------------------")

    extracted = result.get("extracted_fields", {})
    filled = sum(1 for v in extracted.values() if v not in (None, "", {}))
    total = len(extracted) if extracted else 0

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  OCR engine:       {result.get('ocr_engine')}")
    print(f"  Document type:    {result.get('document_type')}")
    print(f"  Status:           {result.get('status')}")
    print(f"  Confidence score: {result.get('confidence_score')}")
    print(f"  Fields filled:    {filled}/{total}")
    print(f"  Flags:            {result.get('flags')}")
    print(f"  Total time:       {elapsed:.2f}s")
    print("=" * 70)

    print("\nExtracted fields:")
    print(json.dumps(extracted, indent=2, ensure_ascii=False))

    # Save full result for inspection
    output_path = Path(image_path).stem + f"_{doc_type}_test_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "image_path": image_path,
            "doc_type": doc_type,
            "elapsed_seconds": round(elapsed, 2),
            "result": result,
        }, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Full result saved to: {output_path}")


if __name__ == "__main__":
    main()