"""
LangGraph Loan Processing Pipeline
===================================
Chains all agents in the correct order:

  parser_node → income_node → compliance_node → scoring_node → decision_node

Compliance node short-circuits to decision on hard veto (blacklist/AML).
"""

from langgraph.graph import StateGraph, END
from app.models.state import AgentState
from app.agents.parser_agent import parser_node
from app.agents.income_agent import analyze as income_node
from app.agents.compliance_agent import compliance_node
from app.agents.score_agent import scoring_node
from app.agents.decision_agent import decision_node


def _route_after_compliance(state: AgentState) -> str:
    """Skip scoring if compliance issued a hard veto."""
    if state.get("compliance_status") == "veto":
        return "decision_node"
    return "scoring_node"


def build_workflow() -> StateGraph:
    """Build the full LangGraph workflow."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("income_node", income_node)
    graph.add_node("compliance_node", compliance_node)
    graph.add_node("scoring_node", scoring_node)
    graph.add_node("decision_node", decision_node)

    # Entry point
    graph.set_entry_point("income_node")

    # Edges
    # graph.add_edge("parser_node", "income_node")   # removed: parser_node no longer exists
    graph.add_edge("income_node", "compliance_node")

    # Conditional: veto skips scoring
    graph.add_conditional_edges(
        "compliance_node",
        _route_after_compliance,
        {
            "scoring_node": "scoring_node",
            "decision_node": "decision_node",
        },
    )
    graph.add_edge("scoring_node", "decision_node")
    graph.add_edge("decision_node", END)

    return graph.compile()


# Pre-built workflow for use in API routes
_workflow = None


def build_test_workflow():
    """Return a compiled LangGraph workflow (cached)."""
    global _workflow
    if _workflow is None:
        print("[pipeline] Building new workflow...")
        _workflow = build_workflow()
        print("[pipeline] Workflow built and compiled.")
    else:
        print("[pipeline] Using cached workflow.")
    return _workflow
