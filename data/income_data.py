from enum import Enum
import re

class CreditCategory(str, Enum):
    """All credit transaction categories (income sources)"""
    SALARY = "SALARY"
    REMITTANCE = "REMITTANCE"
    FREELANCE = "FREELANCE"
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

# High-priority anchor codes (Banking Standards)
NEPALI_BANK_ANCHORS = {
    "IPS": {"CR": CreditCategory.SALARY, "DR": DebitCategory.UTILITIES},
    "CIPS": {"CR": CreditCategory.TRANSFER, "DR": DebitCategory.TRANSFER},
    "POS": {"CR": CreditCategory.INVESTMENT_RETURN, "DR": DebitCategory.SHOPPING},
    "ATM": {"DR": DebitCategory.CASH_WITHDRAWAL},
    "INT": {"CR": CreditCategory.INTEREST},
    "ASBA": {"DR": DebitCategory.INVESTMENT},
    "TDS": {"DR": DebitCategory.TAX}
}

# General Word Stems (Broad Logic)
CREDIT_STEMS = {
    CreditCategory.SALARY: ["SALAR", "PAYROL", "WAG", "REMUNER"],
    CreditCategory.REMITTANCE: ["REMIT", "IME", "INWARD"],
    CreditCategory.FREELANCE: ["UPWORK", "FIVERR", "FREELANCER", "TOPTAL", "GURU", "99DESIGN", "FREELANC"],
    CreditCategory.INTEREST: ["INT", "DIVID"]
}

DEBIT_STEMS = {
    DebitCategory.UTILITIES: ["BILL", "NEA", "ELECT", "TOPUP", "WLINK", "KHANEPANI"],
    DebitCategory.WALLET_LOAD: ["ESEWA", "KHALTI", "WALET"],
    DebitCategory.LIFESTYLE: ["REST", "FOOD", "CAFE", "CINEM", "BHOJ", "PATHAO"],
    DebitCategory.DEBT_REPAYMENT: ["EMI", "LOAN", "MORTGAG"]
}