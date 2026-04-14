# =========================================================
# RISK & FRAUD INDICATORS
# =========================================================
def calculate_income_mismatch_ratio(doc_monthly_income, wallet_monthly_volume):
    """Document monthly ÷ Wallet monthly (key fraud signal)"""
    if wallet_monthly_volume <= 0:
        return float('inf') if doc_monthly_income > 0 else 0.0
    return round(doc_monthly_income / wallet_monthly_volume, 2)

def calculate_income_stability_score(volatility_cv, is_formal):
    """Income Stability Score: Based on volatility CV + formal employment flag"""
    score = 100 - (volatility_cv * 100)
    if is_formal:
        score += 20
    return max(0, min(100, round(score, 1)))

def calculate_tax_trust_score(compliance_flag, effective_rate):
    """Tax Trust Score: Weighted combination of compliance flag + effective tax rate"""
    score = 0
    if compliance_flag:
        score += 50
    if effective_rate and effective_rate > 0:
        tax_score = min(50, effective_rate * 100 * 2.5) # Maxes out at 20% effective tax rate
        score += tax_score
    return round(min(100, score), 1)

def calculate_estimated_monthly_capacity(doc_monthly_income, wallet_monthly_volume):
    """Estimated Monthly Capacity: Weighted income estimate (70% doc, 30% wallet)"""
    if doc_monthly_income <= 0:
        return wallet_monthly_volume
    if wallet_monthly_volume <= 0:
        return doc_monthly_income
    return round((0.7 * doc_monthly_income) + (0.3 * wallet_monthly_volume), 2)

def calculate_capacity_ratios(capacity, loan_amount, existing_liabilities_monthly, annual_interest_rate=0.14, term_months=36):
    """Capacity Ratios: Calculate DTI and LTI but do not enforce—pass to Compliance as advisory"""
    annual_capacity = capacity * 12
    lti = round(loan_amount / annual_capacity, 2) if annual_capacity > 0 else float('inf')
    
    # Standard EMI (Equated Monthly Installment) calculation
    monthly_rate = annual_interest_rate / 12
    if monthly_rate > 0:
        estimated_new_monthly_payment = loan_amount * monthly_rate * ((1 + monthly_rate) ** term_months) / (((1 + monthly_rate) ** term_months) - 1)
    else:
        estimated_new_monthly_payment = loan_amount / term_months
        
    total_monthly_debt = existing_liabilities_monthly + estimated_new_monthly_payment
    
    dti = round(total_monthly_debt / capacity, 2) if capacity > 0 else float('inf')
    
    return {
        "DTI": dti,
        "LTI": lti,
        "estimated_monthly_payment": round(estimated_new_monthly_payment, 2)
    }

def generate_risk_indicators(income_profile, extracted_docs, loan_request):
    doc_features = extracted_docs.get('features', {})
    doc_monthly = doc_features.get('doc_monthly_income', 0)
    tax_compliance = doc_features.get('tax_compliance_flag', False)
    effective_tax = doc_features.get('effective_tax_rate', 0.0)
    
    wallet_monthly = income_profile.get('income', {}).get('monthly_wallet_volume', 0)
    volatility = income_profile.get('stability', {}).get('volatility_cv', 0)
    is_formal = income_profile.get('stability', {}).get('formal_employment', False)
    
    # Defaults in case loan_request is missing
    loan_amount = loan_request.get('amount', 500000) if loan_request else 500000
    existing_liab = loan_request.get('existing_liabilities_monthly', 0) if loan_request else 0
    
    mismatch = calculate_income_mismatch_ratio(doc_monthly, wallet_monthly)
    stability = calculate_income_stability_score(volatility, is_formal)
    tax_trust = calculate_tax_trust_score(tax_compliance, effective_tax)
    capacity = calculate_estimated_monthly_capacity(doc_monthly, wallet_monthly)
    ratios = calculate_capacity_ratios(capacity, loan_amount, existing_liab)
    
    return {
        "mismatch_ratio": mismatch,
        "stability_score": stability,
        "tax_trust_score": tax_trust,
        "estimated_monthly_capacity": capacity,
        "capacity_ratios": ratios
    }
