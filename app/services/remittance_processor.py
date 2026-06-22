"""
Remittance Processor
====================
Standalone module for cleaning, validating, and scoring remittance records.
"""

import hashlib
from datetime import datetime

# (min_rate, max_rate, default_rate) — valid ranges per currency
REFERENCE_RATES = {
    "QA": (35.0, 43.0, 39.0),    # Qatar Riyal
    "SA": (31.0, 40.0, 35.5),    # Saudi Riyal
    "AE": (33.0, 41.0, 36.8),    # UAE Dirham
    "MY": (26.0, 33.0, 29.5),    # Malaysian Ringgit
    "IN": (1.4, 1.8, 1.6),       # Indian Rupee
    "KR": (0.15, 0.22, 0.18),    # South Korean Won (per 1000)
    "US": (120.0, 145.0, 133.5), # US Dollar
    "JP": (0.75, 1.05, 0.89),    # Japanese Yen (per 100)
}

CURRENCY_MAP = {
    "QA": "QAR", "SA": "SAR", "AE": "AED", "MY": "MYR",
    "IN": "INR", "KR": "KRW", "US": "USD", "JP": "JPY",
}

def _row_hash(record: dict) -> str:
    """Hash full row content for exact dedup."""
    content = "|".join(str(record.get(k, "")) for k in sorted(record.keys()))
    return hashlib.md5(content.encode()).hexdigest()

def _clean_amount(val) -> float:
    if isinstance(val, str):
        return float(val.replace(",", ""))
    return float(val or 0)

def _parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(date_str).split(".")[0], fmt)
        except ValueError:
            continue
    return None

def _validate_dates(record: dict) -> tuple[dict, str | None]:
    """Check for future dates and logical date mismatches."""
    transfer_date = _parse_date(record.get("transfer_date_ad"))
    received_date = _parse_date(record.get("received_date_ad"))
    
    if transfer_date and transfer_date > datetime.now():
        return record, "FUTURE_DATE"
        
    if transfer_date and received_date and received_date < transfer_date:
        return record, "DATE_MISMATCH"
        
    return record, None

def _validate_exchange_rate(record: dict) -> tuple[dict, str | None]:
    country = record.get("sender_country_code", "").upper()
    rate = _clean_amount(record.get("exchange_rate", 0))
    foreign_amount = _clean_amount(record.get("amount_foreign_currency", 0))

    if country not in REFERENCE_RATES:
        return record, None

    min_rate, max_rate, default_rate = REFERENCE_RATES[country]

    if rate < min_rate or rate > max_rate:
        record["amount_nrs"] = round(foreign_amount * default_rate, 2)
        record["exchange_rate"] = default_rate
        return record, "IMPOSSIBLE_RATE"

    return record, None

def _validate_currency(record: dict) -> tuple[dict, str | None]:
    country = record.get("sender_country_code", "").upper()
    currency = record.get("foreign_currency_code", "").upper()

    if country in CURRENCY_MAP and currency != CURRENCY_MAP[country]:
        return record, "WRONG_CURRENCY"

    return record, None

def _validate_amount(record: dict) -> tuple[dict, str | None]:
    country = record.get("sender_country_code", "").upper()
    foreign_amount = _clean_amount(record.get("amount_foreign_currency", 0))
    amount_nrs = _clean_amount(record.get("amount_nrs", 0))
    rate = _clean_amount(record.get("exchange_rate", 0))

    if foreign_amount <= 0 or rate <= 0:
        return record, None

    expected_nrs = foreign_amount * rate
    if expected_nrs > 0 and abs(amount_nrs - expected_nrs) / expected_nrs > 0.1:
        if country in REFERENCE_RATES:
            default_rate = REFERENCE_RATES[country][2]
            record["amount_nrs"] = round(foreign_amount * default_rate, 2)
            record["exchange_rate"] = default_rate
        return record, "AMOUNT_MISMATCH"

    return record, None

def _score_name_match(record: dict) -> tuple[dict, str | None]:
    """Check DB name_match_score. Returns flag if < 0.80."""
    score = record.get("name_match_score")
    score_float = float(score) if score is not None else 1.0
    if score_float < 0.80:
        return record, "NAME_CORRUPT"
    return record, None

def _normalize(record: dict) -> dict:
    return {
        "date": record.get("transfer_date_ad", ""),
        "amount": abs(_clean_amount(record.get("amount_nrs", 0))),
        "type": "CREDIT",
        "category": "remittance_agent",
    }

def process_remittances(records: list) -> tuple[list[dict], list[dict]]:
    """
    Clean, validate, and score remittance records.
    """
    normalized = []
    anomalies = []
    
    seen_row_hashes = set()
    seen_rem_ids = set()

    for r in records:
        # 1. Exact row dedup
        row_hash = _row_hash(r)
        if row_hash in seen_row_hashes:
            continue
        seen_row_hashes.add(row_hash)

        # 2. Remittance ID dedup
        rem_id = r.get("remittance_id")
        if rem_id and rem_id in seen_rem_ids:
            continue
        if rem_id:
            seen_rem_ids.add(rem_id)

        record = dict(r)  
        record_anomalies = []

        # 3. Date validation (Future + Mismatch)
        record, flag = _validate_dates(record)
        if flag:
            record_anomalies.append(flag)

        # 4. Exchange rate validation
        record, flag = _validate_exchange_rate(record)
        if flag:
            record_anomalies.append(flag)

        # 5. Currency validation
        record, flag = _validate_currency(record)
        if flag:
            record_anomalies.append(flag)

        # 6. Amount cross-field check
        record, flag = _validate_amount(record)
        if flag:
            record_anomalies.append(flag)

        # 7. Name match check (using DB score)
        record, flag = _score_name_match(record)
        if flag:
            record_anomalies.append(flag)

        # 8. Normalize to income format
        normalized_record = _normalize(record)
        normalized.append(normalized_record)

        # 9. Collect anomalies
        if record_anomalies:
            anomalies.append({
                "remittance_id": rem_id,
                "flags": record_anomalies,
                "sender_country": record.get("sender_country_code"),
                "amount_nrs_original": r.get("amount_nrs"),
                "amount_nrs_cleaned": record.get("amount_nrs"),
            })

    return normalized, anomalies