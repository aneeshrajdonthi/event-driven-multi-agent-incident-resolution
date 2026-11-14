"""Domain models and LangGraph state definitions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, TypedDict

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic domain models
# ---------------------------------------------------------------------------


class TelemetryEvent(BaseModel):
    """A single telemetry / observability event ingested from Kafka."""

    service_name: str
    metric_name: str
    value: float
    timestamp: datetime
    severity: str = "info"  # info | warning | error | critical
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodePatch(BaseModel):
    """A generated code patch for a single file."""

    file_path: str
    original_code: str
    patched_code: str
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)


class ResolutionReport(BaseModel):
    """Final output of the incident resolution pipeline."""

    incident_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    root_cause: str
    patches: list[CodePatch] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# LangGraph state (TypedDict so LangGraph can merge diffs)
# ---------------------------------------------------------------------------


class TriageResult(TypedDict, total=False):
    severity: str  # P1 | P2 | P3 | P4
    affected_services: list[str]
    escalation_needed: bool
    summary: str


class IncidentState(TypedDict, total=False):
    """Shared state flowing through the LangGraph incident pipeline."""

    events: list[dict[str, Any]]  # serialised TelemetryEvent dicts
    triage_result: TriageResult
    root_cause: str
    affected_services: list[str]
    patches: list[dict[str, Any]]  # serialised CodePatch dicts
    status: str  # triage | analysis | patching | review | resolved
    retrieval_context: list[str]
    conversation_history: list[dict[str, str]]
