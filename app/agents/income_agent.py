# income_agent.py
from datetime import datetime
from app.models.state import AgentState
from app.services.income_profile_calculations import generate_income_profile
from app.services.risk_calculations import generate_risk_indicators
from app.services.remittance_processor import process_remittances
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

    # FIX: Added bill_amount_nrs to prevent KeyError in source_monthly calculation
    utility_payments = supabase.table('utility_payments') \
        .select('cumulative_on_time_rate, payment_date_ad, bill_amount_nrs') \
        .eq('applicant_id', applicant_id).execute().data or []

    coop_member = supabase.table('cooperative_members') \
        .select('cooperative_type') \
        .eq('applicant_id', applicant_id).execute().data or []

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

def _normalize_mobile_txns(txns: list) -> tuple:
    """Convert mobile_money_transactions rows into income_profile format and filter future dates."""
    txn_type_fallback = {
        'remittance_receipt': 'remittance_agent',
        'p2p_transfer': 'grocery',
        'merchant_payment': 'grocery',
        'qr_payment': 'grocery',
        'wallet_topup': 'grocery',
    }
    normalized = []
    future_flags = []
    today = datetime.now()
    
    for t in txns:
        date_str = t.get('transaction_date', '')
        parsed_date = None
        
        try:
            parsed_date = datetime.strptime(str(date_str).split(".")[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                parsed_date = datetime.strptime(str(date_str), "%Y-%m-%d")
            except ValueError:
                continue
                
        is_future = parsed_date and parsed_date > today
            
        direction = (t.get('direction') or '').lower()
        category = (t.get('counterparty_category') or '').lower()
        if not category:
            txn_type = (t.get('transaction_type') or '').lower()
            category = txn_type_fallback.get(txn_type, 'grocery')

        # FIX: If it's a future date, flag it and SKIP adding it to income calculation
        if is_future:
            future_flags.append({
                'transaction_id': t.get('transaction_id', 'unknown'),
                'date': date_str,
                'amount': _clean_amount(t.get('amount_nrs', 0)),
                'direction': direction,
            })
            continue  # Do not append to normalized list
            
        normalized.append({
            'date': date_str,
            'amount': abs(_clean_amount(t.get('amount_nrs', 0))),
            'type': 'CREDIT' if direction == 'credit' else 'DEBIT',
            'category': category,
        })
        
    return normalized, future_flags

def _normalize_coop_sales(sales: list, coop_type: str) -> list:
    """Convert cooperative_sales rows into income_profile format."""
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
        mobile_txns, future_flags = _normalize_mobile_txns(db_data['mobile_txns'])
        remittances, remittance_anomalies = process_remittances(db_data['remittances'])
        coop_sales = _normalize_coop_sales(db_data['coop_sales'], db_data.get('coop_member_type'))
        utility_data = db_data['utility_payments']
        occupation = db_data.get('occupation', 'Unknown')
    else:
        mobile_txns, future_flags = _normalize_mobile_txns(state.get('raw_transactions', []))
        remittances, remittance_anomalies = process_remittances(state.get('raw_remittances', []))
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
    if estimated_monthly_income > MAX_INCOME:
        income_flags.append("INCOME_ANOMALY_HIGH")
        estimated_monthly_income = MAX_INCOME 
        
    if estimated_monthly_income < MIN_INCOME:
        if occupation == 'Farmer': 
            estimated_monthly_income = 20000
        elif occupation == 'Daily Wage Worker': 
            estimated_monthly_income = 15000
        else: 
            estimated_monthly_income = MIN_INCOME
            
        # --- 3. Calculate Confidence (0.05 - 0.97) ---
    sources = income_profile.get("sources", {})
    active_sources = len(sources)
    months_of_data = income_profile.get("income", {}).get("months_of_data", 0)
    
    utility_on_time_rate = 0.0
    if utility_data:
        utility_on_time_rate = float(utility_data[-1].get('cumulative_on_time_rate', 0))
        
    # NEW: Calculate average confidence of the actual sources
    if active_sources > 0:
        avg_source_confidence = sum(s["confidence_score"] for s in sources.values()) / active_sources
    else:
        avg_source_confidence = 0.0

    # NEW: Base confidence is now driven by the actual source quality + months of data
    if active_sources == 0:
        confidence = 0.05
    else:
        # Weight: 70% source quality, 30% data history (max 1.0)
        history_score = min(months_of_data / 6, 1.0) 
        confidence = (avg_source_confidence * 0.7) + (history_score * 0.3)

    # Modifiers (Utility & Volatility) remain the same...
    if utility_on_time_rate >= 0.80:
        confidence += 0.07

    elif utility_on_time_rate < 0.50:
        confidence -= 0.10

    # --- 4. Generate Risk Indicators for Compliance Agent ---
    indicators = generate_risk_indicators(income_profile, extracted_docs, loan_request)
    indicators["income_flags"] = income_flags

    # --- 5. Compute monthly averages by source type ---
    REFERENCE_MONTHS = 6

    mobile_credit = sum(t['amount'] for t in mobile_txns if t['type'] == 'CREDIT')
    mobile_debit = sum(abs(t['amount']) for t in mobile_txns if t['type'] == 'DEBIT')

    source_monthly = {
        "mobile": {
            "total_credit": round(mobile_credit),
            "total_debit": round(mobile_debit),
            "monthly_avg_credit": round(mobile_credit / REFERENCE_MONTHS),
            "monthly_avg_debit": round(mobile_debit / REFERENCE_MONTHS),
            "txn_count": len(mobile_txns),
        },
        "remittance": {
            "total": round(sum(t['amount'] for t in remittances)),
            "monthly_avg": round(sum(t['amount'] for t in remittances) / REFERENCE_MONTHS),
            "txn_count": len(remittances),
        },
        "cooperative": {
            "total": round(sum(t['amount'] for t in coop_sales)),
            # FIX: Coop sales are annual lump sums. Divide by 12 for an accurate monthly proxy.
            "monthly_avg": round(sum(t['amount'] for t in coop_sales) / 12), 
            "txn_count": len(coop_sales),
        },
        "utility": {
            "total_billed": round(sum(u.get('bill_amount_nrs', 0) for u in utility_data)),
            "monthly_avg": round(sum(u.get('bill_amount_nrs', 0) for u in utility_data) / REFERENCE_MONTHS) if utility_data else 0,
            "on_time_rate": round(utility_on_time_rate, 2),
            "record_count": len(utility_data),
        },
    }

    all_anomalies = future_flags + remittance_anomalies

    return {
        "income_metrics": income_profile,
        "indicators": indicators,
        "income_agent_monthly_est": estimated_monthly_income,
        "income_confidence": round(confidence, 2),
        "source_monthly": source_monthly,
        "anomaly_flags": all_anomalies,
        "status": "income_analysis_complete"
    }