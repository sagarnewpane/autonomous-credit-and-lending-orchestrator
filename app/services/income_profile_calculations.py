from datetime import datetime
from statistics import mean, stdev
from collections import defaultdict, Counter
import re

# =========================================================
# CONFIG
# =========================================================
PRIMARY_CATEGORY = "SALARY"
SECONDARY_CATEGORIES = ["REMITTANCE", "FREELANCE", "INTEREST", "LOCAL_BUSINESS"]

DATE_FORMATS = ['%Y-%m-%d']

RISK_DISCOUNT = 0.7

FORMAL_MIN = 28
FORMAL_MAX = 31

# =========================================================
# HELPERS
# =========================================================
def parse_date(date_str):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    return None


def group_by_month(transactions):
    monthly = defaultdict(float)

    for txn in transactions:
        dt = parse_date(txn["date"])
        if not dt:
            continue

        key = dt.strftime("%Y-%m")
        monthly[key] += txn["amount"]

    return monthly


# =========================================================
# CORE METRICS
# =========================================================
def calculate_ampi(transactions):
    """Average Monthly Primary Income (SALARY only)"""
    salary_txns = [t for t in transactions if t["category"] == PRIMARY_CATEGORY]

    monthly = group_by_month(salary_txns)

    return mean(monthly.values()) if monthly else 0.0


def calculate_tmvi(transactions):
    """Total Monthly Verified Income (with risk-adjusted secondary income)"""
    ampi = calculate_ampi(transactions)

    secondary_txns = [
        t for t in transactions if t["category"] in SECONDARY_CATEGORIES
    ]

    monthly_secondary = group_by_month(secondary_txns)

    if not monthly_secondary:
        return ampi

    avg_secondary = mean(monthly_secondary.values())

    return ampi + (avg_secondary * RISK_DISCOUNT)


def calculate_volatility(transactions):
    """Coefficient of Variation (σ / μ) on SALARY"""
    salary_txns = [t for t in transactions if t["category"] == PRIMARY_CATEGORY]

    monthly = group_by_month(salary_txns)
    values = list(monthly.values())

    if len(values) < 2:
        return 0.0

    return stdev(values) / mean(values)


def calculate_cadence(transactions):
    """Average days between salary payments"""
    salary_txns = [t for t in transactions if t["category"] == PRIMARY_CATEGORY]

    dates = sorted([
        parse_date(t["date"]) for t in salary_txns if parse_date(t["date"])
    ])

    if len(dates) < 2:
        return {"avg_days": 0, "is_formal": False}

    gaps = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]

    avg_gap = mean(gaps)

    return {
        "avg_days": avg_gap,
        "is_formal": FORMAL_MIN <= avg_gap <= FORMAL_MAX,
        "gaps": gaps
    }


def calculate_dependency(transactions):
    """% of income from secondary sources"""
    primary = sum(t["amount"] for t in transactions if t["category"] == PRIMARY_CATEGORY)
    secondary = sum(t["amount"] for t in transactions if t["category"] in SECONDARY_CATEGORIES)

    total = primary + secondary

    if total == 0:
        return 0

    return (secondary / total) * 100


def get_total_months(transactions):
    """Get unique months in dataset"""
    months = set()
    for txn in transactions:
        dt = parse_date(txn["date"])
        if dt:
            months.add(dt.strftime("%Y-%m"))
    return len(sorted(months))


def calculate_monthly_wallet_volume(transactions):
    """Average monthly transaction volume through wallet platforms (eSewa, Khalti, FonePay)"""
    wallet_keywords = ['ESEWA', 'KHALTI', 'FONEPAY']
    
    wallet_txns = [
        t for t in transactions 
        if any(keyword in t.get('description', '').upper() for keyword in wallet_keywords)
    ]
    
    monthly = group_by_month(wallet_txns)
    
    return mean(monthly.values()) if monthly else 0.0


def calculate_annual_income(transactions):
    """Annualized primary income - only verified if 12+ months of data"""
    ampi = calculate_ampi(transactions)
    total_months = get_total_months(transactions)
    
    return {
        "annual_amount": round(ampi * 12, 2),
        "months_of_data": total_months,
        "is_verified_annual": total_months >= 12,
        "note": "Verified annual income" if total_months >= 12 else f"Projected annual (based on {total_months} months of data)"
    }


def calculate_monthly_unverified_inflow(transactions):
    """Average monthly inflow from unverified credit sources (e.g., UNKNOWN, TRANSFER)"""
    verified_categories = [PRIMARY_CATEGORY] + SECONDARY_CATEGORIES
    unverified_txns = [
        t for t in transactions
        if t.get("type", "").upper() == "CREDIT" and t.get("category") not in verified_categories
    ]
    
    monthly = group_by_month(unverified_txns)
    avg_monthly = mean(monthly.values()) if monthly else 0.0
    
    sources = defaultdict(float)
    for t in unverified_txns:
        cat = t.get("category", "UNKNOWN")
        sources[cat] += float(t.get("amount", 0))
        
    return {
        "amount": avg_monthly,
        "sources": dict(sources) # Totals across the entire period by category
    }


# =========================================================
# FINAL PROFILE
# =========================================================
def generate_income_profile(transactions):
    ampi = calculate_ampi(transactions)
    tmvi = calculate_tmvi(transactions)
    volatility = calculate_volatility(transactions)
    cadence = calculate_cadence(transactions)
    dependency = calculate_dependency(transactions)
    monthly_wallet = calculate_monthly_wallet_volume(transactions)
    annual_income_data = calculate_annual_income(transactions)
    unverified_data = calculate_monthly_unverified_inflow(transactions)

    return {
        "income": {
            "primary_monthly_income": round(ampi, 2),
            "total_effective_income": round(tmvi, 2),
            "secondary_contribution": round(tmvi - ampi, 2),
            "annual_income": annual_income_data["annual_amount"],
            "annual_income_months_of_data": annual_income_data["months_of_data"],
            "annual_income_verified": annual_income_data["is_verified_annual"],
            "annual_income_note": annual_income_data["note"],
            "monthly_wallet_volume": round(monthly_wallet, 2),
            "monthly_unverified_inflows": round(unverified_data["amount"], 2),
            "unverified_inflow_sources": unverified_data["sources"]
        },

        "stability": {
            "volatility_cv": round(volatility, 3),
            "payment_interval_days": round(cadence["avg_days"], 1),
            "formal_employment": cadence["is_formal"]
        },

        "composition": {
            "secondary_income_ratio_%": round(dependency, 1)
        },

        "raw": {
            "cadence_gaps": cadence.get("gaps", [])
        }
    }