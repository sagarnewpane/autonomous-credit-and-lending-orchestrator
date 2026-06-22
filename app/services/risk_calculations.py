# # =========================================================
# # RISK & FRAUD INDICATORS
# # =========================================================
# def coerce_number(value, default=0.0):
#     try:
#         if value is None:
#             return default
#         return float(value)
#     except (TypeError, ValueError):
#         return default


# def calculate_income_mismatch_ratio(doc_monthly_income, wallet_monthly_volume):
#     """Document monthly ÷ Wallet monthly (key fraud signal)"""
#     doc_monthly_income = coerce_number(doc_monthly_income, 0.0)
#     wallet_monthly_volume = coerce_number(wallet_monthly_volume, 0.0)
#     if wallet_monthly_volume <= 0:
#         return float('inf') if doc_monthly_income > 0 else 0.0
#     return round(doc_monthly_income / wallet_monthly_volume, 2)

# def calculate_income_stability_score(volatility_cv, is_formal):
#     """Income Stability Score: Based on volatility CV + formal employment flag"""
#     score = 100 - (volatility_cv * 100)
#     if is_formal:
#         score += 20
#     return max(0, min(100, round(score, 1)))

# def calculate_tax_trust_score(compliance_flag, effective_rate):
#     """Tax Trust Score: Weighted combination of compliance flag + effective tax rate"""
#     effective_rate = coerce_number(effective_rate, 0.0)
#     score = 0
#     if compliance_flag:
#         score += 50
#     if effective_rate and effective_rate > 0:
#         tax_score = min(50, effective_rate * 100 * 2.5) # Maxes out at 20% effective tax rate
#         score += tax_score
#     return round(min(100, score), 1)

# def calculate_estimated_monthly_capacity(doc_monthly_income, wallet_monthly_volume):
#     """Estimated Monthly Capacity: Weighted income estimate (70% doc, 30% wallet)"""
#     doc_monthly_income = coerce_number(doc_monthly_income, 0.0)
#     wallet_monthly_volume = coerce_number(wallet_monthly_volume, 0.0)
#     if doc_monthly_income <= 0:
#         return wallet_monthly_volume
#     if wallet_monthly_volume <= 0:
#         return doc_monthly_income
#     return round((0.7 * doc_monthly_income) + (0.3 * wallet_monthly_volume), 2)

# def calculate_capacity_ratios(capacity, loan_amount, existing_liabilities_monthly, annual_interest_rate=0.14, term_months=36):
#     """Capacity Ratios: Calculate DTI and LTI but do not enforce—pass to Compliance as advisory"""
#     capacity = coerce_number(capacity, 0.0)
#     loan_amount = coerce_number(loan_amount, 0.0)
#     existing_liabilities_monthly = coerce_number(existing_liabilities_monthly, 0.0)
#     annual_capacity = capacity * 12
#     lti = round(loan_amount / annual_capacity, 2) if annual_capacity > 0 else float('inf')
    
#     # Standard EMI (Equated Monthly Installment) calculation
#     monthly_rate = annual_interest_rate / 12
#     if monthly_rate > 0:
#         estimated_new_monthly_payment = loan_amount * monthly_rate * ((1 + monthly_rate) ** term_months) / (((1 + monthly_rate) ** term_months) - 1)
#     else:
#         estimated_new_monthly_payment = loan_amount / term_months
        
#     total_monthly_debt = existing_liabilities_monthly + estimated_new_monthly_payment
    
#     dti = round(total_monthly_debt / capacity, 2) if capacity > 0 else float('inf')
    
#     return {
#         "DTI": dti,
#         "LTI": lti,
#         "estimated_monthly_payment": round(estimated_new_monthly_payment, 2)
#     }

# def generate_risk_indicators(income_profile, extracted_docs, loan_request):
#     doc_features = extracted_docs.get('features', {})
#     declared_monthly_raw = doc_features.get('declared_monthly_income')
#     declared_monthly = coerce_number(declared_monthly_raw, 0.0)
#     tax_compliance = doc_features.get('tax_compliance_flag', False)
#     effective_tax = coerce_number(doc_features.get('effective_tax_rate', 0.0), 0.0)
#     tax_document_present = bool(doc_features.get('tax_document_present'))
    
#     observed_monthly = coerce_number(income_profile.get('income', {}).get('total_observed_income', 0), 0.0)
#     effective_monthly = coerce_number(income_profile.get('income', {}).get('total_effective_income', 0), 0.0)
#     primary_source = income_profile.get('income', {}).get('primary_income_source')
#     primary_profile = income_profile.get('sources', {}).get(primary_source, {}) if primary_source else {}
#     volatility = primary_profile.get('volatility_cv', 0)
#     is_formal = primary_source == "SALARY" and primary_profile.get('recurrence_ratio', 0) >= 0.75
    
#     # Defaults in case loan_request is missing
#     loan_amount = coerce_number(loan_request.get('amount', 500000), 500000.0) if loan_request else 500000.0
#     existing_liab = coerce_number(loan_request.get('existing_liabilities_monthly', 0), 0.0) if loan_request else 0.0
#     term_months = int(loan_request.get('tenure_months', 12) or 12) if loan_request else 12
    
#     mismatch = (
#         calculate_income_mismatch_ratio(declared_monthly, observed_monthly)
#         if declared_monthly_raw is not None
#         else None
#     )
#     stability = calculate_income_stability_score(volatility, is_formal)
#     tax_trust = calculate_tax_trust_score(tax_compliance, effective_tax)
#     capacity = effective_monthly
#     ratios = calculate_capacity_ratios(capacity, loan_amount, existing_liab, term_months=term_months)
    
#     return {
#         "mismatch_ratio": mismatch,
#         "stability_score": stability,
#         "tax_trust_score": tax_trust,
#         "estimated_monthly_capacity": capacity,
#         "declared_monthly_income": declared_monthly_raw,
#         "observed_monthly_income": observed_monthly,
#         "tax_document_present": tax_document_present,
#         "capacity_ratios": ratios
#     }

# risk_calculations.py
from typing import Any, Dict, Optional

def calculate_capacity_ratios(
    capacity: float, 
    requested_amount: float, 
    existing_liabilities: float, 
    term_months: int
) -> Dict[str, float]:
    """Calculates raw DTI and LTI metrics for the Compliance Agent to evaluate."""
    if capacity <= 0:
        # If income is 0, ratios are infinity (Compliance Agent will flag this)
        return {"DTI": float('inf'), "LTI": float('inf')}

    # Assume standard 14% interest rate for baseline DTI installment calculation
    monthly_rate = 0.14 / 12
    if term_months <= 0: term_months = 12
    
    # Rough monthly installment for requested loan
    installment = (requested_amount * monthly_rate) / (1 - (1 + monthly_rate) ** -term_months)
    
    dti = (installment + existing_liabilities) / capacity
    lti = requested_amount / (capacity * 12) # Loan to Annual Income
    
    return {"DTI": round(dti, 2), "LTI": round(lti, 2)}

def calculate_ltv(requested_amount: float, collateral_value: float) -> float:
    """Calculates raw Loan-to-Value metric for the Compliance Agent."""
    if collateral_value <= 0:
        # If no collateral, LTV is infinity if they asked for a loan, else 0
        return float('inf') if requested_amount > 0 else 0.0
        
    return round(requested_amount / collateral_value, 2)

def calculate_income_mismatch_ratio(declared_monthly: Optional[float], observed_monthly: float) -> Optional[float]:
    """Since we have no tax docs, declared income is usually None."""
    if declared_monthly is None or observed_monthly == 0:
        return None
    return declared_monthly / observed_monthly

def calculate_income_stability_score(volatility_cv: float, is_recurring: bool) -> float:
    """Converts volatility into a 0-100 stability score for the Score Agent."""
    score = 100 - (volatility_cv * 100)
    if not is_recurring:
        score -= 20 # Penalize intermittent income
    return max(0.0, min(100.0, score))

def calculate_alternative_trust_score(extracted_docs: Dict[str, Any], income_profile: Dict[str, Any]) -> float:
    """Rewards alternative data proof (Utility, Coop, Remittance docs)."""
    score = 40.0 # Baseline
    doc_types = extracted_docs.get("doc_types", {})
    
    if doc_types.get("utility_bill"):
        score += 20.0 
    if doc_types.get("cooperative_passbook"):
        score += 20.0 
    if doc_types.get("remittance_receipt"):
        score += 20.0 
        
    return max(0.0, min(100.0, score))

def generate_risk_indicators(
    income_profile: Dict[str, Any], 
    extracted_docs: Dict[str, Any], 
    loan_request: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculates all raw financial risk metrics. 
    NOTE: This function does NOT make decisions or apply NRB rules. 
    It just outputs the numbers for the Score and Compliance Agents."""
    
    capacity = float(income_profile.get("income", {}).get("total_effective_income", 0))
    
    # Values needed for raw metric calculations
    requested_amount = float(loan_request.get("amount", 0))
    existing_liabilities = float(loan_request.get("existing_liabilities_monthly", 0))
    tenure = int(loan_request.get("tenure_months", 12))
    collateral_value = float(loan_request.get("collateral_value_nrs", 0))
    
    # 1. Calculate Ratios (No decisions made here)
    ratios = calculate_capacity_ratios(capacity, requested_amount, existing_liabilities, tenure)
    ltv = calculate_ltv(requested_amount, collateral_value)
    
    # 2. Calculate Behavioral Scores (For Score Agent)
    primary_source = income_profile.get("income", {}).get("primary_income_source")
    primary_profile = income_profile.get("sources", {}).get(primary_source, {}) if primary_source else {}
    
    stability = calculate_income_stability_score(
        float(primary_profile.get("volatility_cv", 1.0)),
        primary_profile.get("months_active", 0) >= 4
    )
    
    trust_score = calculate_alternative_trust_score(extracted_docs, income_profile)
    
    # Return all metrics. The Compliance Agent will use LTI/LTV/DTI later.
    return {
        "estimated_monthly_capacity": round(capacity, 2),
        "observed_monthly_income": round(capacity, 2),
        "stability_score": stability,
        "alternative_trust_score": trust_score,
        "calculated_dti": ratios["DTI"],
        "calculated_lti": ratios["LTI"],
        "calculated_ltv": ltv
    }