from app.agents.decision_agent import decide
from app.services.policy_engine import load_policy, monthly_instalment


def state(**kw):
    s = {"loan_request": {"amount": 100000, "tenure_months": 24, "existing_liabilities_monthly": 0},
         "income_agent_monthly_est": 40000, "income_confidence": 0.8, "compliance_status": "pass",
         "compliance_flags": [], "compliance_message": None,
         "scorecard": {"status": "ok", "pd": 0.01, "risk_grade": "B", "credit_score": 640}}
    s.update(kw)
    return s


def test_low_pd_clean_file_is_approved():
    assert decide(state())["final_decision"] == "approve"


def test_veto_declines_and_is_the_only_decline_path():
    assert decide(state(compliance_status="veto", compliance_flags=["BLACKLIST"]))["final_decision"] == "decline"
    high_pd = state(scorecard={"status": "ok", "pd": 0.4, "risk_grade": "E"})
    assert decide(high_pd)["final_decision"] == "refer"


def test_thin_file_is_referred_not_rejected():
    # Regression: income confidence below 0.40 used to be an automatic rejection.
    out = decide(state(income_confidence=0.2))
    assert out["final_decision"] == "refer"
    assert any("Thin file" in r for r in out["decision_reasons"])


def test_flag_turns_approval_into_conditional():
    out = decide(state(compliance_status="flag", compliance_flags=["EXISTING_LOANS"]))
    assert out["final_decision"] == "conditional"
    assert out["approved_amount_nrs"] == 85000


def test_score_unavailable_routes_to_review():
    assert decide(state(scorecard={"status": "error", "pd": None}))["final_decision"] == "refer"


def test_dsti_breach_gets_an_affordable_counter_offer():
    s = state(loan_request={"amount": 500000, "tenure_months": 24, "existing_liabilities_monthly": 2000},
              income_agent_monthly_est=20000, compliance_status="refer", compliance_flags=["DSTI_CAP"])
    out = decide(s)
    offer = out["counter_offer"]
    assert out["final_decision"] == "refer" and offer
    rate = load_policy()["assumptions"]["annual_interest_rate_for_affordability"]
    assert monthly_instalment(offer["max_amount_at_requested_tenure"], rate, 24) + 2000 <= 0.5 * 20000 + 1e-6
