# income_agent.py
from datetime import datetime
from app.models.state import AgentState
from app.services.income_profile_calculations import generate_income_profile
from app.services.risk_calculations import generate_risk_indicators
from app.db.supabase import supabase

# Dictionary Constraints
MIN_INCOME = 3000
MAX_INCOME = 200000

def _fetch_applicant_data(applicant_id: str) -> dict:
    """Fetch all required tables from Supabase."""
    mobile_txns = supabase.table('mobile_money_transactions') \
        .select('*').eq('applicant_id', applicant_id).execute().data or []

    remittances = supabase.table('remittance_records') \
        .select('*').eq('applicant_id', applicant_id).execute().data or []

    coop_sales = supabase.table('cooperative_sales') \
        .select('*').eq('applicant_id', applicant_id).execute().data or []

    # NEW: Fetch utility payments for confidence calculation
    utility_payments = supabase.table('utility_payments') \
        .select('cumulative_on_time_rate, payment_date_ad') \
        .eq('applicant_id', applicant_id).execute().data or []

    # NEW: Fetch cooperative member details to check for savings_credit type
    coop_member = supabase.table('cooperative_members') \
        .select('cooperative_type') \
        .eq('applicant_id', applicant_id).execute().data or []

    # NEW: Fetch profile for occupation baseline
    profile = supabase.table('applicant_profiles') \
        .select('occupation_en') \
        .eq('applicant_id', applicant_id).single().execute().data or {}

    return {
        'mobile_txns': mobile_txns,
        'remittances': remittances,
        'coop_sales': coop_sales,
        'utility_payments': utility_payments,
        'coop_member_type': coop_member[0].get('cooperative_type') if coop_member else None,
        'occupation': profile.get('occupation_en', 'Unknown')
    }

def _clean_amount(val):
    if isinstance(val, str):
        return float(val.replace(",", ""))
    return float(val or 0)

def _normalize_mobile_txns(txns: list) -> list:
    """Convert mobile_money_transactions rows into income_profile format and filter future dates."""
    txn_type_fallback = {
        'remittance_receipt': 'remittance_agent',
        'p2p_transfer': 'grocery',
        'merchant_payment': 'grocery',
        'qr_payment': 'grocery',
        'wallet_topup': 'grocery',
    }
    normalized = []
    today = datetime.now()
    
    for t in txns:
        date_str = t.get('transaction_date', '')
        parsed_date = None
        
        # Parse date and filter out future timestamps (2026 noise)
        try:
            parsed_date = datetime.strptime(str(date_str).split(".")[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                parsed_date = datetime.strptime(str(date_str), "%Y-%m-%d")
            except ValueError:
                continue
                
        if parsed_date and parsed_date > today:
            continue  # Skip impossible future transactions
            
        direction = (t.get('direction') or '').lower()
        category = (t.get('counterparty_category') or '').lower()
        if not category:
            txn_type = (t.get('transaction_type') or '').lower()
            category = txn_type_fallback.get(txn_type, 'grocery')

        normalized.append({
            'date': date_str,
            'amount': abs(_clean_amount(t.get('amount_nrs', 0))),
            'type': 'CREDIT' if direction == 'credit' else 'DEBIT',
            'category': category,
        })
    return normalized

def _normalize_remittances(records: list) -> list:
    """Convert remittance_records rows into income_profile format and clean noise."""
    normalized = []
    seen_ids = set()
    
    for r in records:
        rem_id = r.get('remittance_id')
        if rem_id in seen_ids:
            continue
        seen_ids.add(rem_id)
        
        # Drop impossible exchange rates (e.g., 10x actual. USD is highest at ~133)
        if r.get('exchange_rate') and float(r['exchange_rate']) > 200:
            continue
            
        normalized.append({
            'date': r.get('transfer_date_ad', ''),
            'amount': abs(_clean_amount(r.get('amount_nrs', 0))),
            'type': 'CREDIT',
            'category': 'remittance_agent',
        })
    return normalized

def _normalize_coop_sales(sales: list, coop_type: str) -> list:
    """Convert cooperative_sales rows into income_profile format."""
    # CONSTRAINT: savings_credit cooperatives do not have commodity sales.
    if coop_type == 'savings_credit':
        return []
        
    season_month = {
        'spring': '03', 'summer': '06', 'monsoon': '08',
        'autumn': '10', 'winter': '01', 'dry': '02',
        'Kharif': '08', 'Rabi': '01', 'Annual': '06'
    }
    normalized = []
    for s in sales:
        year_bs = str(s.get('sale_year_bs', ''))
        season = (s.get('season') or '').lower()
        date_str = f"{year_bs}-{season_month.get(season, '01')}-01" if year_bs else ''
        
        normalized.append({
            'date': date_str,
            'amount': abs(_clean_amount(s.get('total_amount_nrs', 0))),
            'type': 'CREDIT',
            'category': 'COOPERATIVE_SALES',
        })
    return normalized

def analyze(state: AgentState):
    """Entry point for the Income Agent."""
    applicant_id = state.get('applicant_id')

    if applicant_id:
        db_data = _fetch_applicant_data(applicant_id)
        mobile_txns = _normalize_mobile_txns(db_data['mobile_txns'])
        remittances = _normalize_remittances(db_data['remittances'])
        # Pass coop_type to filter out savings_credit
        coop_sales = _normalize_coop_sales(db_data['coop_sales'], db_data.get('coop_member_type'))
        utility_data = db_data['utility_payments']
        occupation = db_data.get('occupation', 'Unknown')
    else:
        # Fallback for testing
        mobile_txns = state.get('raw_transactions', [])
        remittances = state.get('raw_remittances', [])
        coop_sales = state.get('raw_coop_sales', [])
        utility_data = state.get('utility_payments', [])
        occupation = state.get('occupation', 'Unknown')

    extracted_docs = state.get('extracted_docs', {})
    loan_request = state.get('loan_request', {})

        # --- 1. Generate Income Profile ---
    all_transactions = mobile_txns + remittances + coop_sales
    income_profile = generate_income_profile(all_transactions, extracted_docs)
    
    # Use OBSERVED (normalized) income to prevent double-penalizing downstream
    estimated_monthly_income = int(income_profile.get("income", {}).get("total_observed_income", 0))
    
    # Initialize a list to collect anomaly flags
    income_flags = []
    
    # --- 2. Anomaly & Bounds Checking ---
    # Check for impossibly high income (Fraud / AML trigger)
    if estimated_monthly_income > MAX_INCOME:
        income_flags.append("INCOME_ANOMALY_HIGH")
        estimated_monthly_income = MAX_INCOME  # Cap to schema max, but flag it
        
    # Check for zero/low income (Apply baseline)
    if estimated_monthly_income < MIN_INCOME:
        if occupation == 'Farmer': 
            estimated_monthly_income = 20000
        elif occupation == 'Daily Wage Worker': 
            estimated_monthly_income = 15000
        else: 
            estimated_monthly_income = MIN_INCOME
            
    # --- 3. Calculate Confidence (0.05 - 0.97) ---
    active_sources = len(income_profile.get("sources", {}))
    months_of_data = income_profile.get("income", {}).get("months_of_data", 0)
    
    utility_on_time_rate = 0.0
    if utility_data:
        utility_on_time_rate = float(utility_data[-1].get('cumulative_on_time_rate', 0))
        
    if active_sources >= 3 and months_of_data >= 5:
        confidence = 0.90
    elif active_sources == 2 and months_of_data >= 4:
        confidence = 0.75
    elif active_sources == 1 and months_of_data >= 3:
        confidence = 0.55
    elif active_sources == 1:
        confidence = 0.35
    else:
        confidence = 0.05 
        
    if utility_on_time_rate >= 0.80:
        confidence += 0.07
    elif utility_on_time_rate < 0.50:
        confidence -= 0.10
        
    primary_source = income_profile.get("income", {}).get("primary_income_source")
    if primary_source:
        volatility = income_profile.get("sources", {}).get(primary_source, {}).get("volatility_cv", 0)
        if volatility > 0.5:
            confidence -= 0.05
            
    # CRITICAL: If income is flagged as anomalous, crush the confidence
    if "INCOME_ANOMALY_HIGH" in income_flags:
        confidence = 0.10  # Very low trust
        income_flags.append("TRIGGER_AML_REVIEW") # Tell Compliance Agent to check AML
            
    # Clamp confidence to dictionary bounds (0.05 - 0.97)
    confidence = max(0.05, min(0.97, confidence))

    # --- 4. Generate Risk Indicators for Compliance Agent ---
    indicators = generate_risk_indicators(income_profile, extracted_docs, loan_request)
    
    # Attach our new flags to the indicators for downstream agents
    indicators["income_flags"] = income_flags

    # --- 5. Compute monthly averages by source type ---
    months_of_data = max(income_profile.get("income", {}).get("months_of_data", 0), 1)

    mobile_credit = sum(t['amount'] for t in mobile_txns if t['type'] == 'CREDIT')
    mobile_debit = sum(abs(t['amount']) for t in mobile_txns if t['type'] == 'DEBIT')

    source_monthly = {
        "mobile": {
            "total_credit": round(mobile_credit),
            "total_debit": round(mobile_debit),
            "monthly_avg_credit": round(mobile_credit / months_of_data),
            "monthly_avg_debit": round(mobile_debit / months_of_data),
            "txn_count": len(mobile_txns),
        },
        "remittance": {
            "total": round(sum(t['amount'] for t in remittances)),
            "monthly_avg": round(sum(t['amount'] for t in remittances) / months_of_data),
            "txn_count": len(remittances),
        },
        "cooperative": {
            "total": round(sum(t['amount'] for t in coop_sales)),
            "monthly_avg": round(sum(t['amount'] for t in coop_sales) / months_of_data),
            "txn_count": len(coop_sales),
        },
        "utility": {
            "total_billed": round(sum(u.get('bill_amount_nrs', 0) for u in utility_data)),
            "monthly_avg": round(sum(u.get('bill_amount_nrs', 0) for u in utility_data) / months_of_data) if utility_data else 0,
            "on_time_rate": round(utility_on_time_rate, 2),
            "record_count": len(utility_data),
        },
    }

    return {
        "income_metrics": income_profile,
        "indicators": indicators,
        "income_agent_monthly_est": estimated_monthly_income,
        "income_confidence": round(confidence, 2),
        "source_monthly": source_monthly,
        "status": "income_analysis_complete"
    }