# compliance_agent.py
import re
import json
from typing import Dict, List, Any
from app.models.state import AgentState
from app.db.supabase import supabase

class ComplianceChecker:
    def __init__(self):
        self.AGRI_PURPOSES = [
            "agricultural_input", "agri_land_development", 
            "livestock_purchase", "irrigation_equipment"
        ]
        self.MAX_LTI_AGRI = 36.0
        self.LOAN_LIMITS = {
            "basic": 100000,
            "mid": 500000,
            "full": float('inf')
        }
        print("✅ Compliance Agent initialized. NRB Rules loaded.")

    def _clean_amount(self, amount) -> float:
        if amount is None: return 0.0
        if isinstance(amount, str):
            cleaned = re.sub(r'[^\d.-]', '', amount)
            return abs(float(cleaned)) if cleaned else 0.0
        return abs(float(amount))

    def check_compliance(self, applicant_data: Dict) -> Dict:
        applicant_id = applicant_data.get("applicant_id", "UNKNOWN")
        flags = []
        rule_traces = {}  # For debugging
        
        req_amount = self._clean_amount(applicant_data.get("requested_amount_nrs", 0))
        income = self._clean_amount(applicant_data.get("income_agent_monthly_est", 0))
        collateral = self._clean_amount(applicant_data.get("collateral_value_nrs", 0))
        
        is_blacklisted = str(applicant_data.get("nrb_blacklist_flag", "")).lower() == "true"
        is_aml_flag = str(applicant_data.get("aml_flag", "")).lower() == "true"
        kyc_tier = str(applicant_data.get("kyc_tier", "basic")).lower()
        loan_purpose = str(applicant_data.get("loan_purpose", "")).lower()
        existing_loans = int(applicant_data.get("existing_loan_count", 0))

        # 1. NRB-AML-004 & Blacklist
        rule_traces["blacklist_check"] = {"triggered": is_blacklisted}
        if is_blacklisted:
            return {
                "status": "veto",
                "compliance_flags": ["NRB_BLACKLIST"],
                "message": "HARD REJECT: Applicant is on NRB blacklist.",
                "rule_traces": rule_traces
            }

        rule_traces["aml_check"] = {"triggered": is_aml_flag}
        if is_aml_flag:
            flags.append("AML_FLAGGED")

        # 2. NRB-KYC-001
        max_allowed = self.LOAN_LIMITS.get(kyc_tier, 0)
        kyc_exceeded = req_amount > max_allowed
        rule_traces["kyc_limit_check"] = {"tier": kyc_tier, "max_allowed": max_allowed, "requested": req_amount, "triggered": kyc_exceeded}
        if kyc_exceeded:
            flags.append("KYC_LIMIT_EXCEEDED")

        # 3. NRB-COL-005
        collateral_required = req_amount > 500000 and collateral <= 0
        rule_traces["collateral_check"] = {"requested": req_amount, "collateral": collateral, "triggered": collateral_required}
        if collateral_required:
            flags.append("COLLATERAL_REQUIRED")

        # 4. NRB-LTI-002
        if loan_purpose in self.AGRI_PURPOSES:
            lti = req_amount / income if income > 0 else float('inf')
            lti_exceeded = lti > self.MAX_LTI_AGRI
            rule_traces["lti_check"] = {"purpose": loan_purpose, "lti": lti, "max_limit": 36.0, "triggered": lti_exceeded}
            if lti_exceeded:
                flags.append("LTI_EXCEEDED" if income > 0 else "LTI_INFINITE_NO_INCOME")
        else:
            rule_traces["lti_check"] = {"skipped": "Not an agricultural loan"}

        # 5. NRB-SEC-003
        exposure_warn = existing_loans >= 3
        rule_traces["exposure_check"] = {"existing_loans": existing_loans, "triggered": exposure_warn}
        if exposure_warn:
            flags.append("EXPOSURE_LIMIT_WARN")

        status = "pass" if len(flags) == 0 else "flag"
        message = "All NRB rules passed." if status == "pass" else f"Application violates {len(flags)} NRB rule(s)."

        return {
            "status": status,
            "compliance_flags": flags,
            "message": message,
            "rule_traces": rule_traces
        }

checker = ComplianceChecker()

# ============================================================================
# LANGGRAPH NODE
# ============================================================================

def compliance_node(state: AgentState):
    """LangGraph entry point for Compliance Agent"""
    applicant_id = state.get("applicant_id")
    
    # 1. Fetch static data from DB
    db_response = supabase.table('scoring_feature_matrix') \
        .select('requested_amount_nrs, collateral_value_nrs, nrb_blacklist_flag, aml_flag, kyc_tier, loan_purpose, existing_loan_count') \
        .eq('applicant_id', applicant_id) \
        .single() \
        .execute()
        
    db_data = db_response.data or {}
    
    # 2. Merge DB data with dynamic Income Agent state
    applicant_data = {
        **db_data,
        "applicant_id": applicant_id,
        "income_agent_monthly_est": state.get("income_agent_monthly_est", 0),
    }

    # 3. Run rules
    result = checker.check_compliance(applicant_data)
    
    return {
        "compliance_status": result["status"],
        "compliance_flags": result["compliance_flags"],
        "compliance_message": result["message"],
        "debug_info": {
            "compliance_agent": {
                "inputs_evaluated": applicant_data,
                "rule_traces": result.get("rule_traces", {}),
                "final_status": result["status"],
                "flags_raised": result["compliance_flags"]
            }
        }
    }