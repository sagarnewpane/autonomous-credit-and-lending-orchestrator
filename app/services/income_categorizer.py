"""
Transaction Categorization Service
Provides utilities for categorizing bank transactions
"""

import re
from data.income_data import CATEGORIZATION_RULES, DebitCategory, CreditCategory


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
    
    # Process declarative rules in order
    for rule in CATEGORIZATION_RULES:
        # Check transaction type match
        if rule.get("type") and rule["type"] != tnx_type:
            continue
            
        rule_matched = True
        
        # Check if all required exact keywords are present
        if "match_all" in rule:
            for kw in rule["match_all"]:
                if kw not in description:
                    rule_matched = False
                    break
        
        if not rule_matched:
            continue
            
        # Check if ANY keyword from EACH required group is present
        if "match_any_groups" in rule:
            for group in rule["match_any_groups"]:
                if not any(kw in description for kw in group):
                    rule_matched = False
                    break
                    
        if rule_matched:
            return rule["category"], rule["confidence"]

    # Fallback: Unclassified
    return CreditCategory.UNKNOWN if tnx_type == "CREDIT" else DebitCategory.UNKNOWN, 0.0
