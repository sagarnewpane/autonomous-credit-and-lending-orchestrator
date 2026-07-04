"""
Test script for POST /api/v1/loan/apply
Usage:
  1. Set ACCESS_TOKEN below (from login response)
  2. Run: python scripts/test_apply.py
"""

import io
import requests

# ──────────────────────────────────────────────
# SET YOUR ACCESS TOKEN HERE
# ──────────────────────────────────────────────
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzIiwiZW1haWwiOiJzYWdhckB1c2VyLmNvbSIsImlzX2FkbWluIjpmYWxzZSwiYXBwbGljYW50X2lkIjoiQVAtMDA0MzU0IiwidHlwZSI6ImFjY2VzcyIsImlhdCI6MTc4Mjk4MzQwOCwiZXhwIjoxNzgyOTg1MjA4fQ.__RkSky3Fa7cOlKfOWtqr16gxtQWJPTgn5Qb8mLkm7A"

BASE_URL = "http://localhost:8000"


def make_dummy_pdf(filename: str, content: bytes = None) -> io.BytesIO:
    """Create a minimal valid PDF in memory."""
    if content is None:
        content = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
            b"xref\n0 4\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\n"
            b"startxref\n190\n%%EOF"
        )
    buf = io.BytesIO(content)
    buf.name = filename
    return buf


def test_apply():
    url = f"{BASE_URL}/api/v1/loan/apply"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }

    # ── Form fields ──────────────────────────────────────
    data = {
        # General Information
        "full_name": "Ram Bahadur Thapa",
        "citizenship_number": "045-076-12345",
        "phone_primary": "9841234567",
        "gender": "Male",
        "dob_ad": "1990-05-15",
        "dob_bs": "2047-01-31",
        "father_name": "Shyam Bahadur Thapa",
        "grandfather_name": "Hari Bahadur Thapa",
        "marital_status": "Married",
        "declared_occupation": "Farmer",
        "education_level": "Secondary",
        "household_size": 5,
        "declared_monthly_income": 35000,
        "primary_bank": "Rastriya Banijya Bank",
        "has_esewa_account": "true",
        "has_khalti_account": "false",
        "remittance_receiving": "false",
        "cooperative_member": "false",
        "cooperative_id": "",
        "land_area_ropani": "2.5",

        # Loan Requirements
        "loan_amount": 500000,
        "loan_purpose": "agricultural_input",
        "tenure_months": 12,
        "collateral_type": "none",
        "collateral_value_nrs": 0,
        "existing_loan_count": 0,
    }

    # ── Required files ───────────────────────────────────
    files = {
        "citizenship_doc": ("citizenship.pdf", make_dummy_pdf("citizenship.pdf"), "application/pdf"),
        "kyc_form_doc": ("kyc_form.pdf", make_dummy_pdf("kyc_form.pdf"), "application/pdf"),
    }

    print(f"POST {url}")
    print(f"Token: {ACCESS_TOKEN[:20]}...")
    print()

    resp = requests.post(url, headers=headers, data=data, files=files, timeout=60)

    print(f"Status: {resp.status_code}")
    print(f"Response:")
    try:
        print(resp.json())
    except Exception:
        print(resp.text)


if __name__ == "__main__":
    test_apply()
