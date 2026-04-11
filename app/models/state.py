from typing import List, Dict, Any, TypedDict

class AgentState(TypedDict):
    # Inputs
    file_paths: List[str]      # Paths to Lal Purja, Citizenship, etc.
    raw_transactions: List[Dict] # Transactions already in your system
    
    # Agent Outputs
    extracted_docs: Dict[str, Any]
    categorized_txns: List[Dict]
    
    # Flow Control
    status: str
    errors: List[str]