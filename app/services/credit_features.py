"""
Feature construction for the probability-of-default (PD) model.

One function, build_feature_row, is used both to build the training table
(experiments/build_features.py) and at serving time (app/agents/score_agent.py), so the
model sees features computed the same way in both places.

Deliberately excluded from the model:
  * protected or proxy attributes: gender, marital status, age, names, citizenship and
    phone numbers, province/district/municipality/ward, rural or urban;
  * outputs of the Track A data generator: its credit_score, composite score, income
    estimate and confidence, decisions, approved amounts, interest rates, processing time
    and compliance results. Our own Income Agent recomputes income and confidence.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from app.services.policy_engine import monthly_instalment

AFFORDABILITY_RATE = 0.14  # same assumption as config/policy_rules.yaml

# elec_on_time_rate is not a model input: in the Income Agent it always equals
# overall_on_time_rate, and an unconstrained copy would defeat that feature's monotone constraint.
NUMERIC_FEATURES = [
    "requested_amount_nrs",
    "requested_tenure_months",
    "collateral_value_nrs",
    "collateral_coverage",
    "existing_loan_count",
    "household_size",
    "land_area_ropani",
    "monthly_income_est",
    "income_confidence",
    "income_signal_count",
    "remittance_monthly_avg",
    "remittance_regularity_score",
    "esewa_net_monthly",
    "esewa_tx_count_6months",
    "cooperative_monthly_sales",
    "coop_tenure_years",
    "utility_avg_bill_nrs",
    "overall_on_time_rate",
    "util_arrears_total_nrs",
    "loan_to_annual_income",
    "instalment_to_income",
    "credit_bureau_score",
    "has_bureau_score",
    "has_esewa_account",
    "has_khalti_account",
    "remittance_receiving",
    "cooperative_member",
]

CATEGORICAL_FEATURES = [
    "loan_purpose",
    "collateral_type",
    "occupation_en",
    "education_level",
    "kyc_tier",
]

FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# +1: PD may only rise with the feature; -1: PD may only fall. Others unconstrained.
MONOTONE = {
    "instalment_to_income": 1,
    "loan_to_annual_income": 1,
    "util_arrears_total_nrs": 1,
    "collateral_coverage": -1,
    "overall_on_time_rate": -1,
    "income_confidence": -1,
    "credit_bureau_score": -1,
}

# Plain-language labels for reason codes.
LABELS = {
    "requested_amount_nrs": "Requested amount",
    "requested_tenure_months": "Loan tenure",
    "collateral_value_nrs": "Collateral value",
    "collateral_coverage": "Collateral cover",
    "existing_loan_count": "Existing loans",
    "household_size": "Household size",
    "land_area_ropani": "Land holding",
    "monthly_income_est": "Observed monthly income",
    "income_confidence": "Strength of income evidence",
    "income_signal_count": "Number of income sources",
    "remittance_monthly_avg": "Remittances via transfer companies",
    "remittance_regularity_score": "Regularity of transfer-company remittances",
    "esewa_net_monthly": "Wallet net inflow",
    "esewa_tx_count_6months": "Wallet activity",
    "cooperative_monthly_sales": "Cooperative sales",
    "coop_tenure_years": "Cooperative membership length",
    "utility_avg_bill_nrs": "Utility bill size",
    "elec_on_time_rate": "On-time electricity payments",
    "overall_on_time_rate": "On-time utility payments",
    "util_arrears_total_nrs": "Utility arrears",
    "loan_to_annual_income": "Loan relative to income",
    "instalment_to_income": "Instalment relative to income",
    "credit_bureau_score": "Credit bureau score",
    "has_bureau_score": "Has a bureau record",
    "has_esewa_account": "Has an eSewa account",
    "has_khalti_account": "Has a Khalti account",
    "remittance_receiving": "Reports receiving remittances",
    "cooperative_member": "Cooperative member",
    "loan_purpose": "Loan purpose",
    "collateral_type": "Collateral type",
    "occupation_en": "Occupation",
    "education_level": "Education",
    "kyc_tier": "KYC tier",
}


def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        s = str(value).replace(",", "").replace("Rs.", "").replace("NPR", "").strip()
        f = float(s)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _flag(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    s = str(value).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return 1.0
    if s in {"false", "0", "no", "n"}:
        return 0.0
    return None


def _cat(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().lower()
    return s or None


def build_feature_row(
    profile: Dict[str, Any],
    application: Dict[str, Any],
    income_features: Dict[str, Any],
    loan_request: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Model inputs for one application.

    profile          applicant_profiles row
    application      loan_applications row (only application-time fields are read)
    income_features  income_signal_features as computed by our Income Agent
    loan_request     optional overrides from the API request (amount, tenure, collateral...)
    """
    lr = loan_request or {}

    def req(key_lr: str, key_app: str) -> Any:
        v = lr.get(key_lr)
        return application.get(key_app) if v in (None, "") else v

    amount = _num(req("amount", "requested_amount_nrs"))
    amount = abs(amount) if amount is not None else None
    tenure = _num(req("tenure_months", "requested_tenure_months"))
    collateral = _num(req("collateral_value_nrs", "collateral_value_nrs"))
    income = _num(income_features.get("derived_income_est"))
    bureau = _num(application.get("credit_bureau_score"))

    instalment = monthly_instalment(amount or 0.0, AFFORDABILITY_RATE, int(tenure or 12)) if amount else None

    row: Dict[str, Any] = {
        "requested_amount_nrs": amount,
        "requested_tenure_months": tenure,
        "collateral_value_nrs": collateral,
        "collateral_coverage": (collateral / amount) if (amount and collateral is not None) else None,
        "existing_loan_count": _num(application.get("existing_loan_count", lr.get("existing_loan_count"))),
        "household_size": _num(profile.get("household_size")),
        "land_area_ropani": _num(profile.get("land_area_ropani")),
        "monthly_income_est": income,
        "income_confidence": _num(income_features.get("income_confidence")),
        "income_signal_count": _num(income_features.get("income_signal_count")),
        "remittance_monthly_avg": _num(income_features.get("remittance_monthly_avg")),
        "remittance_regularity_score": _num(income_features.get("remittance_regularity_score")),
        "esewa_net_monthly": _num(income_features.get("esewa_net_monthly")),
        "esewa_tx_count_6months": _num(income_features.get("esewa_tx_count_6months")),
        "cooperative_monthly_sales": _num(income_features.get("cooperative_monthly_sales")),
        "coop_tenure_years": _num(income_features.get("coop_tenure_years")),
        "utility_avg_bill_nrs": _num(income_features.get("utility_avg_bill_nrs")),
        "elec_on_time_rate": _num(income_features.get("elec_on_time_rate")),
        "overall_on_time_rate": _num(income_features.get("overall_on_time_rate")),
        "util_arrears_total_nrs": _num(income_features.get("util_arrears_total_nrs")),
        "loan_to_annual_income": (amount / (12 * income)) if (amount and income and income > 0) else None,
        "instalment_to_income": (instalment / income) if (instalment and income and income > 0) else None,
        "credit_bureau_score": bureau,
        "has_bureau_score": 1.0 if bureau is not None else 0.0,
        "has_esewa_account": _flag(profile.get("has_esewa_account")),
        "has_khalti_account": _flag(profile.get("has_khalti_account")),
        "remittance_receiving": _flag(profile.get("remittance_receiving")),
        "cooperative_member": _flag(profile.get("cooperative_member")),
        "loan_purpose": _cat(req("loan_purpose", "loan_purpose")),
        "collateral_type": _cat(application.get("collateral_type", lr.get("collateral_type"))),
        "occupation_en": _cat(profile.get("occupation_en")),
        "education_level": _cat(profile.get("education_level")),
        "kyc_tier": _cat(profile.get("kyc_tier")),
    }
    return row
