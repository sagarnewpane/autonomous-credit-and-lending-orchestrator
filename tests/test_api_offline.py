"""API smoke test: sign up, log in, apply and read the decision, with the file-backed data layer.

Needs no data: a new applicant has no transaction history, so the pipeline treats the file
as thin and refers it to a credit officer.
"""
import pytest

pytest.importorskip("httpx")

PASSWORD = "Sm0ke-Test-Pass!"
FORM = {
    "full_name_en": "Test Applicant", "father_name_en": "F", "grandfather_name_en": "G",
    "gender": "female", "marital_status": "Married", "citizenship_number": "12-01-75-01234",
    "dob_ad": "1990-01-01", "dob_bs": "2046-09-17", "phone_primary": "9800000000",
    "occupation_en": "Small Trader", "education_level": "SLC", "household_size": "5",
    "primary_bank": "Other", "loan_purpose": "small_trade", "requested_amount_nrs": "150000",
    "requested_tenure_months": "24", "collateral_type": "none", "collateral_value_nrs": "0",
    "declared_monthly_income": "30000", "existing_loan_amount": "0", "existing_loan_count": "0",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    from fastapi.testclient import TestClient

    from app.main import app
    return TestClient(app)


def test_apply_and_read_decision(client):
    email = "api-smoke@example.com"
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD, "full_name": "Smoke Test"})
    assert r.status_code in (200, 201), r.text
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.post("/api/v1/loan/apply", data=FORM, headers=headers)
    assert r.status_code == 200, r.text
    result = r.json()
    # No transaction history: thin file, so a credit officer reviews it rather than a rejection.
    assert result["final_decision"] == "refer"
    assert "recommendation for a credit officer" in result["message"]
    assert result["policy_version"] and result["model_version"]
    assert result["pd"] is not None and result["risk_grade"]

    r = client.get(f"/api/v1/loan/decision/{result['application_id']}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["decision"] == "refer"
