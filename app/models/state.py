from typing import List, Dict, Any, TypedDict

class AgentState(TypedDict):
    # Inputs
    file_paths: Dict[str, str]      # Paths to Lal Purja, Citizenship, etc. mapped by doc type
    raw_transactions: List[Dict] # Transactions already in your system
    
    # Agent Outputs
    extracted_docs: Dict[str, Any]
    categorized_txns: List[Dict]
    
    # Flow Control
    status: str
    errors: List[str]