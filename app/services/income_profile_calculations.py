# from datetime import datetime
# from statistics import mean, stdev
# from collections import defaultdict, Counter
# import re
# from data.income_data import CreditCategory

# # ============================================================================
# # CONFIGURATION
# # ============================================================================

# PRIMARY_INCOME_CATEGORIES = ['SALARY']

# SECONDARY_INCOME_CATEGORIES = [
#     'REMITTANCE',
#     'FREELANCE',
#     'INTEREST',
#     'INVESTMENT_RETURN'
# ]

# DEFAULT_SECONDARY_INCOME_RISK_DISCOUNT = 0.7

# DATE_FORMATS = ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y']

# FORMAL_EMPLOYMENT_CADENCE_MIN_DAYS = 26
# FORMAL_EMPLOYMENT_CADENCE_MAX_DAYS = 35

# DEPENDENCY_RATIO_VULNERABLE_THRESHOLD = 50

# VOLATILITY_THRESHOLDS = {
#     'very_stable': 0.1,
#     'stable': 0.25,
#     'moderate': 0.5,
#     'high': 1.0,
# }

# BANK_PREFIXES_REGEX = r'^(POS TRN FROM:|FONEPAY::|NABIL/|SALARY FROM:|IPS::SALARY/)'
# EMPLOYER_NAME_DELIMITERS = r'[,\-/\|]'
# MIN_EMPLOYER_NAME_LENGTH = 2


# # ============================================================================
# # HELPERS
# # ============================================================================

# def _parse_date(date_str):
#     for fmt in DATE_FORMATS:
#         try:
#             return datetime.strptime(date_str, fmt)
#         except:
#             continue
#     return None


# def _get_total_months(transactions):
#     months = set()
#     for txn in transactions:
#         d = _parse_date(txn.get('date', ''))
#         if d:
#             months.add(d.strftime('%Y-%m'))
#     return len(months)


# # ============================================================================
# # CORE METRICS
# # ============================================================================

# def calculate_ampi(transactions):
#     salary_txns = [t for t in transactions if t.get('category') == 'SALARY']

#     monthly = defaultdict(float)
#     for txn in salary_txns:
#         d = _parse_date(txn.get('date'))
#         if not d:
#             continue
#         monthly[d.strftime('%Y-%m')] += float(txn.get('amount', 0))

#     return mean(monthly.values()) if monthly else 0.0


# def calculate_tmvi(transactions, risk_discount=DEFAULT_SECONDARY_INCOME_RISK_DISCOUNT):
#     ampi = calculate_ampi(transactions)

#     total_months = _get_total_months(transactions)
#     if total_months == 0:
#         return ampi

#     secondary_txns = [
#         t for t in transactions
#         if t.get('category') in SECONDARY_INCOME_CATEGORIES
#     ]

#     total_secondary = sum(float(t.get('amount', 0)) for t in secondary_txns)
#     avg_secondary = total_secondary / total_months

#     return ampi + (avg_secondary * risk_discount)


# def calculate_income_dependency_ratio(transactions):
#     primary = sum(float(t.get('amount', 0)) for t in transactions if t.get('category') == 'SALARY')

#     secondary = sum(float(t.get('amount', 0)) for t in transactions if t.get('category') in SECONDARY_INCOME_CATEGORIES)

#     total = primary + secondary

#     if total == 0:
#         return {'dependency_ratio': 0, 'is_vulnerable': False}

#     ratio = (secondary / total) * 100

#     return {
#         'dependency_ratio': ratio,
#         'is_vulnerable': ratio > DEPENDENCY_RATIO_VULNERABLE_THRESHOLD
#     }


# def calculate_income_volatility(transactions):
#     salary_txns = [t for t in transactions if t.get('category') == 'SALARY']

#     monthly = defaultdict(float)
#     for txn in salary_txns:
#         d = _parse_date(txn.get('date'))
#         if not d:
#             continue
#         monthly[d.strftime('%Y-%m')] += float(txn.get('amount', 0))

#     values = list(monthly.values())

#     if len(values) < 2:
#         return 0.0

#     return stdev(values) / mean(values)


# def calculate_income_cadence(transactions):
#     salary_txns = [t for t in transactions if t.get('category') == 'SALARY']

#     dates = sorted([_parse_date(t.get('date')) for t in salary_txns if _parse_date(t.get('date'))])

#     if len(dates) < 2:
#         return {'average_days': 0, 'is_formal_employment': False}

#     gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
#     avg = mean(gaps)

#     return {
#         'average_days': avg,
#         'is_formal_employment': FORMAL_EMPLOYMENT_CADENCE_MIN_DAYS <= avg <= FORMAL_EMPLOYMENT_CADENCE_MAX_DAYS
#     }


# def calculate_employer_concentration(transactions):
#     salary_txns = [t for t in transactions if t.get('category') == 'SALARY']

#     employers = []

#     for txn in salary_txns:
#         desc = txn.get('description', '')
#         desc = re.sub(BANK_PREFIXES_REGEX, '', desc).strip()
#         emp = re.split(EMPLOYER_NAME_DELIMITERS, desc)[0].strip()

#         if len(emp) > MIN_EMPLOYER_NAME_LENGTH:
#             employers.append(emp.upper())

#     if not employers:
#         return {'unique_employers': 0, 'concentration': 0}

#     counts = Counter(employers)
#     max_share = max(counts.values()) / len(employers)

#     return {
#         'unique_employers': len(counts),
#         'concentration': max_share
#     }


# def calculate_income_diversity(transactions):
#     categories = set(t.get('category') for t in transactions if t.get('type') == 'CREDIT')
#     return min(len(categories) * 20, 100)


# # ============================================================================
# # MAIN PROFILE
# # ============================================================================

# def get_income_profile(transactions):
#     ampi = calculate_ampi(transactions)
#     tmvi = calculate_tmvi(transactions)
#     dependency = calculate_income_dependency_ratio(transactions)
#     volatility = calculate_income_volatility(transactions)
#     cadence = calculate_income_cadence(transactions)
#     employer = calculate_employer_concentration(transactions)
#     diversity = calculate_income_diversity(transactions)

#     reliability = 100

#     if volatility > 0.25:
#         reliability -= 10
#     if not cadence['is_formal_employment']:
#         reliability -= 20
#     if dependency['dependency_ratio'] > 20:
#         reliability -= 5
#     if dependency['dependency_ratio'] > 40:
#         reliability -= 10

#     reliability = max(0, min(100, reliability))

#     return {
#         "income_metrics": {
#             "ampi": round(ampi, 2),
#             "tmvi": round(tmvi, 2),
#             "secondary_contribution": round(tmvi - ampi, 2)
#         },
#         "stability": {
#             "volatility": round(volatility, 3),
#             "cadence_days": round(cadence['average_days'], 1),
#             "formal_employment": cadence['is_formal_employment']
#         },
#         "composition": {
#             "dependency_ratio": round(dependency['dependency_ratio'], 1),
#             "employer_count": employer['unique_employers'],
#             "income_diversity_score": diversity
#         },
#         "risk": {
#             "reliability_score": reliability,
#             "risk_level": (
#                 "Very Low" if reliability > 90 else
#                 "Low" if reliability > 75 else
#                 "Moderate" if reliability > 60 else
#                 "High"
#             )
#         }
#     }

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

    return {
        "income": {
            "primary_monthly_income": round(ampi, 2),
            "total_effective_income": round(tmvi, 2),
            "secondary_contribution": round(tmvi - ampi, 2),
            "annual_income": annual_income_data["annual_amount"],
            "annual_income_months_of_data": annual_income_data["months_of_data"],
            "annual_income_verified": annual_income_data["is_verified_annual"],
            "annual_income_note": annual_income_data["note"],
            "monthly_wallet_volume": round(monthly_wallet, 2)
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