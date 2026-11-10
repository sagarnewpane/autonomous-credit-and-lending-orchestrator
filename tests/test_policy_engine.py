import math

import pytest

from app.services.policy_engine import evaluate, load_policy, max_principal_for_instalment, monthly_instalment

BASE = {
    "requested_amount_nrs": 80000, "requested_tenure_months": 24, "collateral_value_nrs": 0,
    "loan_purpose": "small_trade", "existing_liabilities_monthly": 0, "existing_loan_count": 0,
    "kyc_tier": "basic", "nrb_blacklist_flag": False, "aml_flag": False, "monthly_income": 40000,
    "imr": None, "imr_status": "not_declared", "remittance_share": 0.0,
}


def run(**kw):
    return evaluate({**BASE, **kw}, load_policy())


def triggered(res):
    return set(res["triggered_rules"])


def test_clean_application_passes():
    res = run()
    assert res["status"] == "pass" and not res["triggered_rules"]


def test_missing_kyc_tier_is_treated_as_basic_not_zero():
    # Regression: an unset tier used to map to a limit of 0 and flag every application.
    assert "KYC_TIER_LIMIT" not in triggered(run(kyc_tier=None, requested_amount_nrs=5000))
    assert "KYC_TIER_LIMIT" in triggered(run(kyc_tier=None, requested_amount_nrs=150000))
    assert "KYC_TIER_LIMIT" not in triggered(run(kyc_tier="full", requested_amount_nrs=900000, collateral_value_nrs=1e6))


def test_blacklist_vetoes_and_aml_refers():
    assert run(nrb_blacklist_flag=True)["status"] == "veto"
    assert run(aml_flag="true")["status"] == "refer"


def test_unscreened_fields_are_referred_not_passed():
    res = run(nrb_blacklist_flag=None, aml_flag=None)
    assert set(res["not_screened"]) == {"BLACKLIST", "AML_SCREEN"}
    assert res["status"] == "refer"
    traces = {t["rule_id"]: t for t in res["rule_traces"]}
    assert traces["BLACKLIST"]["action"] == "refer" and traces["BLACKLIST"]["note"] == "not screened"


def test_collateral_and_agri_rules():
    assert "COLLATERAL_REQUIRED" in triggered(run(kyc_tier="full", requested_amount_nrs=600000))
    res = run(loan_purpose="livestock_purchase", requested_amount_nrs=90000, monthly_income=2000)
    assert "AGRI_LOAN_TO_INCOME" in triggered(res)
    assert "AGRI_LOAN_TO_INCOME" not in triggered(run(loan_purpose="education", requested_amount_nrs=90000, monthly_income=2000))


def test_dsti_cap():
    res = run(kyc_tier="mid", requested_amount_nrs=400000, monthly_income=20000, requested_tenure_months=24)
    trace = next(t for t in res["rule_traces"] if t["rule_id"] == "DSTI_CAP")
    assert trace["triggered"] and trace["observed"] > 0.5
    assert res["status"] == "refer"


def test_imr_band_and_remittance_relaxation():
    assert "INCOME_MISMATCH" in triggered(run(imr=3.5))
    assert "INCOME_MISMATCH" in triggered(run(imr=0.2))
    assert "INCOME_MISMATCH" not in triggered(run(imr=1.1))
    assert "INCOME_MISMATCH" not in triggered(run(imr=4.0, remittance_share=0.8))
    res = run(imr=None, imr_status="insufficient_observed")
    trace = next(t for t in res["rule_traces"] if t["rule_id"] == "INCOME_MISMATCH")
    assert not trace["applicable"] and not trace["triggered"]


def test_policy_version_is_a_hash_and_rules_have_provenance():
    pol = load_policy()
    assert len(pol["policy_version"]) == 12
    for r in pol["rules"]:
        assert r.get("provenance") and r.get("source") and r.get("source_status")


@pytest.mark.parametrize("principal,rate,months", [(100000, 0.14, 12), (250000, 0.12, 36), (50000, 0.0, 10)])
def test_instalment_round_trip(principal, rate, months):
    emi = monthly_instalment(principal, rate, months)
    assert math.isclose(max_principal_for_instalment(emi, rate, months), principal, rel_tol=1e-9)
