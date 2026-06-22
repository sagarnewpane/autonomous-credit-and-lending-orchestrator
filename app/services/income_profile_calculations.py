# income_profile_calculations.py
from collections import defaultdict
from datetime import datetime
from statistics import mean, median

# Handle both Date and Timestamp formats
DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
REFERENCE_MONTHS = 6  # Dataset explicitly covers 6 months (Jan-June 2024)

SOURCE_CONFIG = {
    "remittance_agent": {
        "normalizer": "average_all_months",
        "base_confidence": 0.8,
        "requires_recurrence": True,
        "description": "Household support or inward remittance",
    },
    "COOPERATIVE_SALES": {
        "normalizer": "seasonal_average",
        "base_confidence": 0.70,
        "requires_recurrence": False,
        "description": "Agricultural or commodity sales via cooperative",
    },
    "agriculture_input": {
        "normalizer": "rolling_average",
        "base_confidence": 0.65,
        "requires_recurrence": True,
        "description": "Merchant inflows from agriculture",
    },
    "grocery": {
        "normalizer": "rolling_average",
        "base_confidence": 0.75,
        "requires_recurrence": True,
        "description": "Merchant or shop inflows",
    },
    "restaurant": {
        "normalizer": "rolling_average",
        "base_confidence": 0.75,
        "requires_recurrence": True,
        "description": "Food service inflows",
    },
    "financial_services": {
        "normalizer": "average_all_months",
        "base_confidence": 0.9,
        "requires_recurrence": False,
        "description": "Passive bank interest or financial inflows",
    },
    "medical": {
        "normalizer": "rolling_average",
        "base_confidence": 0.7,
        "requires_recurrence": True,
        "description": "Medical service income",
    },
    "transport": {
        "normalizer": "rolling_average",
        "base_confidence": 0.7,
        "requires_recurrence": True,
        "description": "Transport service income",
    },
    "telecom": {
        "normalizer": "rolling_average",
        "base_confidence": 0.7,
        "requires_recurrence": True,
        "description": "Telecom service income",
    },
    "education": {
        "normalizer": "rolling_average",
        "base_confidence": 0.7,
        "requires_recurrence": True,
        "description": "Education service income",
    },
    "utility": {
        "normalizer": "rolling_average",
        "base_confidence": 0.6,
        "requires_recurrence": True,
        "description": "Utility service income",
    },
}

def parse_date(date_str):
    if not date_str: return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(date_str).split(".")[0], fmt)
        except Exception:
            continue
    return None

def get_all_months(transactions):
    months = {
        parsed.strftime("%Y-%m")
        for txn in transactions
        if (parsed := parse_date(txn.get("date")))
    }
    return sorted(months)

def build_monthly_series(transactions, months):
    monthly = {month: 0.0 for month in months}
    for txn in transactions:
        parsed = parse_date(txn.get("date"))
        if not parsed:
            continue
        monthly[parsed.strftime("%Y-%m")] += float(txn.get("amount", 0.0))
    return monthly

def calculate_volatility(values):
    non_zero = [value for value in values if value > 0]
    if len(non_zero) < 2:
        return 0.0
    avg = mean(non_zero)
    if avg == 0:
        return 0.0
    variance = sum((value - avg) ** 2 for value in non_zero) / (len(non_zero) - 1)
    return (variance ** 0.5) / avg

def clamp(value, minimum=0.0, maximum=1.0):
    return max(minimum, min(maximum, value))

def normalize_monthly_income(values, normalizer):
    active = [value for value in values if value > 0]
    if not values or not active:
        return 0.0

    if normalizer == "median_active":
        return median(active)
    if normalizer == "rolling_average":
        return mean(values[-3:])
    if normalizer == "seasonal_average":
        return sum(values) / 12.0
    return mean(values)

def build_verification_notes(source_name, recurrence_ratio, volatility):
    notes = []
    if recurrence_ratio >= 0.75:
        notes.append(f"{source_name.title().replace('_', ' ')} appears recurring across observed months")
    elif recurrence_ratio > 0:
        notes.append(f"{source_name.title().replace('_', ' ')} appears intermittent rather than fully recurring")

    if volatility <= 0.15 and recurrence_ratio > 0:
        notes.append("Cash flow is relatively stable")
    elif volatility >= 0.5:
        notes.append("Cash flow is volatile and should be discounted")

    if source_name == "COOPERATIVE_SALES":
        notes.append("Agriculture income is seasonally smoothed (Annual / 12) before use")
    if source_name == "remittance_agent":
        notes.append("Remittance is averaged across the full observation window")
    if source_name in ("grocery", "restaurant"):
        notes.append("Business inflows use a rolling average to reduce one-off spikes")

    return notes

def calculate_source_profile(category, transactions, months, extracted_docs):
    config = SOURCE_CONFIG[category]
    monthly = build_monthly_series(transactions, months)
    values = list(monthly.values())
    active_values = [value for value in values if value > 0]
    total_months = len(months) or 1
    active_months = len(active_values)

    normalized_income = normalize_monthly_income(values, config["normalizer"])
    recurrence_ratio = active_months / total_months if total_months else 0.0
    volatility = calculate_volatility(values)
    avg_confidence = mean(
        float(txn.get("category_confidence", config["base_confidence"])) for txn in transactions
    ) if transactions else 0.0

    confidence_score = clamp((avg_confidence + config["base_confidence"]) / 2)
    recurrence_score = recurrence_ratio if config["requires_recurrence"] else max(recurrence_ratio, 0.45)
    stability_score = clamp((0.6 * recurrence_score) + (0.4 * (1 - min(volatility, 1.0))))

    # Fix: Divide total raw income by the standard 6-month window
    total_income = sum(values)
    monthly_average_raw = round(total_income / REFERENCE_MONTHS, 2)

    return {
        "source_type": category,
        "description": config["description"],
        "monthly_average_raw": monthly_average_raw,
        "monthly_usable_income": round(normalized_income, 2),
        "confidence_score": round(confidence_score, 3),
        "stability_score": round(stability_score, 3),
        "volatility_cv": round(volatility, 3),
        "months_active": active_months,
        "months_observed": total_months,
        "recurrence_ratio": round(recurrence_ratio, 3),
        "transaction_count": len(transactions),
        "verification_notes": build_verification_notes(category, recurrence_ratio, volatility),
    }

def generate_income_profile(transactions, extracted_docs=None):
    extracted_docs = extracted_docs or {}

    credit_transactions = [txn for txn in transactions if txn.get("type", "").upper() == "CREDIT"]
    months = get_all_months(credit_transactions)

    categorized = defaultdict(list)
    uncategorized_inflows = []

    for txn in credit_transactions:
        category = txn.get("category", "UNKNOWN")
        if category in SOURCE_CONFIG:
            categorized[category].append(txn)
        else:
            uncategorized_inflows.append(txn)

    source_profiles = {}
    for category in SOURCE_CONFIG:
        if categorized.get(category):
            source_profiles[category] = calculate_source_profile(
                category,
                categorized[category],
                months,
                extracted_docs,
            )

    # Total observed income
    total_observed_income = sum(profile["monthly_usable_income"] for profile in source_profiles.values())
    
    primary_source = max(
        source_profiles.values(),
        key=lambda profile: profile["monthly_usable_income"],
        default=None,
    )

    uncategorized_monthly = 0.0
    if uncategorized_inflows and months:
        uncategorized_monthly = round(sum(float(txn.get("amount", 0.0)) for txn in uncategorized_inflows) / len(months), 2)

    return {
        "income": {
            "total_observed_income": round(total_observed_income, 2),
            "primary_income_source": primary_source["source_type"] if primary_source else None,
            "primary_income_amount": primary_source["monthly_usable_income"] if primary_source else 0.0,
            "monthly_unverified_inflows": uncategorized_monthly,
            "months_of_data": len(months),
        },
        "sources": source_profiles,
        "composition": {
            "informal_income_ratio_%": round(
                (
                    sum(
                        profile["monthly_usable_income"]
                        for source, profile in source_profiles.items()
                        if source != "financial_services"
                    ) / total_observed_income
                ) * 100,
                1,
            ) if total_observed_income > 0 else 0.0
        },
    }