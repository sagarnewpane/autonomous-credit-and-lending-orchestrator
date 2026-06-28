# test_orchestrator.py
import json
from typing import TypedDict, Any, Dict, List
from langgraph.graph import StateGraph, END

# Imports (Adjust paths as needed for your project)

from app.agents.income_agent import analyze as income_node
from app.agents.compliance_agent import compliance_node
from app.agents.score_agent import scoring_node
from app.agents.decision_agent import decision_node


# 1. DEFINE THE EXPANDED STATE
class AgentState(TypedDict, total=False):
    applicant_id: str
    loan_request: Dict[str, Any]
    extracted_docs: Dict[str, Any]
    
    income_metrics: Dict[str, Any]
    indicators: Dict[str, Any]
    income_agent_monthly_est: int
    income_confidence: float
    source_monthly: Dict[str, Any]
    
    compliance_status: str
    compliance_flags: List[str]
    compliance_message: str
    
    scorecard: Dict[str, Any]
    
    final_decision: str
    approved_amount_nrs: int
    interest_tier: str
    interest_rate_pct: float
    decision_reason: str
    
    debug_info: Dict[str, Any]
    status: str

# 2. MOCK ENTRY DATA
initial_state = {
    "applicant_id": "AP-000010",
    "loan_request": {
        "amount": 200000,
        "tenure_months": 18,
        "existing_liabilities_monthly": 0,
        "collateral_value_nrs": 12000
    },
    "extracted_docs": {
        "features": {
            "asset_backing": {
                "has_lalpurja": True
            }
        }
    }
}

# 3. BUILD GRAPH
def build_test_workflow():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("income_agent", income_node)
    workflow.add_node("compliance_agent", compliance_node)
    workflow.add_node("scoring_agent", scoring_node)
    workflow.add_node("decision_agent", decision_node)
    
    workflow.set_entry_point("income_agent")
    
    # Sequential flow for maximum debug visibility
    workflow.add_edge("income_agent", "compliance_agent")
    workflow.add_edge("compliance_agent", "scoring_agent")
    workflow.add_edge("scoring_agent", "decision_agent")
    workflow.add_edge("decision_agent", END)
    
    return workflow.compile()

# 4. RUN TEST
if __name__ == "__main__":
    print("=" * 70)
    print("🚀 STARTING FULL 4-AGENT LANGGRAPH ORCHESTRATOR TEST")
    print("=" * 70)
    
    app = build_test_workflow()
    
    try:
        final_state = app.invoke(initial_state, config={"recursion_limit": 15})
        
        print("\n" + "=" * 70)
        print("✅ PIPELINE EXECUTION FINISHED. DEBUG REPORT:")
        print("=" * 70)
        
        print("\n--- 1. INCOME AGENT ---")
        print(f"Monthly Est: NRs {final_state.get('income_agent_monthly_est', 'N/A')}")
        print(f"Confidence:  {final_state.get('income_confidence', 'N/A')}")
        
        print("\n--- 2. COMPLIANCE AGENT ---")
        print(f"Status:      {final_state.get('compliance_status', 'N/A')}")
        print(f"Flags:       {final_state.get('compliance_flags', 'N/A')}")
        print(f"Message:     {final_state.get('compliance_message', 'N/A')}")
        
        print("\n--- 3. SCORING AGENT ---")
        scorecard = final_state.get("scorecard", {})
        print(f"Credit Score: {scorecard.get('credit_score', 'N/A')}")
        print(f"Score Band:   {scorecard.get('score_band', 'N/A')}")
        print(f"Audit Trail:  {json.dumps(scorecard.get('audit_trail', {}), indent=2)}")
        
        print("\n--- 4. DECISION AGENT (FINAL OUTPUT) ---")
        print(f"Decision:       {final_state.get('final_decision', 'N/A')}")
        print(f"Approved Amt:   NRs {final_state.get('approved_amount_nrs', 'N/A')}")
        print(f"Interest Tier:  {final_state.get('interest_tier', 'N/A')} ({final_state.get('interest_rate_pct', 0)}%)")
        print(f"Reason:         {final_state.get('decision_reason', 'N/A')}")
        
        print("\n" + "=" * 70)
        print("🔍 DEEP DEBUG TRACE")
        print("=" * 70)
        debug_info = final_state.get("debug_info", {})
        
        print("\n[Compliance Agent Traces]:")
        print(json.dumps(debug_info.get("compliance_agent", {}).get("rule_traces", {}), indent=2))
        
        print("\n[Decision Agent Traces]:")
        print(json.dumps(debug_info.get("decision_agent", {}), indent=2))
        
        print("\n" + "=" * 70)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("=" * 70)

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ PIPELINE CRASHED")
        print("=" * 70)
        import traceback
        traceback.print_exc()