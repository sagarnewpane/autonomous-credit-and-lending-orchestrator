"""
Transaction Categorization Service
Provides utilities for categorizing bank transactions
"""

import re
from data.income_data import NEPALI_BANK_ANCHORS, DEBIT_STEMS, CREDIT_STEMS, DebitCategory, CreditCategory


def assign_tnx_category(transaction: dict):
    """
    Assigns a category to a transaction using a hybrid rule-based approach.
    
    Args:
        transaction (dict): Transaction object with 'description' and 'type' keys
        
    Returns:
        tuple: (CategoryEnum, confidence_score)
            - CategoryEnum: The assigned category or None if unclassified
            - confidence_score: Float between 0.0 and 0.95
    """
    description = transaction.get('description', "").upper()
    tnx_type = transaction.get('type', "").upper()  # "CREDIT" or "DEBIT"
    
    # --- STAGE 0: Specific keyword detection (before generic anchor codes) ---
    # For IPS transfers, check if description contains specific category keywords
    if "IPS" in description and tnx_type == "CREDIT":
        if "REMIT" in description or "IME" in description:
            return CreditCategory.REMITTANCE, 0.95
        if "FREELANCE" in description or "UPWORK" in description or "FIVERR" in description:
            return CreditCategory.FREELANCE, 0.95
    
    # --- STAGE 1: Anchor Code Match (Highest Confidence) ---
    for code, mapping in NEPALI_BANK_ANCHORS.items():
        if code in description:
            cat = mapping.get("CR" if tnx_type == "CREDIT" else "DR")
            if cat:
                return cat, 0.95

    # --- STAGE 2: General Word Stemming (Medium Confidence) ---
    tokens = re.findall(r'\w+', description)
    stems = CREDIT_STEMS if tnx_type == "CREDIT" else DEBIT_STEMS
    
    for category, stem_list in stems.items():
        for token in tokens:
            if any(token.startswith(stem) for stem in stem_list):
                return category, 0.75

    # --- STAGE 3: Unclassified ---
    return CreditCategory.UNKNOWN if tnx_type == "CREDIT" else DebitCategory.UNKNOWN, 0.0
