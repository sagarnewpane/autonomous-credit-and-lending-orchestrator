from typing import Any, Dict, List, Optional, Tuple

from app.services.risk_calculations import (
    calculate_capacity_ratios,
    calculate_income_mismatch_ratio,
    calculate_income_stability_score,
    calculate_tax_trust_score,
)


DEFAULT_BASELINE_SCORE = 500
MAX_SCORE = 1000
MIN_SCORE = 0


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def normalize_identity_values(extracted_docs: Dict[str, Any]) -> List[str]:
    raw_values = extracted_docs.get("all_citizenship_numbers_found") or []
    normalized = []
    for _, value in raw_values:
        if not value:
            continue
        digits_only = "".join(char for char in str(value) if char.isdigit())
        if digits_only:
            normalized.append(digits_only)
    return normalized


def classify_identity_mismatch(extracted_docs: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    normalized = normalize_identity_values(extracted_docs)
    unique_values = sorted(set(normalized))
    if len(unique_values) <= 1:
        return None, None

    shortest = min(unique_values, key=len)
    longest = max(unique_values, key=len)
    if longest.startswith(shortest) and len(shortest) < len(longest):
        return "identity_mismatch_low_confidence", "Cross-document identity values appear truncated rather than fully conflicting"

    return "identity_mismatch_hard", "Cross-document identity values conflict across uploaded documents"


def determine_scoring_confidence(
    extracted_docs: Dict[str, Any],
    income_metrics: Dict[str, Any],
    fraud_flags: List[str],
) -> str:
    has_tax_doc = bool(income_metrics.get("document_validation", {}).get("tax_document_present"))
    months_of_data = income_metrics.get("income", {}).get("months_of_data", 0)

    if "identity_mismatch_hard" in fraud_flags:
        return "LOW"
    if months_of_data < 3 or not has_tax_doc or "identity_mismatch_low_confidence" in fraud_flags:
        return "MEDIUM"
    return "HIGH"


def risk_tier_from_score(score: int) -> str:
    if score > 750:
        return "LOW"
    if score >= 500:
        return "MEDIUM"
    return "HIGH"


def build_score_delta(label: str, delta: int) -> str:
    sign = "+" if delta >= 0 else ""
    return f"{label}: {sign}{delta}"


def calculate_max_loan_for_target_dti(
    capacity: float,
    existing_liabilities_monthly: float,
    term_months: int,
    annual_interest_rate: float = 0.14,
    target_dti: float = 0.4,
) -> float:
    if capacity <= 0 or term_months <= 0:
        return 0.0

    payment_budget = max(0.0, (capacity * target_dti) - existing_liabilities_monthly)
    if payment_budget <= 0:
        return 0.0

    monthly_rate = annual_interest_rate / 12
    if monthly_rate <= 0:
        return payment_budget * term_months

    factor = ((1 + monthly_rate) ** term_months) - 1
    denominator = monthly_rate * ((1 + monthly_rate) ** term_months)
    if denominator <= 0:
        return 0.0

    return payment_budget * (factor / denominator)


def build_suggestions(
    loan_request: Dict[str, Any],
    capacity: float,
    risk_tier: str,
    fraud_flags: List[str],
) -> Dict[str, Any]:
    requested_amount = float(loan_request.get("amount", 500000))
    requested_tenure = int(loan_request.get("tenure_months", 12) or 12)
    existing_liabilities = float(loan_request.get("existing_liabilities_monthly", 0) or 0)

    lti_cap = capacity * 12 * 5 if capacity > 0 else 0.0
    dti_cap = calculate_max_loan_for_target_dti(
        capacity,
        existing_liabilities,
        requested_tenure,
        target_dti=0.4,
    )
    suggested_amount = max(0.0, min(requested_amount, lti_cap, dti_cap if dti_cap > 0 else requested_amount))

    suggested_tenure = requested_tenure
    if suggested_amount < requested_amount and capacity > 0:
        for candidate in (18, 24, 36, 48, 60):
            max_for_candidate = calculate_max_loan_for_target_dti(
                capacity,
                existing_liabilities,
                candidate,
                target_dti=0.4,
            )
            if max_for_candidate >= min(requested_amount, lti_cap):
                suggested_tenure = candidate
                break

    if risk_tier == "LOW":
        interest_premium = 0.0
    elif risk_tier == "MEDIUM":
        interest_premium = 2.0
    else:
        interest_premium = 4.0

    if "identity_mismatch_hard" in fraud_flags:
        suggested_amount = 0.0

    return {
        "suggested_loan_amount": round(suggested_amount, 2),
        "suggested_tenure": suggested_tenure,
        "suggested_interest_premium": interest_premium,
    }


def build_top_risk_drivers(
    fraud_flags: List[str],
    income_mismatch_ratio: Optional[float],
    stability_score: float,
    informal_income_ratio: float,
) -> List[str]:
    drivers: List[str] = []

    if "identity_mismatch_hard" in fraud_flags:
        drivers.append("Cross-document identity conflict detected")
    elif "identity_mismatch_low_confidence" in fraud_flags:
        drivers.append("Identity evidence is inconsistent but may be OCR-truncated")

    if "income_mismatch_unavailable" in fraud_flags:
        drivers.append("Declared income evidence is unavailable, so scoring relies on cash-flow behavior")
    elif income_mismatch_ratio not in (0, float("inf"), None) and income_mismatch_ratio < 0.5:
        drivers.append("Declared income is far below observed cash flow")
    elif income_mismatch_ratio > 3:
        drivers.append("Declared income is far above observed cash flow")

    if stability_score < 65:
        drivers.append("Income stability is weak after volatility and recurrence adjustments")

    if informal_income_ratio > 50:
        drivers.append("Repayment capacity depends heavily on informal income sources")

    return drivers[:3]


def generate_scorecard(
    extracted_docs: Dict[str, Any],
    income_metrics: Dict[str, Any],
    indicators: Dict[str, Any],
    loan_request: Dict[str, Any],
) -> Dict[str, Any]:
    citizenship_number = extracted_docs.get("citizenship_number")
    capacity = float(indicators.get("estimated_monthly_capacity", 0) or 0)
    observed_monthly = float(indicators.get("observed_monthly_income", 0) or 0)
    declared_monthly_raw = indicators.get("declared_monthly_income")
    declared_monthly = float(declared_monthly_raw or 0)
    tax_document_present = bool(indicators.get("tax_document_present"))
    income_mismatch_ratio = (
        calculate_income_mismatch_ratio(declared_monthly, observed_monthly)
        if declared_monthly_raw is not None
        else None
    )

    primary_source = income_metrics.get("income", {}).get("primary_income_source")
    primary_profile = income_metrics.get("sources", {}).get(primary_source, {}) if primary_source else {}
    stability_score = float(
        calculate_income_stability_score(
            float(primary_profile.get("volatility_cv", 0) or 0),
            primary_source == "SALARY" and float(primary_profile.get("recurrence_ratio", 0) or 0) >= 0.75,
        )
    )
    tax_trust_score = float(
        calculate_tax_trust_score(
            bool(extracted_docs.get("features", {}).get("tax_compliance_flag")),
            extracted_docs.get("features", {}).get("effective_tax_rate", 0.0),
        )
    )

    requested_amount = float(loan_request.get("amount", 500000) or 500000)
    existing_liabilities = float(loan_request.get("existing_liabilities_monthly", 0) or 0)
    tenure_months = int(loan_request.get("tenure_months", 12) or 12)
    ratios = calculate_capacity_ratios(
        capacity,
        requested_amount,
        existing_liabilities,
        term_months=tenure_months,
    )
    calculated_dti = float(ratios["DTI"])
    calculated_lti = float(ratios["LTI"])

    fraud_flags: List[str] = []
    score_breakdown: List[str] = []
    score = DEFAULT_BASELINE_SCORE

    mismatch_delta = 0
    if declared_monthly_raw is None:
        mismatch_delta = 0
        fraud_flags.append("income_mismatch_unavailable")
    elif income_mismatch_ratio == float("inf"):
        mismatch_delta = -220
        fraud_flags.append("declared_income_without_observed_cashflow")
    elif income_mismatch_ratio < 0.5:
        mismatch_delta = -160
        fraud_flags.append("income_mismatch_low")
    elif income_mismatch_ratio > 3:
        mismatch_delta = -200
        fraud_flags.append("income_mismatch_high")
    elif 0.75 <= income_mismatch_ratio <= 1.25:
        mismatch_delta = 80
    else:
        mismatch_delta = 20
    score += mismatch_delta
    score_breakdown.append(build_score_delta("Income mismatch", mismatch_delta))

    stability_delta = int(round((stability_score - 50) * 2.4))
    score += stability_delta
    score_breakdown.append(build_score_delta("Income stability", stability_delta))

    tax_delta = int(round((tax_trust_score - 50) * 2.4)) if tax_document_present else 0
    score += tax_delta
    score_breakdown.append(build_score_delta("Tax trust", tax_delta))

    informal_income_ratio = float(income_metrics.get("composition", {}).get("informal_income_ratio_%", 0) or 0)
    composition_delta = 40
    if informal_income_ratio > 75:
        composition_delta = -130
    elif informal_income_ratio > 50:
        composition_delta = -70
    elif informal_income_ratio > 30:
        composition_delta = -20
    score += composition_delta
    score_breakdown.append(build_score_delta("Income composition", composition_delta))

    identity_flag, identity_message = classify_identity_mismatch(extracted_docs)
    identity_delta = 0
    if identity_flag == "identity_mismatch_hard":
        identity_delta = -260
        fraud_flags.append(identity_flag)
    elif identity_flag == "identity_mismatch_low_confidence":
        identity_delta = -90
        fraud_flags.append(identity_flag)
    if identity_message:
        score += identity_delta
        score_breakdown.append(build_score_delta("Identity consistency", identity_delta))

    asset_backing = extracted_docs.get("features", {}).get("asset_backing") or {}
    asset_delta = 25 if asset_backing.get("has_lalpurja") and asset_backing.get("ownership_documented") else 0
    score += asset_delta
    if asset_delta:
        score_breakdown.append(build_score_delta("Asset backing", asset_delta))

    score = int(round(clamp(score, MIN_SCORE, MAX_SCORE)))
    risk_tier = risk_tier_from_score(score)
    suggestions = build_suggestions(loan_request, capacity, risk_tier, fraud_flags)
    top_risk_drivers = build_top_risk_drivers(
        fraud_flags,
        income_mismatch_ratio,
        stability_score,
        informal_income_ratio,
    )
    scoring_confidence = determine_scoring_confidence(extracted_docs, income_metrics, fraud_flags)

    return {
        "citizenship_number": citizenship_number,
        "credit_score": score,
        "risk_tier": risk_tier,
        "scoring_confidence": scoring_confidence,
        "income_mismatch_ratio": income_mismatch_ratio,
        "stability_score": round(stability_score, 1),
        "tax_trust_score": round(tax_trust_score, 1),
        "estimated_monthly_capacity": round(capacity, 2),
        "calculated_dti": calculated_dti,
        "calculated_lti": calculated_lti,
        "fraud_flags": fraud_flags,
        "score_breakdown": score_breakdown,
        "top_risk_drivers": top_risk_drivers,
        "audit_note": "Credit risk assessment only; compliance validation required.",
        **suggestions,
    }
