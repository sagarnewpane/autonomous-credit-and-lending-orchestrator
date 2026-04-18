from typing import List, Dict, Any, TypedDict

class AgentState(TypedDict):
    # Inputs
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
    
    # Flow Control
    status: str
    compliance_notes: List[str]
    errors: List[str]
