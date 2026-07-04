# income_agent.py
"""
Income Agent - Calculates income signals from raw financial data.
ZERO-SHOT READY: Will never crash, always returns valid state.
"""
import logging
from datetime import datetime
from statistics import mean, pstdev
from typing import Any, TypedDict
from app.models.state import AgentState
from app.services.income_profile_calculations import generate_income_profile
from app.services.risk_calculations import generate_risk_indicators
from app.services.remittance_processor import process_remittances
from app.db import db

# ============================================================
# CONFIGURATION
# ============================================================
MIN_INCOME = 3000
MAX_INCOME = 200000
OCCUPATION_FLOORS = {
    'farmer': 20000,
    'daily_wage_worker': 15000,
}

logger = logging.getLogger(__name__)

# ============================================================
# SAFE DEFAULTS - Never return None or crash
# ============================================================
DEFAULT_UTILITY_SIGNALS = {
    "utility_avg_bill_nrs": 0.0,
    "elec_on_time_rate": 0.5,
    "overall_on_time_rate": 0.5,
    "util_arrears_total_nrs": 0.0,
}

DEFAULT_MOBILE_SIGNALS = {
    "esewa_net_monthly": 0.0,
    "esewa_tx_count_6months": 0,
    "mobile_net_monthly": 0.0,
    "total_mobile_tx_count": 0,
}

DEFAULT_REMITTANCE_SIGNALS = {
    "remittance_monthly_avg": 0.0,
    "remittance_regularity_score": 0.0,
    "total_remittances": 0,
    "unique_rem_months": 0,
}

DEFAULT_INCOME_FEATURES = {
    "income_signal_count": 0,
    "remittance_monthly_avg": 0,
    "remittance_regularity_score": 0.0,
    "esewa_net_monthly": 0,
    "esewa_tx_count_6months": 0,
    "cooperative_monthly_sales": 0,
    "utility_avg_bill_nrs": 0,
    "elec_on_time_rate": 0.5,
    "overall_on_time_rate": 0.5,
    "util_arrears_total_nrs": 0,
    "land_area_ropani": 0,
    "coop_tenure_years": 0.0,
    "derived_income_est": 0,
    "income_confidence": 0.0,
}

# ============================================================
# SAFE HELPERS
# ============================================================
def _safe_float(val: Any, default: float = 0.0) -> float:
    """Convert any value to float safely."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace(",", "").replace(" ", "").strip()
        for symbol in ["Rs.", "Rs", "NPR", "₹", "$"]:
            cleaned = cleaned.replace(symbol, "")
        try:
            return abs(float(cleaned))
        except ValueError:
            return default
    # Handle decimal.Decimal from PostgreSQL
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Convert any value to int safely."""
    return int(_safe_float(val, default))


def _safe_str(val: Any, default: str = "") -> str:
    """Convert any value to lowercase string safely."""
    if val is None:
        return default
    return str(val).strip().lower()


def _safe_bool(val: Any, default: bool = False) -> bool:
    """Convert any value to bool safely."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return _safe_str(val) in ["true", "1", "yes", "y"]


def _safe_parse_date(date_str: Any) -> datetime | None:
    """Parse date string safely, return None on failure."""
    if not date_str:
        return None
    
    date_str = str(date_str).split(".")[0].strip()  # Remove microseconds
    
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _get_year_month_key(dt: datetime) -> str:
    """Get 'YYYY-MM' key from datetime."""
    return f"{dt.year}-{dt.month:02d}"


# ============================================================
# SAFE DATABASE FETCHING
# ============================================================
def _safe_fetch_table(table_name: str, applicant_id: str, columns: str = "*") -> list:
    """Fetch from Supabase, never crash."""
    try:
        result = db.table(table_name) \
            .select(columns) \
            .eq('applicant_id', applicant_id) \
            .execute()
        return result.data if result and result.data else []
    except Exception as e:
        logger.error(f"[Income Agent] DB fetch error on {table_name}: {e}")
        return []


def _safe_fetch_single(table_name: str, applicant_id: str, columns: str = "*") -> dict:
    """Fetch single row from Supabase, never crash."""
    try:
        result = db.table(table_name) \
            .select(columns) \
            .eq('applicant_id', applicant_id) \
            .single() \
            .execute()
        return result.data if result and result.data else {}
    except Exception as e:
        logger.error(f"[Income Agent] DB fetch error on {table_name}: {e}")
        return {}


def _safe_upsert(table_name: str, data: dict, conflict_col: str = "applicant_id") -> bool:
    """Upsert to Supabase, return success status."""
    if not data.get(conflict_col):
        logger.error(f"[Income Agent] Missing {conflict_col} for {table_name}")
        return False
    try:
        result = db.table(table_name).upsert(data, on_conflict=conflict_col)
        return bool(result and result.data)
    except Exception as e:
        logger.error(f"[Income Agent] DB upsert error on {table_name}: {e}")
        return False


# ============================================================
# DATA FETCHING
# ============================================================
def _fetch_applicant_data(applicant_id: str) -> dict:
    """Fetch all required tables from Supabase."""
    logger.info(f"[Income Agent] Fetching data for {applicant_id}")
    
    mobile_txns = _safe_fetch_table('mobile_money_transactions', applicant_id)
    remittances = _safe_fetch_table('remittance_records', applicant_id)
    coop_sales = _safe_fetch_table('cooperative_sales', applicant_id)
    utility_payments = _safe_fetch_table('utility_payments', applicant_id)
    coop_member_rows = _safe_fetch_table('cooperative_members', applicant_id, 'cooperative_type,membership_year_bs')
    profile = _safe_fetch_single('applicant_profiles', applicant_id, 'occupation_en,land_area_ropani')
    
    # Extract single values from lists safely
    coop_member_type = _safe_str(coop_member_rows[0].get('cooperative_type')) if coop_member_rows else ""
    coop_membership_year_bs = coop_member_rows[0].get('membership_year_bs') if coop_member_rows else None
    
    data = {
        'mobile_txns': mobile_txns,
        'remittances': remittances,
        'coop_sales': coop_sales,
        'utility_payments': utility_payments,
        'coop_member_type': coop_member_type,
        'coop_membership_year_bs': coop_membership_year_bs,
        'land_area_ropani': _safe_float(profile.get('land_area_ropani')),
        'occupation': _safe_str(profile.get('occupation_en'), 'unknown'),
        'fetch_counts': {
            'mobile_txns': len(mobile_txns),
            'remittances': len(remittances),
            'coop_sales': len(coop_sales),
            'utility_payments': len(utility_payments),
        }
    }
    
    logger.info(f"[Income Agent] Fetched: {data['fetch_counts']}")
    return data


# ============================================================
# DATA CLEANING
# ============================================================
def _clean_utility_data(records: list) -> list:
    """Clean utility records: remove noise, fix values."""
    cleaned = []
    for r in records:
        # Skip if flagged as duplicate
        if _safe_bool(r.get('_noise_duplicate')):
            continue
        
        amount = _safe_float(r.get('bill_amount_nrs'))
        
        # Fix negative amounts
        if _safe_bool(r.get('_noise_negative_bill')):
            amount = abs(amount)
        
        cleaned.append({
            'applicant_id': r.get('applicant_id'),
            'bill_amount_nrs': amount,
            'payment_date_ad': r.get('payment_date_ad'),
            'days_late': _safe_float(r.get('days_late'), 1),
            'outstanding_arrears_nrs': _safe_float(r.get('outstanding_arrears_nrs')),
            'is_forced_unpaid': _safe_bool(r.get('_noise_forced_unpaid')),
        })
    return cleaned


def _clean_transaction_data(records: list) -> list:
    """Clean mobile transaction records."""
    cleaned = []
    for r in records:
        # Skip anomalies
        if _safe_bool(r.get('_noise_anomaly_flag')):
            continue
        
        amount = r.get('amount_nrs', 0)
        
        # Fix string amounts
        if _safe_bool(r.get('_noise_amount_string')) and isinstance(amount, str):
            amount = _safe_float(amount)
        else:
            amount = _safe_float(amount)
        
        cleaned.append({
            'applicant_id': r.get('applicant_id'),
            'transaction_id': r.get('transaction_id'),
            'transaction_date': r.get('transaction_date'),
            'amount_nrs': amount,
            'direction': _safe_str(r.get('direction'), 'unknown'),
            'counterparty_category': _safe_str(r.get('counterparty_category'), 'unknown'),
            'transaction_type': _safe_str(r.get('transaction_type')),
            'platform': _safe_str(r.get('platform')),
        })
    return cleaned


def _clean_remittance_data(records: list) -> list:
    """Clean remittance records."""
    cleaned = []
    for r in records:
        # Skip wrong currency or duplicates
        if _safe_bool(r.get('_noise_wrong_currency')):
            continue
        if _safe_bool(r.get('_noise_duplicate')):
            continue
        
        amount = _safe_float(r.get('amount_nrs'))
        rate = _safe_float(r.get('exchange_rate'))
        foreign_amount = _safe_float(r.get('amount_foreign_currency'))
        
        # Fix impossible exchange rates (10x error)
        if _safe_bool(r.get('_noise_impossible_rate')) and rate > 0:
            rate = rate / 10.0
            if foreign_amount > 0:
                amount = foreign_amount * rate
            else:
                amount = amount / 10.0
        
        cleaned.append({
            'applicant_id': r.get('applicant_id'),
            'date': r.get('date'),
            'amount_nrs': amount,
            'exchange_rate': rate,
            'amount_foreign_currency': foreign_amount,
        })
    return cleaned


# ============================================================
# SIGNAL BUILDERS (Derived Tables)
# ============================================================
def _build_utility_signals(clean_utils: list) -> dict:
    """Build derived_utility_signals row."""
    if not clean_utils:
        return dict(DEFAULT_UTILITY_SIGNALS)
    
    # Average bill
    total_bill = sum(u['bill_amount_nrs'] for u in clean_utils)
    avg_bill = round(total_bill / len(clean_utils), 2)
    
    # On-time rate - EXCLUDE forced unpaid
    valid_utils = [u for u in clean_utils if not u['is_forced_unpaid']]
    
    if valid_utils:
        on_time_count = sum(1 for u in valid_utils if u['days_late'] <= 0)
        on_time_rate = round(on_time_count / len(valid_utils), 2)
        total_arrears = sum(u['outstanding_arrears_nrs'] for u in valid_utils)
    else:
        on_time_rate = 0.5  # Default when no valid data
        total_arrears = 0.0
    
    return {
        "utility_avg_bill_nrs": avg_bill,
        "elec_on_time_rate": on_time_rate,
        "overall_on_time_rate": on_time_rate,
        "util_arrears_total_nrs": round(total_arrears, 2),
    }


def _build_mobile_signals(clean_txns: list) -> dict:
    """Build derived_mobile_payment_signals row."""
    if not clean_txns:
        return dict(DEFAULT_MOBILE_SIGNALS)
    
    # All mobile
    credits = sum(t['amount_nrs'] for t in clean_txns if t['direction'] == 'credit')
    debits = sum(t['amount_nrs'] for t in clean_txns if t['direction'] == 'debit')
    
    # eSewa only
    esewa_txns = [t for t in clean_txns if t['platform'] == 'esewa']
    esewa_credits = sum(t['amount_nrs'] for t in esewa_txns if t['direction'] == 'credit')
    esewa_debits = sum(t['amount_nrs'] for t in esewa_txns if t['direction'] == 'debit')
    
    return {
        "esewa_net_monthly": round((esewa_credits - esewa_debits) / 6, 2),
        "esewa_tx_count_6months": len(esewa_txns),
        "mobile_net_monthly": round((credits - debits) / 6, 2),
        "total_mobile_tx_count": len(clean_txns),
    }


def _build_remittance_signals(clean_rem: list, normalized_rem: list) -> dict:
    """Build derived_remittance_signals row."""
    if not normalized_rem:
        return dict(DEFAULT_REMITTANCE_SIGNALS)
    
    # Calculate unique months
    months_set = set()
    total_amount = 0.0
    
    for r in normalized_rem:
        dt = _safe_parse_date(r.get('date'))
        if dt:
            months_set.add(_get_year_month_key(dt))
        total_amount += _safe_float(r.get('amount'))
    
    unique_months = max(len(months_set), 1)
    regularity_score = _calculate_remittance_regularity(normalized_rem)
    
    return {
        "remittance_monthly_avg": round(total_amount / unique_months, 2),
        "remittance_regularity_score": regularity_score,
        "total_remittances": round(total_amount),
        "unique_rem_months": len(months_set),
    }


def _calculate_remittance_regularity(remittances: list) -> float:
    """Score (0-1) for remittance consistency."""
    if not remittances or len(remittances) < 2:
        return 0.0
    
    amounts = [_safe_float(r.get('amount')) for r in remittances]
    amounts = [a for a in amounts if a > 0]
    
    if len(amounts) < 2:
        return 0.0
    
    # Amount consistency
    amount_mean = mean(amounts)
    if amount_mean > 0:
        amount_cv = pstdev(amounts) / amount_mean
        amount_score = max(0.0, 1.0 - min(amount_cv, 1.0))
    else:
        amount_score = 0.0
    
    # Timing consistency
    dates = []
    for r in remittances:
        dt = _safe_parse_date(r.get('date'))
        if dt:
            dates.append(dt)
    
    dates.sort()
    
    if len(dates) >= 3:
        gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
        gaps = [g for g in gaps if g > 0]
        
        if gaps:
            gap_mean = mean(gaps)
            if gap_mean > 0:
                gap_cv = pstdev(gaps) / gap_mean
                cadence_score = max(0.0, 1.0 - min(gap_cv, 1.0))
            else:
                cadence_score = 0.0
        else:
            cadence_score = amount_score
    else:
        cadence_score = amount_score
    
    return round((amount_score * 0.5) + (cadence_score * 0.5), 3)


# ============================================================
# NORMALIZATION (For Income Profile)
# ============================================================
TXN_TYPE_FALLBACK = {
    'remittance_receipt': 'remittance_agent',
    'p2p_transfer': 'grocery',
    'merchant_payment': 'grocery',
    'qr_payment': 'grocery',
    'wallet_topup': 'grocery',
}

SEASON_MONTH = {
    'spring': '03', 'summer': '06', 'monsoon': '08',
    'autumn': '10', 'winter': '01', 'dry': '02',
    'kharif': '08', 'rabi': '01', 'annual': '06',
}


def _normalize_mobile_txns(txns: list) -> tuple[list, list]:
    """Convert to income_profile format, separate future dates."""
    normalized = []
    future_flags = []
    today = datetime.now()
    
    for t in txns:
        dt = _safe_parse_date(t.get('transaction_date'))
        if not dt:
            continue
        
        is_future = dt > today
        direction = t.get('direction', 'unknown')
        category = t.get('counterparty_category', '')
        
        if not category:
            txn_type = t.get('transaction_type', '')
            category = TXN_TYPE_FALLBACK.get(txn_type, 'grocery')
        
        if is_future:
            future_flags.append({
                'transaction_id': t.get('transaction_id', 'unknown'),
                'date': t.get('transaction_date'),
                'amount': t['amount_nrs'],
                'direction': direction,
            })
            continue
        
        normalized.append({
            'date': t.get('transaction_date'),
            'amount': t['amount_nrs'],
            'type': 'CREDIT' if direction == 'credit' else 'DEBIT',
            'category': category,
            'platform': t.get('platform'),
        })
    
    return normalized, future_flags


def _normalize_coop_sales(sales: list, coop_type: str) -> list:
    """Convert cooperative sales to income_profile format."""
    if coop_type == 'savings_credit':
        return []
    
    normalized = []
    for s in sales:
        year_bs = str(s.get('sale_year_bs', '') or '')[:4]
        season = _safe_str(s.get('season'))
        month = SEASON_MONTH.get(season, '01')
        date_str = f"{year_bs}-{month}-01" if year_bs else ''
        
        normalized.append({
            'date': date_str,
            'amount': _safe_float(s.get('total_amount_nrs')),
            'type': 'CREDIT',
            'category': 'COOPERATIVE_SALES',
        })
    
    return normalized


# ============================================================
# TENURE CALCULATION
# ============================================================
def _calculate_coop_tenure_years(membership_year_bs) -> float:
    """Calculate cooperative tenure from BS year."""
    if not membership_year_bs:
        return 0.0
    try:
        membership_year = int(str(membership_year_bs)[:4])
        current_bs_year = datetime.now().year + 57
        return round(max(current_bs_year - membership_year, 0), 1)
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# INCOME ESTIMATION
# ============================================================
def _estimate_monthly_income(income_profile: dict, occupation: str) -> tuple[int, list]:
    """Estimate monthly income with floors and caps."""
    raw_income = income_profile.get("income", {}).get("total_observed_income", 0)
    estimated = _safe_int(raw_income)
    flags = []
    
    # Cap
    if estimated > MAX_INCOME:
        flags.append("INCOME_ANOMALY_HIGH")
        estimated = MAX_INCOME
    
    # Floor by occupation
    if estimated < MIN_INCOME:
        floor = OCCUPATION_FLOORS.get(occupation, MIN_INCOME)
        estimated = floor
        flags.append("INCOME_FLOOR_APPLIED")
    
    return estimated, flags


def _calculate_confidence(
    income_profile: dict,
    utility_on_time_rate: float,
    months_of_data: int
) -> float:
    """Calculate income confidence score."""
    sources = income_profile.get("sources", {})
    active_sources = len(sources)
    
    if active_sources == 0:
        return 0.05
    
    # Source confidence average
    avg_source_conf = sum(s.get("confidence_score", 0) for s in sources.values()) / active_sources
    
    # History score (cap at 6 months)
    history_score = min(months_of_data / 6, 1.0)
    
    # Base confidence
    confidence = (avg_source_conf * 0.7) + (history_score * 0.3)
    
    # Utility bonus/penalty
    if utility_on_time_rate >= 0.80:
        confidence += 0.07
    elif utility_on_time_rate < 0.50:
        confidence -= 0.10
    
    return round(max(0.0, min(1.0, confidence)), 2)


# ============================================================
# MAIN ENTRY POINT
# ============================================================
def analyze(state: AgentState) -> dict:
    """
    Income Agent entry point.
    NEVER CRASHES - always returns valid state.
    """
    applicant_id = state.get('applicant_id')
    application_id = state.get('application_id')
    
    # === VALIDATION ===
    if not applicant_id:
        logger.error("[Income Agent] No applicant_id in state")
        return {
            "status": "income_analysis_failed",
            "error": "Missing applicant_id",
            "income_agent_monthly_est": 0,
            "income_confidence": 0.0,
            "income_signal_count": 0,
            "income_signal_features": {**DEFAULT_INCOME_FEATURES, "applicant_id": ""},
            "db_write_errors": [{"table": "validation", "error": "No applicant_id"}],
        }
    
    logger.info(f"[Income Agent] Starting analysis for {applicant_id}")
    print(f"\n{'='*60}")
    print(f"[Income Agent] Starting analysis for applicant_id={applicant_id}")
    
    db_write_errors = []
    
    # === STEP 1: FETCH DATA ===
    print(f"[Income Agent] STEP 1: Fetching data...")
    db_data = _fetch_applicant_data(applicant_id)
    print(f"[Income Agent] STEP 1 DONE: fetch_counts={db_data['fetch_counts']}")
    
    # === STEP 2: CLEAN DATA ===
    print(f"[Income Agent] STEP 2: Cleaning data...")
    clean_utils = _clean_utility_data(db_data['utility_payments'])
    clean_txns = _clean_transaction_data(db_data['mobile_txns'])
    clean_rem = _clean_remittance_data(db_data['remittances'])
    
    logger.info(f"[Income Agent] Cleaned: utils={len(clean_utils)}, txns={len(clean_txns)}, rem={len(clean_rem)}")
    print(f"[Income Agent] STEP 2 DONE: utils={len(clean_utils)}, txns={len(clean_txns)}, rem={len(clean_rem)}")
    
    # === STEP 3: NORMALIZE FOR INCOME PROFILE ===
    print(f"[Income Agent] STEP 3: Normalizing data...")
    mobile_txns, future_flags = _normalize_mobile_txns(clean_txns)
    
    # Safe remittance processing
    try:
        remittances, remittance_anomalies = process_remittances(clean_rem)
    except Exception as e:
        logger.error(f"[Income Agent] Remittance processing error: {e}")
        remittances = []
        remittance_anomalies = []
    
    coop_sales = _normalize_coop_sales(db_data['coop_sales'], db_data['coop_member_type'])
    
    # === STEP 4: BUILD DERIVED SIGNALS ===
    print(f"[Income Agent] STEP 4: Building derived signals...")
    util_signals = _build_utility_signals(clean_utils)
    mobile_signals = _build_mobile_signals(clean_txns)
    rem_signals = _build_remittance_signals(clean_rem, remittances)
    print(f"[Income Agent] STEP 4 DONE")
    
    # === STEP 5: SAVE DERIVED TABLES ===
    util_signals["applicant_id"] = applicant_id
    mobile_signals["applicant_id"] = applicant_id
    rem_signals["applicant_id"] = applicant_id
    
    if not _safe_upsert("derived_utility_signals", util_signals):
        db_write_errors.append({"table": "derived_utility_signals", "error": "Upsert failed"})
    
    if not _safe_upsert("derived_mobile_payment_signals", mobile_signals):
        db_write_errors.append({"table": "derived_mobile_payment_signals", "error": "Upsert failed"})
    
    if not _safe_upsert("derived_remittance_signals", rem_signals):
        db_write_errors.append({"table": "derived_remittance_signals", "error": "Upsert failed"})
    
    # === STEP 6: GENERATE INCOME PROFILE ===
    print(f"[Income Agent] STEP 6: Generating income profile...")
    try:
        all_transactions = mobile_txns + remittances + coop_sales
        income_profile = generate_income_profile(all_transactions, {})
        print(f"[Income Agent] STEP 6 DONE: sources={len(income_profile.get('sources', {}))}")
    except Exception as e:
        logger.error(f"[Income Agent] Income profile error: {e}")
        print(f"[Income Agent] STEP 6 ERROR: {e}")
        income_profile = {"income": {"total_observed_income": 0}, "sources": {}}
    
    # === STEP 7: ESTIMATE INCOME ===
    print(f"[Income Agent] STEP 7: Estimating income...")
    occupation = db_data['occupation']
    estimated_income, income_flags = _estimate_monthly_income(income_profile, occupation)
    print(f"[Income Agent] STEP 7 DONE: estimated_income={estimated_income}, flags={income_flags}")
    
    # === STEP 8: CALCULATE CONFIDENCE ===
    print(f"[Income Agent] STEP 8: Calculating confidence...")
    months_of_data = income_profile.get("income", {}).get("months_of_data", 0)
    utility_on_time = util_signals.get("overall_on_time_rate", 0.5)
    confidence = _calculate_confidence(income_profile, utility_on_time, months_of_data)
    print(f"[Income Agent] STEP 8 DONE: confidence={confidence}")
    
    # === STEP 9: BUILD INCOME SIGNAL FEATURES ===
    coop_tenure = _calculate_coop_tenure_years(db_data['coop_membership_year_bs'])
    coop_monthly_sales = round(sum(t['amount'] for t in coop_sales) / 12) if coop_sales else 0
    
    income_signal_features = {
        "applicant_id": applicant_id,
        "income_signal_count": len(income_profile.get("sources", {})),
        "remittance_monthly_avg": rem_signals.get("remittance_monthly_avg", 0),
        "remittance_regularity_score": rem_signals.get("remittance_regularity_score", 0.0),
        "esewa_net_monthly": mobile_signals.get("esewa_net_monthly", 0),
        "esewa_tx_count_6months": mobile_signals.get("esewa_tx_count_6months", 0),
        "cooperative_monthly_sales": coop_monthly_sales,
        "utility_avg_bill_nrs": util_signals.get("utility_avg_bill_nrs", 0),
        "elec_on_time_rate": util_signals.get("elec_on_time_rate", 0.5),
        "overall_on_time_rate": util_signals.get("overall_on_time_rate", 0.5),
        "util_arrears_total_nrs": util_signals.get("util_arrears_total_nrs", 0),
        "land_area_ropani": db_data['land_area_ropani'],
        "coop_tenure_years": coop_tenure,
        "derived_income_est": estimated_income,
        "income_confidence": confidence,
    }
    print(f"[Income Agent] STEP 9 DONE: income_signal_features=")
    print(income_signal_features)
    
    # === STEP 10: SAVE INCOME SIGNAL FEATURES ===
    print(f"[Income Agent] STEP 10: Saving income_signal_features to DB...")
    try:
        db.table("income_signal_features").upsert(income_signal_features, on_conflict="applicant_id")
        print(f"[Income Agent] STEP 10 DONE: Saved successfully")
    except Exception as e:
        logger.error(f"[Income Agent] Failed to save income_signal_features: {e}")
        print(f"[Income Agent] STEP 10 ERROR: {e}")
        db_write_errors.append({"table": "income_signal_features", "error": str(e)})
    
    # === STEP 11: UPDATE LOAN APPLICATION ===
    if application_id:
        try:
            db.table("loan_applications").eq("application_id", application_id).update({
                "income_agent_monthly_est": estimated_income,
                "income_confidence": confidence,
            })
        except Exception as e:
            logger.error(f"[Income Agent] Failed to update loan_applications: {e}")
            db_write_errors.append({"table": "loan_applications", "error": str(e)})
    
    # === STEP 12: GENERATE RISK INDICATORS ===
    try:
        loan_request = state.get('loan_request', {})
        indicators = generate_risk_indicators(income_profile, {}, loan_request)
        indicators["income_flags"] = income_flags
    except Exception as e:
        logger.error(f"[Income Agent] Risk indicators error: {e}")
        indicators = {"income_flags": income_flags}
    
    # === RETURN RESULT ===
    result = {
        "status": "income_analysis_complete",
        "income_metrics": income_profile,
        "indicators": indicators,
        "income_agent_monthly_est": estimated_income,
        "income_confidence": confidence,
        "income_signal_count": len(income_profile.get("sources", {})),
        "income_signal_features": income_signal_features,
        "source_monthly": {
            "utility": util_signals,
            "mobile": mobile_signals,
            "remittance": rem_signals,
        },
        "db_write_errors": db_write_errors,
        "anomaly_flags": future_flags + remittance_anomalies,
        "debug_info": {
            "fetch_counts": db_data['fetch_counts'],
            "cleaned_counts": {
                "utility": len(clean_utils),
                "mobile": len(clean_txns),
                "remittance": len(clean_rem),
            },
            "normalized_counts": {
                "mobile": len(mobile_txns),
                "remittance": len(remittances),
                "coop_sales": len(coop_sales),
            },
        },
    }
    
    logger.info(f"[Income Agent] Complete for {applicant_id}: income={estimated_income}, conf={confidence}")
    print(f"[Income Agent] COMPLETE for {applicant_id}: income={estimated_income}, conf={confidence}")
    print(f"{'='*60}\n")
    return result