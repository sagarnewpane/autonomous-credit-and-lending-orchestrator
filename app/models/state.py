from typing import List, Dict, Any, TypedDict, Union

class AgentState(TypedDict, total=False):
    # Inputs
    applicant_id: str               # Applicant ID to fetch data from DB
    application_id: str             # Loan application ID
    file_paths: Dict[str, Union[str, List[str]]]  # Paths mapped by doc type; lists for multi-image docs (e.g., citizenship front+back)
    raw_transactions: List[Dict]    # Transactions already in your system
    declared_monthly_income: float  # User-declared monthly income
    household_size: int             # Household size for per-capita calculations

    # Agent Outputs
    extracted_docs: Dict[str, Any]
    categorized_txns: List[Dict]
    income_metrics: Dict[str, Any]
    indicators: Dict[str, Any]
    scorecard: Dict[str, Any]
    compliance_result: Dict[str, Any]
    final_output: Dict[str, Any]

    # Context (For capacity/risk sizing)
    loan_request: Dict[str, Any]

    # Income Agent Outputs
    income_agent_monthly_est: int
    income_confidence: float
    raw_mobile_credit: float
    raw_mobile_debit: float
    source_monthly: Dict[str, Any]
    anomaly_flags: List[Dict[str, Any]]

    # Compliance Agent Outputs
    compliance_status: str
    compliance_flags: List[str]
    compliance_message: str

    # Decision Agent Outputs
    final_decision: str
    approved_amount_nrs: float
    interest_tier: str
    interest_rate_pct: float
    decision_reason: str

    # Flow Control
    status: str
    compliance_notes: List[str]
    errors: List[str]
    debug_info: Dict[str, Any]
