#!/usr/bin/env python3
"""
Test script for POST /api/v1/loan/apply endpoint.

Usage:
    python scripts/test_apply_endpoint.py
    python scripts/test_apply_endpoint.py --server http://localhost:8000
    python scripts/test_apply_endpoint.py --citizenship data/front.jpeg --lalpurja data/lalpurja.jpeg
"""

import argparse
import json
import sys
from pathlib import Path

import requests

DEFAULT_SERVER = "http://localhost:8000"
ENDPOINT = "/api/v1/loan/apply"

# Default form fields (profile + loan data sent by frontend)
DEFAULT_PAYLOAD = {
    "full_name": "Ram Bahadur Thapa",
    "citizenship_number": "045-076-12345",
    "declared_occupation": "Farmer",
    "household_size": 5,
    "declared_monthly_income": 45000.0,
    "loan_amount": 500000.0,
    "loan_purpose": "agricultural_input",
    "tenure_months": 24,
    "collateral_type": "land",
    "collateral_value_nrs": 2000000.0,
    "existing_loan_count": 1,
}

# Default document paths (relative to project root)
DEFAULT_DOCS = {
    "citizenship_doc": "data/front.jpeg",
    "kyc_form_doc": "data/samples/kyc.png",
    "utility_bill": "data/samples/kyc.png",
    "bank_statement": "data/samples/kyc.png",
    "lalpurja_doc": "data/lalpurja.jpeg",
    "cooperative_records": None,
    "remittance_receipt": None,
}


def run_test(server: str, payload: dict, docs: dict, verbose: bool = False):
    url = f"{server}{ENDPOINT}"

    # Build multipart form data
    form_data = {}
    for key, value in payload.items():
        form_data[key] = (None, str(value))

    # Attach files
    files = {}
    missing = []
    for field, path in docs.items():
        if path is None:
            continue
        p = Path(path)
        if p.exists():
            files[field] = (p.name, open(p, "rb"), "application/octet-stream")
        else:
            missing.append(f"{field}: {path}")

    if missing:
        print(f"Missing files: {', '.join(missing)}")
        print("Available sample documents:")
        for sample in Path("data").rglob("*"):
            if sample.is_file() and sample.suffix.lower() in (".jpg", ".jpeg", ".png"):
                print(f"  {sample}")
        sys.exit(1)

    print(f"POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print(f"Files: {', '.join(f'{k}={v[0]}' for k, v in files.items())}")
    print("-" * 60)

    try:
        resp = requests.post(url, data=form_data, files=files, timeout=300)
    except requests.ConnectionError:
        print(f"\nERROR: Cannot connect to {server}. Is the server running?")
        print(f"Start it with: uvicorn app.main:app --reload")
        sys.exit(1)
    finally:
        for f in files.values():
            f[1].close()

    print(f"Status: {resp.status_code}")
    print("-" * 60)

    try:
        body = resp.json()
    except ValueError:
        print(resp.text)
        return

    print(json.dumps(body, indent=2, ensure_ascii=False))

    if verbose and "pipeline_error" not in body:
        print("\n--- Decision Summary ---")
        print(f"  Decision:      {body.get('final_decision', 'N/A')}")
        print(f"  Credit Score:  {body.get('credit_score', 'N/A')}")
        print(f"  Approved Amt:  {body.get('approved_amount', 'N/A')}")
        print(f"  Interest Tier: {body.get('interest_tier', 'N/A')}")
        print(f"  Reason:        {body.get('decision_reason', 'N/A')}")

    return body


def main():
    parser = argparse.ArgumentParser(description="Test loan apply endpoint")
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"Server URL (default: {DEFAULT_SERVER})")
    # General Information
    parser.add_argument("--full-name", default=DEFAULT_PAYLOAD["full_name"], help="Full name (English)")
    parser.add_argument("--citizenship-no", default=DEFAULT_PAYLOAD["citizenship_number"], help="Citizenship number (DDD-DDD-DDDDD)")
    parser.add_argument("--occupation", default=DEFAULT_PAYLOAD["declared_occupation"], help="Occupation")
    parser.add_argument("--household-size", type=int, default=DEFAULT_PAYLOAD["household_size"], help="Household size (1-8)")
    parser.add_argument("--monthly-income", type=float, default=DEFAULT_PAYLOAD["declared_monthly_income"], help="Declared monthly income (NRs)")
    # Loan Requirements
    parser.add_argument("--amount", type=float, default=DEFAULT_PAYLOAD["loan_amount"], help="Loan amount in NPR")
    parser.add_argument("--purpose", default=DEFAULT_PAYLOAD["loan_purpose"], help="Loan purpose")
    parser.add_argument("--tenure", type=int, default=DEFAULT_PAYLOAD["tenure_months"], help="Tenure in months")
    # Documents
    parser.add_argument("--citizenship-doc", default=DEFAULT_DOCS["citizenship_doc"], help="Citizenship document path")
    parser.add_argument("--kyc-form", default=DEFAULT_DOCS["kyc_form_doc"], help="KYC form image path")
    parser.add_argument("--utility-bill", default=DEFAULT_DOCS["utility_bill"], help="Utility bill (NEA/Ncell) image path")
    parser.add_argument("--bank-statement", default=DEFAULT_DOCS["bank_statement"], help="Bank statement / Mobile wallet CSV path")
    parser.add_argument("--lalpurja", default=DEFAULT_DOCS["lalpurja_doc"], help="Lalpurja document path")
    parser.add_argument("--cooperative", default=None, help="Cooperative passbook path")
    parser.add_argument("--remittance", default=None, help="Remittance receipt path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print decision summary")
    args = parser.parse_args()

    payload = {
        "full_name": args.full_name,
        "citizenship_number": args.citizenship_no,
        "declared_occupation": args.occupation,
        "household_size": args.household_size,
        "declared_monthly_income": args.monthly_income,
        "loan_amount": args.amount,
        "loan_purpose": args.purpose,
        "tenure_months": args.tenure,
        "collateral_type": DEFAULT_PAYLOAD["collateral_type"],
        "collateral_value_nrs": DEFAULT_PAYLOAD["collateral_value_nrs"],
        "existing_loan_count": DEFAULT_PAYLOAD["existing_loan_count"],
    }

    docs = {
        "citizenship_doc": args.citizenship_doc,
        "kyc_form_doc": args.kyc_form,
        "utility_bill": args.utility_bill,
        "bank_statement": args.bank_statement,
        "lalpurja_doc": args.lalpurja,
        "cooperative_records": args.cooperative,
        "remittance_receipt": args.remittance,
    }

    run_test(args.server, payload, docs, verbose=args.verbose)


if __name__ == "__main__":
    main()
