"""
=====================================================================
Test Script for Unified Document Parsing Agent
=====================================================================
Tests all supported document types and outputs results to a JSON file.

Supported doc_types:
    - citizenship_certificate
    - lalpurja
    - kyc_form
    - utility_bill
    - remittance_receipt
    - cooperative_passbook
"""

import sys
from pathlib import Path

# Add project root to sys.path so `app` module is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import time
import traceback
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path

from app.agents.parser_agent import parse_single_document, parse_documents

# =====================================================================
# DOCUMENT PATH VARIABLES
# =====================================================================

DATA_DIR = Path("/Users/sagarnewpane/autonomous-credit-and-lending-orchestrator/data")

# Citizenship uses both front and back images combined
CITIZENSHIP_FRONT_PATH = str(DATA_DIR / "front.jpeg")
CITIZENSHIP_BACK_PATH  = str(DATA_DIR / "samples" / "back2.jpeg")

COMBINED_CITIZENSHIP_DIR = Path("/Users/sagarnewpane/autonomous-credit-and-lending-orchestrator/ocr_output/combined")
COMBINED_CITIZENSHIP_DIR.mkdir(parents=True, exist_ok=True)

# Legacy combined image (for backward compatibility)
CITIZENSHIP_PATH = str(COMBINED_CITIZENSHIP_DIR / "citizenship_front_back_combined.jpeg")

def combine_front_back(front_path: str, back_path: str, output_path: str) -> str:
    """Stack front and back images vertically into a single combined image."""
    front = cv2.imread(front_path)
    back = cv2.imread(back_path)
    if front is None or back is None:
        raise FileNotFoundError(f"Could not read images: front={front_path}, back={back_path}")

    target_w = max(front.shape[1], back.shape[1])

    def resize_to_width(img, target_w):
        h, w = img.shape[:2]
        if w == target_w:
            return img
        scale = target_w / w
        return cv2.resize(img, (target_w, int(h * scale)), interpolation=cv2.INTER_AREA)

    front_resized = resize_to_width(front, target_w)
    back_resized = resize_to_width(back, target_w)

    combined = np.vstack([front_resized, back_resized])
    cv2.imwrite(output_path, combined)
    print(f"  Combined front+back: {combined.shape[1]}x{combined.shape[0]} -> {output_path}")
    return output_path

# Build citizenship paths - prefer list-based approach for multi-image OCR
CITIZENSHIP_LIST_PATHS = []
if Path(CITIZENSHIP_FRONT_PATH).exists():
    CITIZENSHIP_LIST_PATHS.append(CITIZENSHIP_FRONT_PATH)
if Path(CITIZENSHIP_BACK_PATH).exists():
    CITIZENSHIP_LIST_PATHS.append(CITIZENSHIP_BACK_PATH)

# Fallback: combine into single image if only one exists or for legacy single-image mode
if Path(CITIZENSHIP_FRONT_PATH).exists() and Path(CITIZENSHIP_BACK_PATH).exists():
    combine_front_back(CITIZENSHIP_FRONT_PATH, CITIZENSHIP_BACK_PATH, CITIZENSHIP_PATH)
elif Path(CITIZENSHIP_FRONT_PATH).exists():
    CITIZENSHIP_PATH = CITIZENSHIP_FRONT_PATH

LALPURJA_PATH           = str(DATA_DIR / "lalpurja.jpeg")
KYC_FORM_PATH           = str(DATA_DIR / "samples" / "kyc.png")
UTILITY_BILL_PATH       = str(DATA_DIR / "samples" / "electricity.png")
REMITTANCE_RECEIPT_PATH = None
COOPERATIVE_PASSBOOK_PATH = None

OUTPUT_DIR  = Path("/Users/sagarnewpane/autonomous-credit-and-lending-orchestrator/ocr_output/test_results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TIMESTAMP   = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = OUTPUT_DIR / f"doc_parsing_test_results_{TIMESTAMP}.json"

DEBUG_MODE  = True
APPLICANT_ID = "TEST-APPLICANT-001"

# =====================================================================
# Build doc -> path mapping
# =====================================================================

def _exists(p):
    if isinstance(p, list):
        return len(p) > 0
    return bool(p) and Path(p).exists()

DOC_PATHS = {
    "citizenship_certificate": CITIZENSHIP_LIST_PATHS if CITIZENSHIP_LIST_PATHS else CITIZENSHIP_PATH,
    "lalpurja":                LALPURJA_PATH,
    "kyc_form":                KYC_FORM_PATH,
    "utility_bill":            UTILITY_BILL_PATH,
    "remittance_receipt":      REMITTANCE_RECEIPT_PATH,
    "cooperative_passbook":    COOPERATIVE_PASSBOOK_PATH,
}

AVAILABLE_DOCS = {k: v for k, v in DOC_PATHS.items() if _exists(v)}
MISSING_DOCS   = [k for k, v in DOC_PATHS.items() if not _exists(v)]

# =====================================================================
# Per-document test runner
# =====================================================================

def test_single_doc(doc_type: str, image_path) -> dict:
    test_entry = {
        "doc_type": doc_type,
        "image_path": image_path,
        "status": "pending",
        "elapsed_seconds": None,
        "error": None,
        "result": None,
    }
    t0 = time.time()
    try:
        # Support list of images (e.g., citizenship front + back)
        if isinstance(image_path, list):
            result = parse_documents(
                file_paths={doc_type: image_path},
                debug=DEBUG_MODE,
                applicant_id=APPLICANT_ID,
            )
            result = result.get("raw_extracted_data", {}).get(doc_type, {})
        else:
            result = parse_single_document(
                doc_type=doc_type,
                image_path=image_path,
                debug=DEBUG_MODE,
                applicant_id=APPLICANT_ID,
                document_id=f"{APPLICANT_ID}-{doc_type}-{TIMESTAMP}",
            )
        test_entry["result"] = result
        test_entry["status"] = result.get("status", "completed")
    except Exception as e:
        test_entry["status"] = "exception"
        test_entry["error"]  = f"{type(e).__name__}: {e}"
        test_entry["traceback"] = traceback.format_exc()
    finally:
        test_entry["elapsed_seconds"] = round(time.time() - t0, 2)

    return test_entry

# =====================================================================
# Combined multi-doc test
# =====================================================================

def test_combined_parse(file_paths: dict) -> dict:
    combined_entry = {
        "status": "pending",
        "elapsed_seconds": None,
        "error": None,
        "result": None,
    }
    t0 = time.time()
    try:
        result = parse_documents(
            file_paths=file_paths,
            debug=DEBUG_MODE,
            applicant_id=APPLICANT_ID,
        )
        combined_entry["result"] = result
        combined_entry["status"] = "completed"
    except Exception as e:
        combined_entry["status"] = "exception"
        combined_entry["error"]  = f"{type(e).__name__}: {e}"
        combined_entry["traceback"] = traceback.format_exc()
    finally:
        combined_entry["elapsed_seconds"] = round(time.time() - t0, 2)
    return combined_entry

# =====================================================================
# Main test routine
# =====================================================================

def run_all_tests() -> dict:
    print("=" * 70)
    print(" Unified Document Parsing Agent - Test Runner")
    print("=" * 70)
    print(f" Timestamp      : {TIMESTAMP}")
    print(f" Applicant ID   : {APPLICANT_ID}")
    print(f" Debug mode     : {DEBUG_MODE}")
    print(f" Output file    : {OUTPUT_FILE}")
    print("-" * 70)
    print(f" Available docs : {len(AVAILABLE_DOCS)}")
    for k, v in AVAILABLE_DOCS.items():
        display_path = v if isinstance(v, str) else f"{len(v)} images: {v}"
        print(f"   - {k:25s} -> {display_path}")
    if MISSING_DOCS:
        print(f" Missing docs   : {len(MISSING_DOCS)}  (will be skipped)")
        for k in MISSING_DOCS:
            print(f"   - {k}")
    print("-" * 70)

    per_doc_results = {}
    for doc_type, image_path in AVAILABLE_DOCS.items():
        print(f"[TEST] {doc_type:25s} ... ", end="", flush=True)
        entry = test_single_doc(doc_type, image_path)
        per_doc_results[doc_type] = entry
        if entry["status"] in ("verified", "completed", "not_implemented"):
            emoji = "OK"
        elif entry["status"] == "low_confidence":
            emoji = "WARN"
        else:
            emoji = "FAIL"
        print(f"{emoji} status={entry['status']}  time={entry['elapsed_seconds']}s")

    combined_result = None
    if AVAILABLE_DOCS:
        print(f"[TEST] combined parse_documents() ... ", end="", flush=True)
        combined_result = test_combined_parse(AVAILABLE_DOCS)
        emoji = "OK" if combined_result["status"] == "completed" else "FAIL"
        print(f"{emoji} status={combined_result['status']}  time={combined_result['elapsed_seconds']}s")

    summary = {
        "total_doc_types_tested": len(per_doc_results),
        "verified":    sum(1 for e in per_doc_results.values() if e["status"] == "verified"),
        "low_confidence": sum(1 for e in per_doc_results.values() if e["status"] == "low_confidence"),
        "ocr_failed":  sum(1 for e in per_doc_results.values() if e["status"] == "ocr_failed"),
        "exceptions":  sum(1 for e in per_doc_results.values() if e["status"] == "exception"),
        "not_implemented": sum(1 for e in per_doc_results.values() if e["status"] == "not_implemented"),
        "other":       sum(1 for e in per_doc_results.values()
                            if e["status"] not in ("verified", "low_confidence", "ocr_failed",
                                                   "exception", "not_implemented")),
        "missing_docs_skipped": MISSING_DOCS,
        "total_elapsed_seconds": round(sum(e["elapsed_seconds"] or 0 for e in per_doc_results.values()), 2),
    }

    final_report = {
        "test_run_metadata": {
            "timestamp": TIMESTAMP,
            "applicant_id": APPLICANT_ID,
            "debug_mode": DEBUG_MODE,
            "output_file": str(OUTPUT_FILE),
        },
        "document_paths_configured": DOC_PATHS,
        "available_docs": list(AVAILABLE_DOCS.keys()),
        "missing_docs": MISSING_DOCS,
        "per_document_results": per_doc_results,
        "combined_parse_result": combined_result,
        "summary": summary,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)

    print("-" * 70)
    print(f" Results written to: {OUTPUT_FILE}")
    print(f" Summary: verified={summary['verified']}  "
          f"low_conf={summary['low_confidence']}  "
          f"ocr_failed={summary['ocr_failed']}  "
          f"exceptions={summary['exceptions']}  "
          f"not_impl={summary['not_implemented']}")
    print("=" * 70)

    return final_report


if __name__ == "__main__":
    run_all_tests()
