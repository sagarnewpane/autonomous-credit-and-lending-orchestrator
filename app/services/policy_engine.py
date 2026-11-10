"""
Policy engine: evaluates the rules in config/policy_rules.yaml.

The engine is deterministic and has no learned parameters. Each evaluation returns one
trace per rule (triggered or not, observed value, threshold, provenance), the overall
status, and the policy version, so every decision can be traced to the exact rule file
that produced it.

Status precedence: veto > refer > flag > pass.
"""

from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "policy_rules.yaml"
_PRECEDENCE = {"pass": 0, "flag": 1, "refer": 2, "veto": 3}


def _policy_path() -> Path:
    return Path(os.getenv("POLICY_RULES_PATH", str(DEFAULT_POLICY_PATH)))


@lru_cache(maxsize=8)
def _load(path_str: str) -> Dict[str, Any]:
    raw = Path(path_str).read_bytes()
    policy = yaml.safe_load(raw)
    policy["policy_version"] = hashlib.sha256(raw).hexdigest()[:12]
    return policy


def load_policy(path: Optional[str] = None) -> Dict[str, Any]:
    """Load (and cache) the policy file; adds policy_version, a hash of its bytes."""
    return _load(str(path or _policy_path()))


def monthly_instalment(principal: float, annual_rate: float, months: int) -> float:
    """Equated monthly instalment for a fully amortising loan."""
    principal = max(float(principal or 0.0), 0.0)
    months = max(int(months or 0), 1)
    r = float(annual_rate) / 12.0
    if r <= 0:
        return principal / months
    return principal * r / (1.0 - (1.0 + r) ** (-months))


def max_principal_for_instalment(instalment: float, annual_rate: float, months: int) -> float:
    """Largest principal whose instalment does not exceed `instalment`."""
    instalment = max(float(instalment or 0.0), 0.0)
    months = max(int(months or 0), 1)
    r = float(annual_rate) / 12.0
    if r <= 0:
        return instalment * months
    return instalment * (1.0 - (1.0 + r) ** (-months)) / r


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(str(value).replace(",", "").replace("Rs.", "").replace("NPR", "").strip())
    except (TypeError, ValueError):
        return default


def _evaluate_rule(rule: Dict[str, Any], a: Dict[str, Any], assumptions: Dict[str, Any]) -> Dict[str, Any]:
    check = rule["check"]
    params = rule.get("params", {}) or {}
    triggered = False
    observed: Any = None
    threshold: Any = None
    applicable = True
    note = ""

    action = rule["action"]
    if check == "flag_true":
        raw = a.get(rule["field"])
        threshold = True
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            # No screening result: never treated as a pass. The rule's if_missing action
            # (refer by default) applies instead of its normal action.
            observed, note = None, "not screened"
            triggered, action = True, rule.get("if_missing", "refer")
        else:
            observed = _truthy(raw)
            triggered = bool(observed)

    elif check == "max_amount_by_tier":
        tier_raw = a.get(rule["field"])
        tier = str(tier_raw).strip().lower() if tier_raw not in (None, "") else rule.get("default_tier", "basic")
        if tier not in params:
            note = f"unknown tier '{tier}', treated as {rule.get('default_tier', 'basic')}"
            tier = rule.get("default_tier", "basic")
        limit = params.get(tier)
        observed = {"tier": tier, "requested": _num(a.get("requested_amount_nrs"))}
        threshold = limit
        triggered = limit is not None and observed["requested"] > float(limit)

    elif check == "collateral_required_above":
        req = _num(a.get("requested_amount_nrs"))
        col = _num(a.get("collateral_value_nrs"))
        observed = {"requested": req, "collateral": col}
        threshold = params["amount_threshold"]
        triggered = req > float(threshold) and col <= 0

    elif check == "loan_to_monthly_income_above":
        purposes = set(params.get("purposes", []))
        purpose = str(a.get("loan_purpose") or "").strip().lower()
        if purposes and purpose not in purposes:
            applicable, note = False, f"purpose '{purpose}' not covered"
        income = _num(a.get("monthly_income"))
        req = _num(a.get("requested_amount_nrs"))
        observed = round(req / max(income, 1.0), 2)
        threshold = params["max_multiple"]
        triggered = applicable and observed > float(threshold)

    elif check == "existing_loans_at_least":
        observed = int(_num(a.get("existing_loan_count")))
        threshold = params["count"]
        triggered = observed >= int(threshold)

    elif check == "dsti_above":
        rate = float(assumptions.get("annual_interest_rate_for_affordability", 0.14))
        income = _num(a.get("monthly_income"))
        new_emi = monthly_instalment(_num(a.get("requested_amount_nrs")), rate, int(_num(a.get("requested_tenure_months"), 12)))
        existing = _num(a.get("existing_liabilities_monthly"))
        observed = round((existing + new_emi) / income, 3) if income > 0 else None
        threshold = params["max_ratio"]
        if observed is None:
            applicable, note = False, "no observed income"
        triggered = observed is not None and observed > float(threshold)

    elif check == "imr_outside":
        imr = a.get("imr")
        observed = imr
        high = float(params["high"])
        if _num(a.get("remittance_share")) >= float(params.get("remittance_share_threshold", 1.1)):
            high = float(params.get("high_if_remittance_household", high))
            note = "remittance household: relaxed upper bound"
        threshold = {"low": float(params["low"]), "high": high}
        if imr is None:
            applicable, note = False, a.get("imr_status") or "not computed"
        triggered = imr is not None and (imr < threshold["low"] or imr > threshold["high"])

    else:
        applicable, note = False, f"unknown check '{check}'"

    return {
        "rule_id": rule["id"],
        "description": " ".join(str(rule.get("description", "")).split()),
        "triggered": bool(triggered),
        "applicable": bool(applicable),
        "action": action if triggered else "pass",
        "observed": observed,
        "threshold": threshold,
        "provenance": rule.get("provenance"),
        "source_status": rule.get("source_status"),
        "note": note,
    }


def evaluate(applicant: Dict[str, Any], policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Evaluate every rule for one application.

    applicant keys used: requested_amount_nrs, requested_tenure_months, collateral_value_nrs,
    loan_purpose, monthly_income, existing_liabilities_monthly, existing_loan_count, kyc_tier,
    nrb_blacklist_flag, aml_flag, imr, imr_status, remittance_share.
    """
    policy = policy or load_policy()
    assumptions = policy.get("assumptions", {}) or {}
    traces: List[Dict[str, Any]] = [_evaluate_rule(r, applicant, assumptions) for r in policy["rules"]]
    status = "pass"
    for t in traces:
        if t["triggered"] and _PRECEDENCE[t["action"]] > _PRECEDENCE[status]:
            status = t["action"]
    triggered = [t["rule_id"] for t in traces if t["triggered"]]
    not_screened = [t["rule_id"] for t in traces if t["note"] == "not screened"]
    return {
        "status": status,
        "triggered_rules": triggered,
        "not_screened": not_screened,
        "rule_traces": traces,
        "policy_version": policy["policy_version"],
        "policy_label": policy.get("version_label"),
    }
