from typing import List, Dict, Any, TypedDict

class AgentState(TypedDict):
    # Inputs
    applicant_id: str               # Applicant ID to fetch data from DB
    file_paths: Dict[str, str]      # Paths to Lal Purja, Citizenship, etc. mapped by doc type
    raw_transactions: List[Dict] # Transactions already in your system
    
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

    # Flow Control
    status: str
    compliance_notes: List[str]
    errors: List[str]
