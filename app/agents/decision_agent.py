# decision_agent.py
from typing import Dict, Any
from app.models.state import AgentState

def _get_interest_tier(credit_score: int) -> str:
    if credit_score >= 670: return "base"       
    elif credit_score >= 580: return "premium"  
    else: return "subprime"                     

def _get_mock_interest_rate(tier: str) -> float:
    """Assigns a compliant rate based on tier"""
    if tier == "base": return 11.0
    elif tier == "premium": return 12.5
    elif tier == "subprime": return 14.5
    return 0.0

def decision_node(state: AgentState):
    """The Final Judge. Merges Compliance and Scoring."""
    
    # 1. Extract Data from State
    compliance_status = state.get("compliance_status", "pass")
    compliance_flags = state.get("compliance_flags", [])
    credit_score = state.get("scorecard", {}).get("credit_score", 300)
    income_conf = state.get("income_confidence", 0.0)
    requested_amount = state.get("loan_request", {}).get("amount", 0)
    
    decision_trace = {
        "initial_inputs": {
            "credit_score": credit_score,
            "compliance_status": compliance_status,
            "income_confidence": income_conf,
            "requested_amount": requested_amount
        }
    }
    
    # 2. Hard Veto Check
    if compliance_status == "veto":
        decision_trace["veto_check"] = "Triggered. Rejecting."
        return {
            "final_decision": "reject",
            "approved_amount_nrs": 0,
            "interest_tier": None,
            "interest_rate_pct": 0.0,
            "decision_reason": "NRB Hard Veto",
            "debug_info": {"decision_agent": decision_trace}
        }
        
    # 3. Income Confidence Check
    if income_conf < 0.40:
        decision_trace["confidence_check"] = f"Failed ({income_conf} < 0.40). Rejecting."
        return {
            "final_decision": "reject",
            "approved_amount_nrs": 0,
            "interest_tier": None,
            "interest_rate_pct": 0.0,
            "decision_reason": "Income Confidence too low",
            "debug_info": {"decision_agent": decision_trace}
        }
        
    # 4. Score & Compliance Matrix
    approved = 0
    tier = None
    rate = 0.0
    reason = ""
    
    if credit_score < 450:
        decision = "reject"
        decision_trace["score_matrix"] = "Score < 450. Rejecting."
        reason = "Poor credit score"
        
    elif 450 <= credit_score < 580:
        decision = "refer"
        decision_trace["score_matrix"] = "Score 450-579. Referring to manual underwriter."
        reason = "Manual review required"
        
    elif 580 <= credit_score < 670:
        decision = "conditional"
        tier = "premium"
        rate = _get_mock_interest_rate(tier)
        # Apply 15% haircut if confidence is weak OR compliance flagged it
        if income_conf < 0.70 or compliance_status == "flag":
            approved = int(requested_amount * 0.85)
            decision_trace["haircut_check"] = f"Applied 15% haircut. Approved: {approved}"
        else:
            approved = requested_amount
        decision_trace["score_matrix"] = f"Score 580-669. Conditional. Tier: {tier}."
        reason = "Conditional approval"
        
    else: # 670+
        decision = "approve"
        tier = "base"
        rate = _get_mock_interest_rate(tier)
        if income_conf < 0.70 or compliance_status == "flag":
            approved = int(requested_amount * 0.85)
            decision_trace["haircut_check"] = f"Applied 15% haircut. Approved: {approved}"
        else:
            approved = requested_amount
        decision_trace["score_matrix"] = f"Score 670+. Approved. Tier: {tier}."
        reason = "Standard approval"
        
    # 5. Compliance Downgrade Check
    # If compliance flagged it, force to 'conditional' for manual review
    if compliance_status == "flag" and decision == "approve":
        decision = "conditional"
        approved = int(requested_amount * 0.85)
        decision_trace["compliance_override"] = "Compliance flagged. Downgraded approve -> conditional."
        reason = "Conditional approval (Compliance flag)"
        
    return {
        "final_decision": decision,
        "approved_amount_nrs": approved,
        "interest_tier": tier,
        "interest_rate_pct": rate,
        "decision_reason": reason,
        "debug_info": {"decision_agent": decision_trace}
    }