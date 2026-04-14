from app.models.state import AgentState
from app.services.income_categorizer import assign_tnx_category
from data.income_data import DebitCategory, CreditCategory
from app.services.llm_service import categorize_txn
from app.services.income_profile_calculations import generate_income_profile
from app.services.risk_calculations import generate_risk_indicators

def analyze(state: AgentState):
    all_txns = state['raw_transactions']
    
    # 1. Rule-based categorization
    for tran in all_txns:
        tran['category'], tran['category_confidence'] = assign_tnx_category(tran)

    # 2. Filter for LLM help
    unknown_txns = [tran for tran in all_txns if tran['category'] == DebitCategory.UNKNOWN or tran['category'] == CreditCategory.UNKNOWN]
    
    # 3. Call LLM for unknowns
    categozied_llm = categorize_txn(unknown_txns)
    llm_lookup = {item['id']: {'category': item['category'], 'confidence': item['confidence']} for item in categozied_llm}

    # 4. Merge back
    final_transactions = []
    for tran in all_txns:
        if tran['id'] in llm_lookup:
            tran['category'] = llm_lookup[tran['id']]['category']
            tran['category_confidence'] = llm_lookup[tran['id']]['confidence']
        if hasattr(tran['category'], 'value'):
            tran['category'] = tran['category'].value
        final_transactions.append(tran)

    # 5. Generate the Final Profile
    income_profile = generate_income_profile(final_transactions)
    
    extracted_docs = state.get('extracted_docs', {})
    loan_request = state.get('loan_request', {})
    
    indicators = generate_risk_indicators(income_profile, extracted_docs, loan_request)

    # 6. Return the update to the state
    return {
        "categorized_txns": final_transactions,
        "income_metrics": income_profile,
        "indicators": indicators,
        "status": "income_analysis_complete"
    }