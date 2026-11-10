# income_agent.py
"""
Income Agent: builds an income profile from wallet, remittance, cooperative and
utility records, and computes the declared-versus-observed income ratio (IMR).
Never raises; always returns a valid state update.
"""
import logging
from datetime import datetime
from statistics import mean, pstdev
from typing import Any, TypedDict
from app.models.state import AgentState
from app.services.income_profile_calculations import generate_income_profile
from app.services.risk_calculations import generate_risk_indicators
from app.services.remittance_processor import process_remittances
from app.services.as_of import as_of
from app.db import db

# ============================================================
# CONFIGURATION
# ============================================================
# Observed monthly income below this is flagged LOW_OBSERVED_INCOME. It is not
# replaced by an assumed figure: an earlier version imputed NPR 20,000 a month for
# farmers, which manufactured repayment capacity for the thinnest files.
LOW_OBSERVED_INCOME = 3000
# Observed monthly income above this is flagged for review, not capped.
HIGH_OBSERVED_INCOME = 200000
# The income mismatch ratio is not computed below this observed income.
IMR_MIN_OBSERVED_INCOME = 1000

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
# Fields that describe a utility bill or a remittance. Rows equal on all of them are repeats
# (Track A injects duplicates as copies with a new ID). The lists are explicit so that the
# result does not depend on which other columns a caller happens to load.
UTILITY_KEY = ("utility_type", "provider", "service_number", "billing_period_ad", "bill_amount_nrs",
               "units_consumed", "due_date_ad", "payment_date_ad", "payment_method", "days_late",
               "outstanding_arrears_nrs")
REMITTANCE_KEY = ("sender_name", "sender_country_code", "sender_city", "transfer_service", "transfer_date_ad",
                  "received_date_ad", "amount_foreign_currency", "foreign_currency_code", "amount_nrs",
                  "exchange_rate", "transaction_fee_nrs", "disbursement_mode")


def _drop_repeats(records: list, key_fields: tuple) -> list:
    """
    Drop rows that repeat an earlier row on every field in key_fields.

    The generator's `_noise_*` columns are never used: they are labels a lender would not
    have (the organisers remove them from their hidden test split).
    """
    seen, out = set(), []
    for r in records:
        key = tuple(str(r.get(k)) for k in key_fields)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _clean_utility_data(records: list) -> list:
    """Utility bills: drop repeated rows, use the absolute bill amount, and treat a bill with
    no payment record as not paid on time. No generator noise labels are used."""
    cleaned = []
    for r in _drop_repeats(records, UTILITY_KEY):
        cleaned.append({
            'applicant_id': r.get('applicant_id'),
            'bill_amount_nrs': abs(_safe_float(r.get('bill_amount_nrs'))),
            'payment_date_ad': r.get('payment_date_ad'),
            'days_late': _safe_float(r.get('days_late'), 1),  # unpaid bills have no days_late: late
            'outstanding_arrears_nrs': _safe_float(r.get('outstanding_arrears_nrs')),
        })
    return cleaned


def _clean_transaction_data(records: list) -> list:
    """Wallet transactions: parse amounts stored as comma-formatted strings. Nothing is
    dropped here; records dated after the as-of date are set aside in _normalize_mobile_txns.
    No generator noise labels are used."""
    cleaned = []
    for r in records:
        cleaned.append({
            'applicant_id': r.get('applicant_id'),
            'transaction_id': r.get('transaction_id'),
            'transaction_date': r.get('transaction_date'),
            'amount_nrs': _safe_float(r.get('amount_nrs', 0)),
            'direction': _safe_str(r.get('direction'), 'unknown'),
            'counterparty_category': _safe_str(r.get('counterparty_category'), 'unknown'),
            'transaction_type': _safe_str(r.get('transaction_type')),
            'platform': _safe_str(r.get('platform')),
        })
    return cleaned


def _clean_remittance_data(records: list) -> list:
    """Remittance records: drop repeated rows. process_remittances() then checks exchange
    rates, currencies and amounts against reference values. No generator noise labels are used."""
    cleaned = []
    for r in _drop_repeats(records, REMITTANCE_KEY):
        amount = _safe_float(r.get('amount_nrs'))
        rate = _safe_float(r.get('exchange_rate'))
        foreign_amount = _safe_float(r.get('amount_foreign_currency'))

        # Keep the transfer date and identifiers: process_remittances() validates and
        # normalises on transfer_date_ad. An earlier version kept only a non-existent
        # 'date' field, so every remittance lost its month and dropped out of the profile.
        transfer_date = r.get('transfer_date_ad') or r.get('date')
        cleaned.append({
            'applicant_id': r.get('applicant_id'),
            'remittance_id': r.get('remittance_id'),
            'date': transfer_date,
            'transfer_date_ad': transfer_date,
            'received_date_ad': r.get('received_date_ad'),
            'sender_country_code': r.get('sender_country_code') or '',
            'foreign_currency_code': r.get('foreign_currency_code') or '',
            'name_match_score': r.get('name_match_score'),
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
    
    valid_utils = clean_utils
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
# Wallet credits are grouped by transaction type. (An earlier version grouped them by
# counterparty_category, which in Track A is unrelated to the transaction type, so a wallet
# top-up could become "telecom" or "grocery" income.)
WALLET_CREDIT_SOURCE = {
    'remittance_receipt': 'remittance_agent',
    'wallet_topup': 'wallet_topup',
}

SEASON_MONTH = {
    'spring': '03', 'summer': '06', 'monsoon': '08',
    'autumn': '10', 'winter': '01', 'dry': '02',
    'kharif': '08', 'rabi': '01', 'annual': '06',
}


def _normalize_mobile_txns(txns: list) -> tuple[list, list]:
    """Convert to income_profile format; set aside records dated after the as-of date."""
    normalized = []
    future_flags = []
    now = as_of()

    for t in txns:
        dt = _safe_parse_date(t.get('transaction_date'))
        if not dt:
            continue
        direction = t.get('direction', 'unknown')
        if dt > now:
            future_flags.append({
                'transaction_id': t.get('transaction_id', 'unknown'),
                'date': t.get('transaction_date'),
                'amount': t['amount_nrs'],
                'direction': direction,
            })
            continue
        txn_type = (t.get('transaction_type') or '').strip().lower()
        normalized.append({
            'date': t.get('transaction_date'),
            'amount': t['amount_nrs'],
            'type': 'CREDIT' if direction == 'credit' else 'DEBIT',
            'category': WALLET_CREDIT_SOURCE.get(txn_type, 'other_wallet_inflows'),
            'platform': t.get('platform'),
        })

    return normalized, future_flags


def _coop_source_profile(sales: list, coop_type: str) -> dict | None:
    """
    Cooperative sales as an annual income source.

    Sales are recorded by Bikram Sambat year and season, not by date, so they are kept out
    of the monthly window used for wallet and remittance inflows. Monthly income is the
    average annual sales divided by 12. (An earlier version turned BS years into Gregorian
    dates, which widened the monthly window to several years and summed all years' sales
    as one year's.) Savings-and-credit cooperatives carry no sales income.
    """
    if coop_type == 'savings_credit' or not sales:
        return None
    by_year: dict = {}
    for s in sales:
        year = str(s.get('sale_year_bs', '') or '')[:4]
        amount = _safe_float(s.get('total_amount_nrs'))
        if year and amount > 0:
            by_year[year] = by_year.get(year, 0.0) + amount
    if not by_year:
        return None
    annual = list(by_year.values())
    annual_mean = mean(annual)
    cv = (pstdev(annual) / annual_mean) if (len(annual) > 1 and annual_mean > 0) else 0.0
    monthly = annual_mean / 12.0
    return {
        "source_type": "COOPERATIVE_SALES",
        "description": "Agricultural or commodity sales via cooperative",
        "monthly_average_raw": round(monthly, 2),
        "monthly_usable_income": round(monthly, 2),
        "confidence_score": 0.70,
        "stability_score": round(max(0.0, min(1.0, 1.0 - min(cv, 1.0))), 3),
        "volatility_cv": round(cv, 3),
        "months_active": 12,          # annual source: treated as active across the year
        "months_observed": 12,
        "years_observed": len(annual),
        "recurrence_ratio": 1.0,
        "transaction_count": len(sales),
        "verification_notes": [f"Cooperative sales across {len(annual)} BS year(s)"],
    }


def _merge_coop_source(income_profile: dict, coop_profile: dict | None) -> dict:
    """Add the cooperative source to a profile built from monthly inflows."""
    if not coop_profile:
        return income_profile
    sources = dict(income_profile.get("sources", {}))
    sources["COOPERATIVE_SALES"] = coop_profile
    income = dict(income_profile.get("income", {}))
    total = sum(_safe_float(p.get("monthly_usable_income")) for p in sources.values())
    primary = max(sources.values(), key=lambda p: _safe_float(p.get("monthly_usable_income")))
    income["total_observed_income"] = round(total, 2)
    income["primary_income_source"] = primary["source_type"]
    income["primary_income_amount"] = primary["monthly_usable_income"]
    informal = sum(_safe_float(p.get("monthly_usable_income")) for k, p in sources.items() if k != "financial_services")
    composition = dict(income_profile.get("composition", {}))
    composition["informal_income_ratio_%"] = round(informal / total * 100, 1) if total > 0 else 0.0
    return {**income_profile, "income": income, "sources": sources, "composition": composition}


# ============================================================
# TENURE CALCULATION
# ============================================================
def _calculate_coop_tenure_years(membership_year_bs, reference_bs_year: int | None = None) -> float:
    """Years of cooperative membership up to reference_bs_year (default: the current BS year)."""
    if not membership_year_bs:
        return 0.0
    try:
        membership_year = int(str(membership_year_bs)[:4])
        current = int(reference_bs_year) if reference_bs_year else as_of().year + 57
        return round(max(current - membership_year, 0), 1)
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# INCOME ESTIMATION
# ============================================================
def _estimate_monthly_income(income_profile: dict) -> tuple[int, list]:
    """Observed monthly income, with flags. No floors or caps are applied."""
    estimated = _safe_int(income_profile.get("income", {}).get("total_observed_income", 0))
    flags = []
    if estimated > HIGH_OBSERVED_INCOME:
        flags.append("INCOME_ANOMALY_HIGH")
    if estimated < LOW_OBSERVED_INCOME:
        flags.append("LOW_OBSERVED_INCOME")
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
# DECLARED-VERSUS-OBSERVED INCOME (IMR)
# ============================================================
def compute_imr(declared_monthly_income: Any, observed_monthly_income: Any) -> tuple:
    """
    Income mismatch ratio: declared monthly income divided by observed monthly income.

    Returns (imr, status). status is:
      "not_declared"           no declared income was supplied, IMR not computed
      "insufficient_observed"  observed income is below IMR_MIN_OBSERVED_INCOME
      "computed"               imr holds the ratio
    The ratio is a consistency signal for manual review, never a rejection reason
    on its own; thresholds live in config/policy_rules.yaml (rule INCOME_MISMATCH).
    """
    if declared_monthly_income in (None, ""):
        return None, "not_declared"
    declared = _safe_float(declared_monthly_income)
    if declared <= 0:
        return None, "not_declared"
    observed = _safe_float(observed_monthly_income)
    if observed < IMR_MIN_OBSERVED_INCOME:
        return None, "insufficient_observed"
    return round(declared / observed, 3), "computed"


# ============================================================
# PURE COMPUTATION (no database access)
# ============================================================
def compute_income_assessment(db_data: dict, loan_request: dict | None = None) -> dict:
    """
    Run every Income Agent step that does not touch the database.

    db_data has the shape returned by _fetch_applicant_data. The same function is
    used by the live node (analyze) and by the batch experiments, so features seen
    in training and in serving come from one code path.
    """
    loan_request = loan_request or {}

    clean_utils = _clean_utility_data(db_data.get('utility_payments', []))
    clean_txns = _clean_transaction_data(db_data.get('mobile_txns', []))
    clean_rem = _clean_remittance_data(db_data.get('remittances', []))

    mobile_txns, future_flags = _normalize_mobile_txns(clean_txns)
    try:
        remittances, remittance_anomalies = process_remittances(clean_rem)
    except Exception as e:
        logger.error(f"[Income Agent] Remittance processing error: {e}")
        remittances, remittance_anomalies = [], []
    coop_profile = _coop_source_profile(db_data.get('coop_sales', []), db_data.get('coop_member_type', ''))

    util_signals = _build_utility_signals(clean_utils)
    mobile_signals = _build_mobile_signals(clean_txns)
    rem_signals = _build_remittance_signals(clean_rem, remittances)

    try:
        income_profile = generate_income_profile(mobile_txns + remittances, {})
    except Exception as e:
        logger.error(f"[Income Agent] Income profile error: {e}")
        income_profile = {"income": {"total_observed_income": 0}, "sources": {}}
    income_profile = _merge_coop_source(income_profile, coop_profile)

    estimated_income, income_flags = _estimate_monthly_income(income_profile)
    months_of_data = income_profile.get("income", {}).get("months_of_data", 0)
    confidence = _calculate_confidence(
        income_profile, util_signals.get("overall_on_time_rate", 0.5), months_of_data
    )

    sources = income_profile.get("sources", {})
    total_observed = _safe_float(income_profile.get("income", {}).get("total_observed_income"))
    remittance_income = _safe_float(sources.get("remittance_agent", {}).get("monthly_usable_income"))
    remittance_share = round(remittance_income / total_observed, 3) if total_observed > 0 else 0.0

    coop_tenure = _calculate_coop_tenure_years(db_data.get('coop_membership_year_bs'), db_data.get('reference_bs_year'))
    coop_monthly_sales = round(coop_profile["monthly_usable_income"]) if coop_profile else 0

    income_signal_features = {
        "income_signal_count": len(sources),
        "remittance_monthly_avg": rem_signals.get("remittance_monthly_avg", 0),
        "remittance_regularity_score": rem_signals.get("remittance_regularity_score", 0.0),
        "esewa_net_monthly": mobile_signals.get("esewa_net_monthly", 0),
        "esewa_tx_count_6months": mobile_signals.get("esewa_tx_count_6months", 0),
        "cooperative_monthly_sales": coop_monthly_sales,
        "utility_avg_bill_nrs": util_signals.get("utility_avg_bill_nrs", 0),
        "elec_on_time_rate": util_signals.get("elec_on_time_rate", 0.5),
        "overall_on_time_rate": util_signals.get("overall_on_time_rate", 0.5),
        "util_arrears_total_nrs": util_signals.get("util_arrears_total_nrs", 0),
        "land_area_ropani": db_data.get('land_area_ropani', 0),
        "coop_tenure_years": coop_tenure,
        "derived_income_est": estimated_income,
        "income_confidence": confidence,
    }

    declared = loan_request.get('declared_monthly_income')
    imr, imr_status = compute_imr(declared, estimated_income)

    try:
        indicators = generate_risk_indicators(income_profile, {}, loan_request)
    except Exception as e:
        logger.error(f"[Income Agent] Risk indicators error: {e}")
        indicators = {}
    indicators["income_flags"] = income_flags

    return {
        "estimated_income": estimated_income,
        "income_flags": income_flags,
        "confidence": confidence,
        "months_of_data": months_of_data,
        "income_profile": income_profile,
        "income_signal_features": income_signal_features,
        "signals": {"utility": util_signals, "mobile": mobile_signals, "remittance": rem_signals},
        "indicators": indicators,
        "declared_monthly_income": _safe_float(declared) if declared not in (None, "") else None,
        "imr": imr,
        "imr_status": imr_status,
        "remittance_share": remittance_share,
        "anomaly_flags": future_flags + remittance_anomalies,
        "counts": {
            "cleaned_counts": {"utility": len(clean_utils), "mobile": len(clean_txns), "remittance": len(clean_rem)},
            "normalized_counts": {"mobile": len(mobile_txns), "remittance": len(remittances),
                                  "coop_sales": coop_profile["transaction_count"] if coop_profile else 0},
        },
    }


def _application_bs_year(application_id: str | None) -> int | None:
    """BS year of the application date, so membership tenure does not drift with the clock."""
    if not application_id:
        return None
    try:
        row = db.table('loan_applications').select('application_date_bs') \
            .eq('application_id', application_id).single().execute().data or {}
        value = str(row.get('application_date_bs') or '')[:4]
        return int(value) if value.isdigit() else None
    except Exception:
        return None


# ============================================================
# MAIN ENTRY POINT
# ============================================================
def analyze(state: AgentState) -> dict:
    """
    Income Agent entry point: fetch, compute, persist.
    Never raises; always returns a valid state update.
    """
    applicant_id = state.get('applicant_id')
    application_id = state.get('application_id')

    if not applicant_id:
        logger.error("[Income Agent] No applicant_id in state")
        return {
            "status": "income_analysis_failed",
            "errors": ["Missing applicant_id"],
            "income_agent_monthly_est": 0,
            "income_confidence": 0.0,
            "income_signal_count": 0,
            "income_signal_features": {**DEFAULT_INCOME_FEATURES, "applicant_id": ""},
            "imr": None,
            "imr_status": "not_declared",
            "db_write_errors": [{"table": "validation", "error": "No applicant_id"}],
        }

    logger.info(f"[Income Agent] Starting analysis for {applicant_id}")
    db_write_errors = []

    db_data = _fetch_applicant_data(applicant_id)
    db_data['reference_bs_year'] = _application_bs_year(application_id)
    a = compute_income_assessment(db_data, state.get('loan_request', {}) or {})

    for table, signals in (
        ("derived_utility_signals", a["signals"]["utility"]),
        ("derived_mobile_payment_signals", a["signals"]["mobile"]),
        ("derived_remittance_signals", a["signals"]["remittance"]),
    ):
        if not _safe_upsert(table, {**signals, "applicant_id": applicant_id}):
            db_write_errors.append({"table": table, "error": "Upsert failed"})

    features = {"applicant_id": applicant_id, **a["income_signal_features"]}
    try:
        db.table("income_signal_features").upsert(features, on_conflict="applicant_id")
    except Exception as e:
        logger.error(f"[Income Agent] Failed to save income_signal_features: {e}")
        db_write_errors.append({"table": "income_signal_features", "error": str(e)})

    if application_id:
        try:
            db.table("loan_applications").eq("application_id", application_id).update({
                "income_agent_monthly_est": a["estimated_income"],
                "income_confidence": a["confidence"],
            })
        except Exception as e:
            logger.error(f"[Income Agent] Failed to update loan_applications: {e}")
            db_write_errors.append({"table": "loan_applications", "error": str(e)})

    logger.info(
        f"[Income Agent] Complete for {applicant_id}: income={a['estimated_income']}, "
        f"conf={a['confidence']}, imr={a['imr']} ({a['imr_status']})"
    )
    return {
        "status": "income_analysis_complete",
        "income_metrics": a["income_profile"],
        "indicators": a["indicators"],
        "income_agent_monthly_est": a["estimated_income"],
        "income_confidence": a["confidence"],
        "income_signal_count": len(a["income_profile"].get("sources", {})),
        "income_signal_features": features,
        "source_monthly": a["signals"],
        "declared_monthly_income": a["declared_monthly_income"],
        "imr": a["imr"],
        "imr_status": a["imr_status"],
        "remittance_share": a["remittance_share"],
        "db_write_errors": db_write_errors,
        "anomaly_flags": a["anomaly_flags"],
        "income_flags": a["income_flags"],
        "debug_info": {"fetch_counts": db_data['fetch_counts'], **a["counts"]},
    }
