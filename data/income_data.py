from enum import Enum
import re

class CreditCategory(str, Enum):
    """All credit transaction categories (income sources)"""
    SALARY = "SALARY"
    REMITTANCE = "REMITTANCE"
    FREELANCE = "FREELANCE"
    LOCAL_BUSINESS = "LOCAL_BUSINESS"
    TRANSFER = "TRANSFER"
    INTEREST = "INTEREST"
    INVESTMENT_RETURN = "INVESTMENT_RETURN"
    UNKNOWN = "UNKNOWN"


class DebitCategory(str, Enum):
    SHOPPING = "SHOPPING"
    LIFESTYLE = "LIFESTYLE"
    UTILITIES = "UTILITIES"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"
    TRANSFER = "TRANSFER"
    INVESTMENT = "INVESTMENT"
    WALLET_LOAD = "WALLET_LOAD"
    TAX = "TAX"
    DEBT_REPAYMENT = "DEBT_REPAYMENT"
    UNKNOWN = "UNKNOWN"

# General Rule Engine Configuration
CATEGORIZATION_RULES = [
    # --- STAGE 0A: Wallet settlement transactions (HIGHEST PRIORITY) ---
    {
        "type": "CREDIT",
        "match_any_groups": [
            ["ESEWA", "KHALTI", "FONEPAY"],
            ["SETTLEMENT", "TRANSFER", "COLLECTION", "RECEIVED"]
        ],
        "category": CreditCategory.LOCAL_BUSINESS,
        "confidence": 0.95
    },
    # --- STAGE 0B: QR/wallet payments ---
    {
        "type": "CREDIT",
        "match_any_groups": [
            ["QR", "COLLECTION"],
            ["KIRANA", "MERCHANT", "RECEIVED"]
        ],
        "category": CreditCategory.LOCAL_BUSINESS,
        "confidence": 0.90
    },
    # --- STAGE 0C: IPS-specific categories ---
    {
        "type": "CREDIT",
        "match_all": ["IPS"],
        "match_any_groups": [["REMIT", "IME"]],
        "category": CreditCategory.REMITTANCE,
        "confidence": 0.95
    },
    {
        "type": "CREDIT",
        "match_all": ["IPS"],
        "match_any_groups": [["FREELANCE", "UPWORK", "FIVERR"]],
        "category": CreditCategory.FREELANCE,
        "confidence": 0.95
    },
    # --- STAGE 1: Anchor Code Match (High Confidence) ---
    {"type": "CREDIT", "match_all": ["IPS"], "category": CreditCategory.SALARY, "confidence": 0.95},
    {"type": "DEBIT", "match_all": ["IPS"], "category": DebitCategory.UTILITIES, "confidence": 0.95},

    {"type": "CREDIT", "match_all": ["CIPS"], "category": CreditCategory.TRANSFER, "confidence": 0.95},
    {"type": "DEBIT", "match_all": ["CIPS"], "category": DebitCategory.TRANSFER, "confidence": 0.95},

    {"type": "CREDIT", "match_all": ["POS"], "category": CreditCategory.INVESTMENT_RETURN, "confidence": 0.95},
    {"type": "DEBIT", "match_all": ["POS"], "category": DebitCategory.SHOPPING, "confidence": 0.95},

    {"type": "DEBIT", "match_all": ["ATM"], "category": DebitCategory.CASH_WITHDRAWAL, "confidence": 0.95},
    {"type": "CREDIT", "match_all": ["INT"], "category": CreditCategory.INTEREST, "confidence": 0.95},
    {"type": "DEBIT", "match_all": ["ASBA"], "category": DebitCategory.INVESTMENT, "confidence": 0.95},
    {"type": "DEBIT", "match_all": ["TDS"], "category": DebitCategory.TAX, "confidence": 0.95},

    # --- STAGE 2: General Word Stemming (Medium Confidence) ---
    # Credit Stems
    {"type": "CREDIT", "match_any_groups": [["SALAR", "PAYROL", "WAG", "REMUNER"]], "category": CreditCategory.SALARY, "confidence": 0.75},
    {"type": "CREDIT", "match_any_groups": [["REMIT", "IME", "INWARD"]], "category": CreditCategory.REMITTANCE, "confidence": 0.75},
    {"type": "CREDIT", "match_any_groups": [["UPWORK", "FIVERR", "FREELANCER", "TOPTAL", "GURU", "99DESIGN", "FREELANC"]], "category": CreditCategory.FREELANCE, "confidence": 0.75},
    {"type": "CREDIT", "match_any_groups": [["QR", "KIRANA", "MERCHANT", "COLLECTION", "RECEIVED", "SETTLEMENT", "WALLET"]], "category": CreditCategory.LOCAL_BUSINESS, "confidence": 0.75},
    {"type": "CREDIT", "match_any_groups": [["INT", "DIVID"]], "category": CreditCategory.INTEREST, "confidence": 0.75},

    # Debit Stems
    {"type": "DEBIT", "match_any_groups": [["BILL", "NEA", "ELECT", "TOPUP", "WLINK", "KHANEPANI"]], "category": DebitCategory.UTILITIES, "confidence": 0.75},
    {"type": "DEBIT", "match_any_groups": [["ESEWA", "KHALTI", "WALET"]], "category": DebitCategory.WALLET_LOAD, "confidence": 0.75},
    {"type": "DEBIT", "match_any_groups": [["REST", "FOOD", "CAFE", "CINEM", "BHOJ", "PATHAO"]], "category": DebitCategory.LIFESTYLE, "confidence": 0.75},
    {"type": "DEBIT", "match_any_groups": [["EMI", "LOAN", "MORTGAG"]], "category": DebitCategory.DEBT_REPAYMENT, "confidence": 0.75},
]
