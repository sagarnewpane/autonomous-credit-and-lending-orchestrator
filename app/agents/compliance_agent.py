from app.models.state import AgentState

def check_compliance(state: AgentState):
    extracted_docs = state.get("extracted_docs", {})
    indicators = state.get("indicators", {})
    compliance_notes = state.get("compliance_notes", []) or []
    
    # 1. Cross-Document Consistency
    flags = extracted_docs.get("flags", [])
    if "citizenship_mismatch_across_documents" in flags:
        compliance_notes.append("WARNING: Citizenship number mismatch detected across uploaded documents.")
    
    mismatches = extracted_docs.get("all_citizenship_numbers_found", [])
    if mismatches and len(set([m[1] for m in mismatches if m[1]])) > 1:
        compliance_notes.append(f"WARNING: Multiple distinct citizenship numbers found: {mismatches}")
    
    # 2. Advisory Check for Capacity Ratios 
    capacity_ratios = indicators.get("capacity_ratios", {})
    dti = capacity_ratios.get("DTI", 0)
    lti = capacity_ratios.get("LTI", 0)
    
    if dti > 0.5:
        compliance_notes.append(f"ADVISORY: High Debt-to-Income ratio ({round(dti * 100, 2)}%). Exceeds 50% threshold.")
        
    if lti > 1.5:
        compliance_notes.append(f"ADVISORY: High Loan-to-Income ratio ({lti}x). Exceeds 1.5x threshold.")

    return {
        "compliance_notes": compliance_notes,
        "status": "compliance_checks_complete"
    }