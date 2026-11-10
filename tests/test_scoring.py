from pathlib import Path

import pytest

MODEL = Path(__file__).resolve().parents[1] / "app" / "ScoringModel" / "pd_model" / "model.json"
pytestmark = pytest.mark.skipif(not MODEL.exists(), reason="PD model not trained (run experiments/e2_outcome_model.py)")


@pytest.fixture(scope="module")
def scorer():
    from app.agents.score_agent import CreditScorer
    return CreditScorer()


ROW = {
    "requested_amount_nrs": 150000.0, "requested_tenure_months": 24.0, "collateral_value_nrs": 400000.0,
    "collateral_coverage": 2.67, "existing_loan_count": 0.0, "household_size": 5.0, "land_area_ropani": 4.0,
    "monthly_income_est": 25000.0, "income_confidence": 0.75, "income_signal_count": 4.0,
    "remittance_monthly_avg": 15000.0, "remittance_regularity_score": 0.6, "esewa_net_monthly": -2000.0,
    "esewa_tx_count_6months": 30.0, "cooperative_monthly_sales": 0.0, "coop_tenure_years": 0.0,
    "utility_avg_bill_nrs": 500.0, "elec_on_time_rate": 0.8, "overall_on_time_rate": 0.8,
    "util_arrears_total_nrs": 0.0, "loan_to_annual_income": 0.5, "instalment_to_income": 0.29,
    "credit_bureau_score": None, "has_bureau_score": 0.0, "has_esewa_account": 1.0, "has_khalti_account": 0.0,
    "remittance_receiving": 1.0, "cooperative_member": 0.0, "loan_purpose": "small_trade",
    "collateral_type": "land", "occupation_en": "small trader", "education_level": "slc", "kyc_tier": "mid",
}


def test_model_and_spec_agree(scorer):
    assert scorer.booster.num_features() == len(scorer.features)
    assert set(scorer.spec["categories"]) <= set(scorer.features)


def test_score_is_monotone_in_pd(scorer):
    from app.agents.score_agent import pd_to_score
    scores = [pd_to_score(p, scorer.spec) for p in (0.005, 0.01, 0.02, 0.05, 0.1, 0.3)]
    assert scores == sorted(scores, reverse=True)


def test_scoring_a_row_gives_pd_and_drivers(scorer):
    out = scorer.score(ROW)
    assert 0 < out["pd"] < 1 and 300 <= out["credit_score"] <= 850
    assert out["drivers"] and all("shap_log_odds" in d for d in out["drivers"])


def test_monotone_constraint_on_affordability(scorer):
    pds = [scorer.predict_pd({**ROW, "instalment_to_income": x}) for x in (0.1, 0.3, 0.6, 1.0, 2.0)]
    assert all(b >= a - 1e-12 for a, b in zip(pds, pds[1:]))


def test_unknown_category_is_treated_as_missing(scorer):
    out = scorer.score({**ROW, "occupation_en": "astronaut"})
    assert 0 < out["pd"] < 1


def test_monotone_constraint_on_payment_record(scorer):
    pds = [scorer.predict_pd({**ROW, "overall_on_time_rate": x}) for x in (0.0, 0.3, 0.6, 0.9, 1.0)]
    assert all(b <= a + 1e-12 for a, b in zip(pds, pds[1:]))
