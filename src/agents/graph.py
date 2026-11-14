"""LangGraph StateGraph definition for the incident resolution pipeline."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.triage_agent import triage_node
from src.agents.root_cause_agent import root_cause_node
from src.agents.patch_agent import patch_node
from src.models import IncidentState, ResolutionReport, TelemetryEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Human-review placeholder node
# ---------------------------------------------------------------------------


async def human_review_node(state: IncidentState) -> dict[str, Any]:
    """Placeholder node for human review.

    In production this would pause the graph and wait for human approval.
    For now it auto-approves and marks the incident as resolved.
    """
    logger.info(
        "Human review requested — %d patch(es) pending",
        len(state.get("patches", [])),
    )
    return {
        "status": "resolved",
        "conversation_history": state.get("conversation_history", [])
        + [{"role": "system", "content": "Human review: auto-approved."}],
    }


# ---------------------------------------------------------------------------
# Conditional edge: skip deep analysis for low-severity incidents
# ---------------------------------------------------------------------------


def _route_after_triage(state: IncidentState) -> str:
    """Decide the next node based on triage severity."""
    triage = state.get("triage_result", {})
    severity = triage.get("severity", "P4")
    if severity in ("P1", "P2"):
        return "root_cause"
    # P3/P4 can still go through analysis, but we route through anyway
    return "root_cause"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

_builder = StateGraph(IncidentState)

_builder.add_node("triage", triage_node)
_builder.add_node("root_cause", root_cause_node)
_builder.add_node("patch", patch_node)
_builder.add_node("human_review", human_review_node)

_builder.set_entry_point("triage")

_builder.add_conditional_edges("triage", _route_after_triage, {"root_cause": "root_cause"})
_builder.add_edge("root_cause", "patch")
_builder.add_edge("patch", "human_review")
_builder.add_edge("human_review", END)

graph = _builder.compile()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_incident_pipeline(
    events: list[TelemetryEvent],
) -> ResolutionReport:
    """Run the full incident resolution pipeline and return a report."""

    initial_state: IncidentState = {
        "events": [e.model_dump(mode="json") for e in events],
        "triage_result": {},
        "root_cause": "",
        "affected_services": [],
        "patches": [],
        "status": "triage",
        "retrieval_context": [],
        "conversation_history": [],
    }

    final_state = await graph.ainvoke(initial_state)  # type: ignore[arg-type]

    from src.models import CodePatch

    return ResolutionReport(
        incident_id=uuid.uuid4().hex,
        root_cause=final_state.get("root_cause", ""),
        patches=[
            CodePatch.model_validate(p)
            for p in final_state.get("patches", [])
        ],
        metrics={
            "severity": final_state.get("triage_result", {}).get("severity"),
            "num_patches": len(final_state.get("patches", [])),
        },
        timestamp=datetime.utcnow(),
    )
