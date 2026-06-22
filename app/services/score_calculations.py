# score_calculations.py
from typing import Any, Dict, List, Optional, Tuple
from app.services.risk_calculations import calculate_capacity_ratios

# Updated to match Data Dictionary
MIN_SCORE = 300
MAX_SCORE = 850
DEFAULT_BASELINE_SCORE = 550

def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))

def risk_tier_from_score(score: int) -> str:
    """Matches the score_band enum from the data dictionary"""
    if score >= 740: return "excellent"
    if score >= 670: return "very_good"
    if score >= 580: return "good"
    if score >= 450: return "fair"
    return "poor"

def interest_tier_from_score(score: int) -> str:
    """Matches the interest_tier enum (Base, Premium, Subprime)"""
    if score >= 670: return "base"       # 10.0% - 11.5%
    if score >= 580: return "premium"    # 11.5% - 13.0%
    return "subprime"                     # 13.0% - 15.0%

def classify_identity_mismatch(extracted_docs: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Checks if OCR extracted different citizenship numbers across docs"""
    raw_values = extracted_docs.get("all_citizenship_numbers_found") or []
    normalized = []
    for _, value in raw_values:
        if not value: continue
        digits_only = "".join(char for char in str(value) if char.isdigit())
        if digits_only: normalized.append(digits_only)
        
    unique_values = sorted(set(normalized))
    if len(unique_values) <= 1:
        return None, None

    shortest = min(unique_values, key=len)
    longest = max(unique_values, key=len)
    if longest.startswith(shortest) and len(shortest) < len(longest):
        return "identity_mismatch_low_confidence", "OCR truncation detected on identity"
    return "identity_mismatch_hard", "Hard conflict on identity across documents"

def build_suggestions(
    loan_request: Dict[str, Any], 
    capacity: float, 
    risk_tier: str, 
    fraud_flags: List[str]
) -> Dict[str, Any]:
    """Calculates max eligible loan and NRB-compliant interest rate"""
    requested_amount = float(loan_request.get("amount", 500000))
    requested_tenure = int(loan_request.get("tenure_months", 12) or 12)
    existing_liabilities = float(loan_request.get("existing_liabilities_monthly", 0) or 0)

    # NRB Rule NRB-LTI-002: Loan cannot exceed 36x monthly income
    lti_cap = capacity * 36 if capacity > 0 else 0.0
    suggested_amount = max(0.0, min(requested_amount, lti_cap))

    if "identity_mismatch_hard" in fraud_flags:
        suggested_amount = 0.0

    # Interest rate based on tier (NRB corridor: 10% - 15%)
    if risk_tier == "excellent" or risk_tier == "very_good":
        interest_rate = 10.5
    elif risk_tier == "good":
        interest_rate = 12.0
    else:
        interest_rate = 14.5

    return {
        "suggested_loan_amount": round(suggested_amount, 2),
        "suggested_tenure": requested_tenure,
        "suggested_interest_rate_pct": interest_rate,
        "interest_tier": interest_tier_from_score(DEFAULT_BASELINE_SCORE) # Will be updated by score later
    }

def generate_scorecard(
    extracted_docs: Dict[str, Any],
    income_metrics: Dict[str, Any],
    indicators: Dict[str, Any],
    loan_request: Dict[str, Any]
) -> Dict[str, Any]:
    """Generates the final 300-850 score and audit trail"""
    
    capacity = float(indicators.get("estimated_monthly_capacity", 0))
    stability_score = float(indicators.get("stability_score", 0))
    trust_score = float(indicators.get("alternative_trust_score", 0))
    informal_income_ratio = float(income_metrics.get("composition", {}).get("informal_income_ratio_%", 0))
    
    requested_amount = float(loan_request.get("amount", 0))
    existing_liabilities = float(loan_request.get("existing_liabilities_monthly", 0))
    tenure = int(loan_request.get("tenure_months", 12))
    
    ratios = calculate_capacity_ratios(capacity, requested_amount, existing_liabilities, tenure)
    calculated_dti = float(ratios["DTI"])
    calculated_lti = float(ratios["LTI"])

    fraud_flags: List[str] = []
    score_breakdown: List[str] = []
    score = DEFAULT_BASELINE_SCORE

    # 1. Stability Scoring (0 to +100)
    stability_delta = int(round((stability_score - 50) * 1.2))
    score += stability_delta
    score_breakdown.append(f"Income stability: {'+' if stability_delta>=0 else ''}{stability_delta}")

    # 2. Alternative Trust Scoring (-50 to +50)
    trust_delta = int(round((trust_score - 50) * 1.0))
    score += trust_delta
    score_breakdown.append(f"Alternative data trust: {'+' if trust_delta>=0 else ''}{trust_delta}")

    # 3. Informal Income Ratio Penalty
    composition_delta = 30
    if informal_income_ratio > 75:
        composition_delta = -100
        fraud_flags.append("over_reliance_on_informal_income")
    elif informal_income_ratio > 50:
        composition_delta = -40
    score += composition_delta
    score_breakdown.append(f"Income composition: {'+' if composition_delta>=0 else ''}{composition_delta}")

    # 4. NRB LTI Rule Violation
    lti_delta = 0
    if calculated_lti > 36:
        lti_delta = -150
        fraud_flags.append("NRB_LTI_EXCEEDED")
    elif calculated_lti > 24:
        lti_delta = -50
    score += lti_delta
    score_breakdown.append(f"Loan-to-Income ratio: {lti_delta}")

    # 5. Identity Mismatch (Fraud)
    identity_flag, identity_message = classify_identity_mismatch(extracted_docs)
    identity_delta = 0
    if identity_flag == "identity_mismatch_hard":
        identity_delta = -200
        fraud_flags.append(identity_flag)
    elif identity_flag == "identity_mismatch_low_confidence":
        identity_delta = -50
        fraud_flags.append(identity_flag)
    score += identity_delta
    if identity_delta: score_breakdown.append(f"Identity consistency: {identity_delta}")

    # 6. Asset Backing (Lalpurja)
    asset_backing = extracted_docs.get("features", {}).get("asset_backing") or {}
    asset_delta = 40 if asset_backing.get("has_lalpurja") else 0
    score += asset_delta
    if asset_delta: score_breakdown.append(f"Asset backing: +{asset_delta}")

    # Clamp to NRB Bureau limits (300 - 850)
    score = int(round(clamp(score, MIN_SCORE, MAX_SCORE)))
    risk_tier = risk_tier_from_score(score)
    
    suggestions = build_suggestions(loan_request, capacity, risk_tier, fraud_flags)
    suggestions["interest_tier"] = interest_tier_from_score(score)

    return {
        "credit_score": score,
        "score_band": risk_tier,
        "risk_tier": risk_tier,
        "calculated_dti": calculated_dti,
        "calculated_lti": calculated_lti,
        "fraud_flags": fraud_flags,
        "score_breakdown": score_breakdown,
        "audit_note": "Score generated from alternative data (Mobile, Remittance, Coop).",
        **suggestions
    }