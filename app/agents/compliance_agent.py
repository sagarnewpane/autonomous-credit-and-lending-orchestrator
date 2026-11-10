"""
Compliance Agent: applies the lending policy in config/policy_rules.yaml.

Runs after the Income Agent and before any model score is used. Screening results
(blacklist, AML) and the KYC tier are read from stored records, never from fields the
applicant fills in on the form. Rules, thresholds and their provenance live in the YAML
file; this module only gathers inputs, calls the policy engine and records the result.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.db import db
from app.models.state import AgentState
from app.services.policy_engine import evaluate, load_policy

logger = logging.getLogger(__name__)


def _fetch_single(table: str, key: str, value: Optional[str]) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        res = db.table(table).select("*").eq(key, value).single().execute()
        return res.data or {}
    except Exception as e:  # never let a lookup failure crash the pipeline
        logger.error(f"[Compliance Agent] lookup failed on {table}: {e}")
        return {}


def build_policy_inputs(state: AgentState) -> Dict[str, Any]:
    """Collect every field the policy rules need, from state and stored records."""
    lr = state.get("loan_request", {}) or {}
    profile = _fetch_single("applicant_profiles", "applicant_id", state.get("applicant_id"))
    application = _fetch_single("loan_applications", "application_id", state.get("application_id"))

    def pick(req_key: str, app_key: str, default: Any = None) -> Any:
        value = lr.get(req_key)
        return application.get(app_key, default) if value in (None, "") else value

    return {
        "applicant_id": state.get("applicant_id"),
        "application_id": state.get("application_id"),
        "requested_amount_nrs": pick("amount", "requested_amount_nrs", 0),
        "requested_tenure_months": pick("tenure_months", "requested_tenure_months", 12),
        "collateral_value_nrs": pick("collateral_value_nrs", "collateral_value_nrs", 0),
        "loan_purpose": pick("loan_purpose", "loan_purpose", ""),
        "existing_liabilities_monthly": lr.get("existing_liabilities_monthly") or 0,
        "existing_loan_count": application.get("existing_loan_count", lr.get("existing_loan_count", 0)),
        "kyc_tier": profile.get("kyc_tier"),
        # Screening results come from stored records (Track A supplies simulated values).
        # None means "not screened" and is reported as such in the trace.
        "nrb_blacklist_flag": application.get("nrb_blacklist_flag"),
        "aml_flag": application.get("aml_flag"),
        "monthly_income": state.get("income_agent_monthly_est"),
        "imr": state.get("imr"),
        "imr_status": state.get("imr_status"),
        "remittance_share": state.get("remittance_share"),
    }


def _message(status: str, triggered: list) -> str:
    if status == "veto":
        return f"Declined by policy rule(s): {', '.join(triggered)}."
    if status == "refer":
        return f"Manual review required: {', '.join(triggered)}."
    if status == "flag":
        return f"Recorded for the credit officer: {', '.join(triggered)}."
    return "All policy checks passed."


def compliance_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph entry point for the Compliance Agent."""
    inputs = build_policy_inputs(state)
    result = evaluate(inputs, load_policy())
    status, triggered = result["status"], result["triggered_rules"]

    application_id = state.get("application_id")
    if application_id:
        try:
            db.table("loan_applications").eq("application_id", application_id).update({
                "compliance_status": status,
                "compliance_flags": triggered,
            })
        except Exception as e:
            logger.error(f"[Compliance Agent] DB save error for {application_id}: {e}")

    notes = [f"{rule_id}: not screened" for rule_id in result["not_screened"]]
    return {
        "compliance_status": status,
        "compliance_flags": triggered,
        "compliance_message": _message(status, triggered),
        "compliance_result": result,
        "compliance_notes": notes,
        "policy_version": result["policy_version"],
        "debug_info": {"compliance_agent": {"inputs_evaluated": inputs}},
    }


class ComplianceChecker:
    """Backward-compatible wrapper used by older scripts and tests."""

    def check_compliance(self, applicant_data: Dict[str, Any]) -> Dict[str, Any]:
        inputs = dict(applicant_data)
        inputs.setdefault("monthly_income", applicant_data.get("income_agent_monthly_est"))
        result = evaluate(inputs, load_policy())
        return {
            "status": result["status"],
            "compliance_flags": result["triggered_rules"],
            "message": _message(result["status"], result["triggered_rules"]),
            "rule_traces": {t["rule_id"]: t for t in result["rule_traces"]},
        }


checker = ComplianceChecker()
