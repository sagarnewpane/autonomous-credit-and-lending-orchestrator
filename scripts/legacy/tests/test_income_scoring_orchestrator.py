# test_orchestrator.py
import json
from typing import TypedDict, Any, Dict, List, Optional
from langgraph.graph import StateGraph, END


from app.agents.income_agent import analyze as income_node
from app.agents.score_agent import scoring_node

# ============================================================================
# 1. DEFINE THE STATE
# ============================================================================
# This defines what data flows between your agents.
class AgentState(TypedDict, total=False):
    # Core identifiers
    applicant_id: str
    
    # Income Agent Inputs / Context
    loan_request: Dict[str, Any]
    extracted_docs: Dict[str, Any]
    
    # Income Agent Outputs
    income_metrics: Dict[str, Any]
    indicators: Dict[str, Any]
    income_agent_monthly_est: int
    income_confidence: float
    source_monthly: Dict[str, Any]
    anomaly_flags: List[Any]
    
    # Scoring Agent Outputs
    scorecard: Dict[str, Any]
    debug_info: Dict[str, Any]
    status: str

# ============================================================================
# 2. DEFINE MOCK ENTRY DATA
# ============================================================================
# We simulate the state as it would exist right BEFORE the Income Agent runs.
# The Income Agent will fetch raw data from Supabase using this applicant_id.
initial_state = {
    "applicant_id": "AP-000010",
    "loan_request": {
        "amount": 200000,
        "tenure_months": 18,
        "existing_liabilities_monthly": 0,
        "collateral_value_nrs": 800000
    },
    "extracted_docs": {
        "features": {
            "asset_backing": {
                "has_lalpurja": True
            }
        }
    }
}

# ============================================================================
# 3. BUILD THE LANGGRAPH WORKFLOW
# ============================================================================
def build_test_workflow():
    workflow = StateGraph(AgentState)
    
    # Add the nodes
    workflow.add_node("income_agent", income_node)
    workflow.add_node("scoring_agent", scoring_node)
    
    # Set the entry point
    workflow.set_entry_point("income_agent")
    
    # Define the edges (sequential flow)
    workflow.add_edge("income_agent", "scoring_agent")
    workflow.add_edge("scoring_agent", END)
    
    return workflow.compile()

# ============================================================================
# 4. RUN THE TEST
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 STARTING LANGGRAPH ORCHESTRATOR TEST")
    print("=" * 60)
    
    app = build_test_workflow()
    
    try:
        # Invoke the graph
        final_state = app.invoke(initial_state, config={"recursion_limit": 10})
        
        print("\n" + "=" * 70)
        print("  PIPELINE EXECUTION FINISHED")
        print("=" * 70)
        
        # =====================================================================
        # INCOME AGENT — DETAILED OUTPUT
        # =====================================================================
        print("\n" + "-" * 70)
        print("  1. INCOME AGENT OUTPUT")
        print("-" * 70)
        
        # 1a. Top-level income estimates
        print(f"\n  Estimated Monthly Income : NRs {final_state.get('income_agent_monthly_est', 'N/A')}")
        print(f"  Income Confidence        : {final_state.get('income_confidence', 'N/A')}")
        
        # 1b. Income Metrics (full income profile)
        income_metrics = final_state.get("income_metrics", {})
        income_summary = income_metrics.get("income", {})
        print(f"\n  --- Income Summary ---")
        print(f"  Total Observed Income    : NRs {income_summary.get('total_observed_income', 'N/A')}")
        print(f"  Primary Income Source    : {income_summary.get('primary_income_source', 'N/A')}")
        print(f"  Primary Income Amount    : NRs {income_summary.get('primary_income_amount', 'N/A')}")
        print(f"  Monthly Unverified Inflows: NRs {income_summary.get('monthly_unverified_inflows', 'N/A')}")
        print(f"  Months of Data           : {income_summary.get('months_of_data', 'N/A')}")
        
        # 1c. Income Composition
        composition = income_metrics.get("composition", {})
        print(f"\n  --- Income Composition ---")
        print(f"  Informal Income Ratio    : {composition.get('informal_income_ratio_%', 'N/A')}%")
        
        # 1d. Source Profiles (each income source breakdown)
        sources = income_metrics.get("sources", {})
        if sources:
            print(f"\n  --- Income Sources ({len(sources)} active) ---")
            for src_name, src in sources.items():
                print(f"\n    [{src.get('source_type', src_name).upper()}]")
                print(f"      Description           : {src.get('description', 'N/A')}")
                print(f"      Monthly Avg (Raw)     : NRs {src.get('monthly_average_raw', 'N/A')}")
                print(f"      Monthly Usable Income : NRs {src.get('monthly_usable_income', 'N/A')}")
                print(f"      Confidence Score      : {src.get('confidence_score', 'N/A')}")
                print(f"      Stability Score       : {src.get('stability_score', 'N/A')}")
                print(f"      Volatility (CV)       : {src.get('volatility_cv', 'N/A')}")
                print(f"      Months Active         : {src.get('months_active', 'N/A')} / {src.get('months_observed', 'N/A')}")
                print(f"      Recurrence Ratio      : {src.get('recurrence_ratio', 'N/A')}")
                print(f"      Transaction Count     : {src.get('transaction_count', 'N/A')}")
                notes = src.get("verification_notes", [])
                if notes:
                    print(f"      Verification Notes    :")
                    for note in notes:
                        print(f"        - {note}")
        
        # 1e. Risk Indicators
        indicators = final_state.get("indicators", {})
        if indicators:
            print(f"\n  --- Risk Indicators ---")
            print(f"  Estimated Monthly Capacity : NRs {indicators.get('estimated_monthly_capacity', 'N/A')}")
            print(f"  Observed Monthly Income    : NRs {indicators.get('observed_monthly_income', 'N/A')}")
            print(f"  Stability Score            : {indicators.get('stability_score', 'N/A')}")
            print(f"  Alternative Trust Score    : {indicators.get('alternative_trust_score', 'N/A')}")
            print(f"  Calculated DTI             : {indicators.get('calculated_dti', 'N/A')}")
            print(f"  Calculated LTI             : {indicators.get('calculated_lti', 'N/A')}")
            print(f"  Calculated LTV             : {indicators.get('calculated_ltv', 'N/A')}")
            income_flags = indicators.get("income_flags", [])
            if income_flags:
                print(f"  Income Flags               : {income_flags}")
            else:
                print(f"  Income Flags               : None")
        
        # 1f. Source Monthly Breakdown
        source_monthly = final_state.get("source_monthly", {})
        if source_monthly:
            print(f"\n  --- Monthly Breakdown by Source (6-month reference) ---")
            for src_key, src_data in source_monthly.items():
                print(f"\n    [{src_key.upper()}]")
                for k, v in src_data.items():
                    print(f"      {k:25s}: {v}")
        
        # 1g. Anomaly Flags
        anomalies = final_state.get("anomaly_flags", [])
        print(f"\n  --- Anomaly Flags ---")
        if anomalies:
            for a in anomalies:
                if isinstance(a, dict):
                    print(f"    - Txn {a.get('transaction_id', '?')} | Date: {a.get('date', '?')} | "
                          f"Amount: NRs {a.get('amount', '?')} | Direction: {a.get('direction', '?')}")
                else:
                    print(f"    - {a}")
        else:
            print(f"    None detected")
        
        # =====================================================================
        # SCORING AGENT — DETAILED OUTPUT
        # =====================================================================
        print("\n" + "-" * 70)
        print("  2. SCORING AGENT OUTPUT")
        print("-" * 70)
        
        # 2a. Scorecard
        scorecard = final_state.get("scorecard", {})
        print(f"\n  Credit Score  : {scorecard.get('credit_score', 'N/A')}")
        print(f"  Score Band    : {scorecard.get('score_band', 'N/A').upper()}")
        
        # 2b. Audit Trail (SHAP explainability)
        audit_trail = scorecard.get("audit_trail", {})
        print(f"\n  --- Audit Trail (SHAP Explainability) ---")
        print(f"  Primary Reason : {audit_trail.get('primary_reason', 'N/A')}")
        shap_factors = audit_trail.get("shap_top_factors", [])
        if shap_factors:
            print(f"  Top SHAP Factors:")
            for i, f in enumerate(shap_factors, 1):
                direction = f.get("direction", "?").upper()
                impact = f.get("impact", 0)
                bar = "+" * int(abs(impact) * 50) if impact > 0 else "-" * int(abs(impact) * 50)
                print(f"    {i}. {f.get('feature', '?'):35s} | Impact: {impact:+.4f} ({direction}) | {bar}")
        else:
            print(f"    No SHAP factors available")
        
        # 2c. Debug Info
        debug_info = final_state.get("debug_info", {})
        print(f"\n  --- Debug Info ---")
        print(f"  DB Fetch Success : {debug_info.get('db_fetch_success', 'N/A')}")
        
        upstream = debug_info.get("upstream_inputs", {})
        if upstream:
            print(f"\n  --- Upstream Inputs (from Income Agent) ---")
            for k, v in upstream.items():
                print(f"    {k:35s}: {v}")
        
        # 2d. Model Input Features (truncated for readability — show key ones)
        model_features = debug_info.get("model_input_features", {})
        if model_features:
            print(f"\n  --- Model Input Features ({len(model_features)} total) ---")
            key_features = [
                "income_agent_monthly_est", "income_confidence", "lti_ratio", "ltv_ratio",
                "requested_amount_nrs", "collateral_value_nrs", "household_size",
                "total_credit_6m", "total_debit_6m", "credit_debit_ratio",
                "payment_discipline", "latest_on_time_rate", "late_payment_count",
                "unpaid_bill_count", "has_lalpurja", "remittance_receiving",
                "cooperative_member", "kyc_tier", "rural_urban", "loan_purpose",
            ]
            shown = set()
            for feat in key_features:
                if feat in model_features:
                    print(f"    {feat:35s}: {model_features[feat]}")
                    shown.add(feat)
            remaining = {k: v for k, v in model_features.items() if k not in shown}
            if remaining:
                print(f"\n    ... and {len(remaining)} more features:")
                for k, v in list(remaining.items())[:10]:
                    print(f"    {k:35s}: {v}")
                if len(remaining) > 10:
                    print(f"    ... ({len(remaining) - 10} additional)")
        
        # =====================================================================
        # SUMMARY
        # =====================================================================
        print("\n" + "=" * 70)
        print("  TEST COMPLETED SUCCESSFULLY")
        print("=" * 70)

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ PIPELINE CRASHED")
        print("=" * 60)
        import traceback
        traceback.print_exc()