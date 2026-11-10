"""
Shared state passed between the LangGraph nodes.

AgentState is a TypedDict (total=False): LangGraph merges each node's returned keys
into it. It is not validated at runtime; app/services/audit.py records what each node
returned so the trail can be checked afterwards.
"""

from typing import Any, Dict, List, Optional, TypedDict, Union


class AgentState(TypedDict, total=False):
    # ---- Inputs ---------------------------------------------------------
    applicant_id: str
    application_id: str
    file_paths: Dict[str, Union[str, List[str]]]  # document images by type (Document Agent, optional)
    raw_transactions: List[Dict]
    household_size: int
    loan_request: Dict[str, Any]  # amount, tenure_months, collateral_value_nrs, loan_purpose,
                                  # existing_liabilities_monthly, declared_monthly_income

    # ---- Document Agent (optional, not in the default graph) -------------
    extracted_docs: Dict[str, Any]

    # ---- Income Agent ---------------------------------------------------
    income_metrics: Dict[str, Any]
    indicators: Dict[str, Any]
    income_agent_monthly_est: int
    income_confidence: float
    income_signal_count: int
    income_signal_features: Dict[str, Any]
    source_monthly: Dict[str, Any]
    anomaly_flags: List[Dict[str, Any]]
    income_flags: List[str]
    declared_monthly_income: Optional[float]
    imr: Optional[float]
    imr_status: str
    remittance_share: float
    db_write_errors: List[Dict[str, Any]]

    # ---- Compliance Agent -----------------------------------------------
    compliance_result: Dict[str, Any]
    compliance_status: str            # pass | flag | refer | veto
    compliance_flags: List[str]
    compliance_message: str
    compliance_notes: List[str]
    policy_version: str

    # ---- Score Agent ----------------------------------------------------
    scorecard: Dict[str, Any]

    # ---- Decision Agent -------------------------------------------------
    final_decision: str               # approve | conditional | refer | decline
    approved_amount_nrs: float
    interest_tier: str
    interest_rate_pct: float
    decision_reason: str
    decision_reasons: List[str]
    counter_offer: Dict[str, Any]
    final_output: Dict[str, Any]

    # ---- Flow control and audit ------------------------------------------
    status: str
    errors: List[str]
    debug_info: Dict[str, Any]
    audit_entries: List[str]          # hashes of audit-log entries written for this run
