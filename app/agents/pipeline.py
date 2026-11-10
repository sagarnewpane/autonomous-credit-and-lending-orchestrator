"""
LangGraph loan-assessment pipeline.

    income_node -> compliance_node -> scoring_node -> decision_node
                                \\-> decision_node (when a policy rule vetoes)

Each node is wrapped so that what it returns is summarised into the hash-chained audit
log (app/services/audit.py). The Document Agent (app/agents/parser_agent.py) is an
optional component for OCR experiments and is not part of this graph.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict

from langgraph.graph import END, StateGraph

from app.agents.compliance_agent import compliance_node
from app.agents.decision_agent import decision_node
from app.agents.income_agent import analyze as income_node
from app.agents.score_agent import scoring_node
from app.models.state import AgentState
from app.services import audit

logger = logging.getLogger(__name__)


def audited(name: str, fn: Callable[[AgentState], Dict]) -> Callable[[AgentState], Dict]:
    def wrapper(state: AgentState) -> Dict:
        t0 = time.perf_counter()
        update = fn(state) or {}
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        try:
            payload = audit.summarise(name, update)
            payload["elapsed_ms"] = elapsed_ms
            h = audit.record(state.get("application_id"), name, payload)
            update["audit_entries"] = list(state.get("audit_entries", []) or []) + [h]
        except Exception as e:  # auditing must never block a decision, but failures are logged
            logger.error(f"[audit] could not record {name}: {e}")
        timings = dict((state.get("debug_info") or {}).get("timings_ms", {}))
        timings[name] = elapsed_ms
        debug = dict(update.get("debug_info") or {})
        debug["timings_ms"] = timings
        update["debug_info"] = debug
        return update

    wrapper.__name__ = f"audited_{name}"
    return wrapper


def _route_after_compliance(state: AgentState) -> str:
    """Skip scoring when a policy rule vetoes the application."""
    return "decision_node" if state.get("compliance_status") == "veto" else "scoring_node"


def build_workflow():
    graph = StateGraph(AgentState)
    graph.add_node("income_node", audited("income_node", income_node))
    graph.add_node("compliance_node", audited("compliance_node", compliance_node))
    graph.add_node("scoring_node", audited("scoring_node", scoring_node))
    graph.add_node("decision_node", audited("decision_node", decision_node))
    graph.set_entry_point("income_node")
    graph.add_edge("income_node", "compliance_node")
    graph.add_conditional_edges(
        "compliance_node",
        _route_after_compliance,
        {"scoring_node": "scoring_node", "decision_node": "decision_node"},
    )
    graph.add_edge("scoring_node", "decision_node")
    graph.add_edge("decision_node", END)
    return graph.compile()


_workflow = None


def get_workflow():
    """Compiled workflow, built once per process."""
    global _workflow
    if _workflow is None:
        _workflow = build_workflow()
    return _workflow


# Backward-compatible name used by app/api/routes.py
build_test_workflow = get_workflow
