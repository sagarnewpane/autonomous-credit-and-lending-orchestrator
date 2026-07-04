# compliance_agent.py
import re
import json
import sys
import os
from typing import Dict, List, Any
from app.models.state import AgentState
from app.db import db

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from scripts.etl_master_builder import build_single_master_record

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
        existing_loans = int(applicant_data.get("existing_loan_count", 0) or 0)

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
    application_id = state.get("application_id")

    # Build applicant_data from state for compliance checks
    applicant_data = {
        "applicant_id": applicant_id,
        "requested_amount_nrs": state.get("loan_request", {}).get("amount"),
        "income_agent_monthly_est": state.get("income_agent_monthly_est"),
        "collateral_value_nrs": state.get("loan_request", {}).get("collateral_value_nrs"),
        "nrb_blacklist_flag": state.get("loan_request", {}).get("nrb_blacklist_flag"),
        "aml_flag": state.get("loan_request", {}).get("aml_flag"),
        "kyc_tier": state.get("loan_request", {}).get("kyc_tier"),
        "loan_purpose": state.get("loan_request", {}).get("loan_purpose"),
        "existing_loan_count": state.get("loan_request", {}).get("existing_loan_count"),
    }

    # 4. Run rules
    result = checker.check_compliance(applicant_data)

    # Save compliance results to database immediately
    if application_id:
        try:
            db.table("loan_applications").eq("application_id", application_id).update({
                "compliance_status": result["status"],
                "compliance_flags": result["compliance_flags"],
            })
        except Exception as e:
            print(f"[Compliance Agent] DB Save Error for {application_id}: {e}")

    # ============================================
    # 5. BUILD MASTER RECORD (AFTER compliance save)
    # ============================================
    master_record = None
    master_error = None
    
    try:
        # Pass the current state so master builder has all needed IDs
        # Also include income data from state in case DB fetch fails
        enriched_state = {
            **state,
            "compliance_status": result["status"],
            "compliance_flags": result["compliance_flags"],
        }
        master_record = build_single_master_record(enriched_state)
    except Exception as e:
        master_error = str(e)
        print(f"[Compliance Agent] ❌ MASTER TABLE BUILD FAILED: {e}")
        # DON'T silently fail - add to debug info so it's visible

    return {
        "compliance_status": result["status"],
        "compliance_flags": result["compliance_flags"],
        "compliance_message": result["message"],
        "master_record_built": master_record is not None,
        "master_build_error": master_error,  # NEW: Track this error
        "debug_info": {
            "compliance_agent": {
                "inputs_evaluated": applicant_data,
                "rule_traces": result.get("rule_traces", {}),
                "final_status": result["status"],
                "flags_raised": result["compliance_flags"],
                "master_table_status": "built" if master_record else f"FAILED: {master_error}"
            }
        }
    }