"""API route handlers."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from src.agents.graph import run_incident_pipeline
from src.llm.cache import LLMCache
from src.models import ResolutionReport, TelemetryEvent

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory store for completed reports (swap with a DB in production)
_reports: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/incidents/analyze", response_model=ResolutionReport)
async def analyze_incident(events: list[TelemetryEvent]) -> ResolutionReport:
    """Accept telemetry events and run the full LangGraph pipeline."""
    if not events:
        raise HTTPException(status_code=400, detail="At least one event is required")

    report = await run_incident_pipeline(events)
    _reports[report.incident_id] = report.model_dump(mode="json")
    logger.info("Incident %s resolved", report.incident_id)
    return report


@router.get("/incidents/{incident_id}", response_model=ResolutionReport)
async def get_incident(incident_id: str) -> ResolutionReport:
    """Retrieve a previously generated resolution report."""
    data = _reports.get(incident_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return ResolutionReport.model_validate(data)


@router.get("/health")
async def health() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}


@router.get("/metrics")
async def metrics() -> dict[str, Any]:
    """Return basic application metrics."""
    cache = LLMCache()
    return {
        "incidents_processed": len(_reports),
        "cache": cache.metrics(),
    }
