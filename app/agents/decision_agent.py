"""
Decision Agent: combines policy results, the PD estimate and income evidence into a
recommendation for a credit officer.

Outcomes (lower case, stored as such):
  decline      only when a policy rule with action "veto" fired; the model never declines
  refer        manual review: a "refer" rule fired, income evidence is thin, PD is high,
               or the score is unavailable
  conditional  low-to-moderate PD, or an approval with a "flag" rule: offered at a reduced
               amount, or at the affordable amount when the instalment check failed
  approve      low PD, no rule fired

Thresholds come from the `decision` block of config/policy_rules.yaml.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.db import db
from app.models.state import AgentState
from app.services.policy_engine import load_policy, max_principal_for_instalment, monthly_instalment

logger = logging.getLogger(__name__)


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def counter_offer(amount: float, tenure: int, income: float, existing: float, rate: float,
                  max_ratio: float, max_tenure: int) -> Optional[Dict[str, Any]]:
    """Largest affordable principal at the requested tenure, and the tenure needed for the full amount."""
    budget = max_ratio * income - existing
    if income <= 0 or budget <= 0:
        return None
    principal_same_tenure = max_principal_for_instalment(budget, rate, tenure)
    tenure_needed = None
    for months in range(int(tenure), int(max_tenure) + 1):
        if monthly_instalment(amount, rate, months) <= budget:
            tenure_needed = months
            break
    return {
        "max_amount_at_requested_tenure": int(min(amount, principal_same_tenure) // 1000 * 1000),
        "requested_tenure_months": int(tenure),
        "tenure_needed_for_full_amount": tenure_needed,
        "affordable_monthly_instalment": round(budget, 2),
        "basis": f"debt service at most {int(max_ratio * 100)}% of observed income, {rate:.0%} assumed rate",
    }


def decide(state: Dict[str, Any], policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    policy = policy or load_policy()
    cfg = policy["decision"]
    rate = float(policy.get("assumptions", {}).get("annual_interest_rate_for_affordability", 0.14))

    lr = state.get("loan_request", {}) or {}
    amount = _num(lr.get("amount"))
    tenure = int(_num(lr.get("tenure_months"), 12)) or 12
    income = _num(state.get("income_agent_monthly_est"))
    existing = _num(lr.get("existing_liabilities_monthly"))
    confidence = _num(state.get("income_confidence"))

    compliance = state.get("compliance_status", "pass")
    triggered: List[str] = state.get("compliance_flags", []) or []
    scorecard = state.get("scorecard", {}) or {}
    pd_value = scorecard.get("pd")
    reasons: List[str] = []
    offer = None

    if compliance == "veto":
        decision = "decline"
        reasons.append(state.get("compliance_message") or "Declined by a policy veto rule.")
    else:
        if scorecard.get("status") != "ok" or pd_value is None:
            decision = "refer"
            reasons.append("Score unavailable; manual review.")
        elif pd_value < cfg["pd_approve_max"]:
            decision = "approve"
            reasons.append(f"Estimated default probability {pd_value:.1%} is low.")
        elif pd_value < cfg["pd_conditional_max"]:
            decision = "conditional"
            reasons.append(f"Estimated default probability {pd_value:.1%} is moderate.")
        else:
            decision = "refer"
            reasons.append(f"Estimated default probability {pd_value:.1%} is high; manual review.")

        if confidence < cfg["min_income_confidence"]:
            decision = "refer"
            reasons.append(
                f"Thin file: income evidence confidence {confidence:.2f} is below "
                f"{cfg['min_income_confidence']:.2f}; manual review rather than decline."
            )
        if compliance == "refer":
            decision = "refer"
            reasons.append(state.get("compliance_message") or "A policy rule requires manual review.")
        elif compliance == "flag" and decision == "approve":
            decision = "conditional"
            reasons.append(state.get("compliance_message") or "A policy rule was flagged.")

        flags = state.get("income_flags") or []
        if "LOW_OBSERVED_INCOME" in flags:
            reasons.append("Observed income is below NPR 3,000 a month; much of the applicant's income may be in cash.")
        if "INCOME_ANOMALY_HIGH" in flags:
            reasons.append("Observed income is unusually high (above NPR 200,000 a month); check the records.")

        if "DSTI_CAP" in triggered:
            dsti_rule = next((r for r in policy["rules"] if r["id"] == "DSTI_CAP"), None)
            max_ratio = float(dsti_rule["params"]["max_ratio"]) if dsti_rule else 0.5
            offer = counter_offer(amount, tenure, income, existing, rate, max_ratio,
                                  int(cfg.get("counter_offer_max_tenure_months", 60)))
            if offer:
                reasons.append(
                    f"Affordable amount at {tenure} months: NPR {offer['max_amount_at_requested_tenure']:,}."
                )

    if decision == "approve":
        approved = amount
    elif decision == "conditional":
        approved = amount * float(cfg.get("conditional_amount_factor", 0.85))
        if offer:
            approved = min(approved, offer["max_amount_at_requested_tenure"])
    else:
        approved = None

    grade = scorecard.get("risk_grade")
    rate_pct = cfg.get("illustrative_rates_pct", {}).get(grade) if decision in ("approve", "conditional") else None

    return {
        "final_decision": decision,
        "approved_amount_nrs": None if approved is None else int(approved // 1000 * 1000),
        "interest_tier": grade,
        "interest_rate_pct": rate_pct,
        "decision_reason": " ".join(reasons),
        "decision_reasons": reasons,
        "counter_offer": offer,
    }


def decision_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph entry point for the Decision Agent."""
    out = decide(state)
    scorecard = state.get("scorecard", {}) or {}
    out["final_output"] = {
        "application_id": state.get("application_id"),
        "applicant_id": state.get("applicant_id"),
        "decision": out["final_decision"],
        "approved_amount_nrs": out["approved_amount_nrs"],
        "reasons": out["decision_reasons"],
        "counter_offer": out["counter_offer"],
        "pd": scorecard.get("pd"),
        "credit_score": scorecard.get("credit_score"),
        "risk_grade": scorecard.get("risk_grade"),
        "drivers": scorecard.get("drivers", []),
        "compliance_status": state.get("compliance_status"),
        "triggered_rules": state.get("compliance_flags", []),
        "imr": state.get("imr"),
        "imr_status": state.get("imr_status"),
        "income_confidence": state.get("income_confidence"),
        "income_flags": state.get("income_flags", []),
        "not_screened": (state.get("compliance_result") or {}).get("not_screened", []),
        "policy_version": state.get("policy_version"),
        "model_version": scorecard.get("model_version"),
        "illustrative_rate_pct": out["interest_rate_pct"],
    }
    application_id = state.get("application_id")
    if application_id:
        try:
            db.table("loan_applications").eq("application_id", application_id).update({
                "final_decision": out["final_decision"],
                "approved_amount_nrs": out["approved_amount_nrs"],
                "interest_tier": out["interest_tier"],
                "interest_rate_pct": out["interest_rate_pct"],
                "decision_reason": out["decision_reason"],
            })
        except Exception as e:
            logger.error(f"[Decision Agent] DB update failed for {application_id}: {e}")
        traces = {t["rule_id"]: t for t in (state.get("compliance_result") or {}).get("rule_traces", [])}
        lr = state.get("loan_request", {}) or {}
        income = _num(state.get("income_agent_monthly_est"))
        try:  # columns added by scripts/sql/2026_11_add_assessment_columns.sql
            db.table("loan_applications").eq("application_id", application_id).update({
                "income_mismatch_ratio": state.get("imr"),
                "dsr": (traces.get("DSTI_CAP") or {}).get("observed"),
                "loan_to_income": round(_num(lr.get("amount")) / (12 * income), 3) if income > 0 else None,
                "policy_version": state.get("policy_version"),
            })
        except Exception as e:
            logger.warning(f"[Decision Agent] optional columns not saved for {application_id}: {e}")
    out["status"] = "decision_complete"
    return out
