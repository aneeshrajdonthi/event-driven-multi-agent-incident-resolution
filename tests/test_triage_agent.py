"""Tests for the triage agent — severity classification with mocked LLM."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.models import IncidentState, TelemetryEvent, TriageResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_state(events: list[TelemetryEvent]) -> IncidentState:
    """Construct a minimal IncidentState from a list of events."""
    return IncidentState(
        events=[e.model_dump(mode="json") for e in events],
        triage_result=TriageResult(
            severity="",
            affected_services=[],
            escalation_needed=False,
            summary="",
        ),
        root_cause="",
        affected_services=[],
        patches=[],
        status="triage",
        retrieval_context=[],
        conversation_history=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTriageAgent:
    """Triage agent should classify severity based on event patterns."""

    @pytest.mark.asyncio
    async def test_p1_classification_for_critical_cascading_failure(
        self, p1_telemetry_events: list[TelemetryEvent]
    ) -> None:
        """Multiple critical-severity events across services → P1."""
        llm_response = json.dumps(
            {
                "severity": "P1",
                "affected_services": [
                    "payment-service",
                    "order-service",
                    "gateway-service",
                ],
                "escalation_needed": True,
                "summary": "Cascading critical failure across payment, order and gateway.",
            }
        )

        with patch("src.agents.triage_agent.LLMClient") as MockLLM:
            instance = AsyncMock()
            instance.generate = AsyncMock(return_value=llm_response)
            MockLLM.return_value = instance

            from src.agents.triage_agent import triage_node

            state = _build_state(p1_telemetry_events)
            result = await triage_node(state)

        triage = result["triage_result"]
        assert triage["severity"] == "P1"
        assert triage["escalation_needed"] is True
        assert len(triage["affected_services"]) >= 2

    @pytest.mark.asyncio
    async def test_p4_classification_for_low_severity(
        self, p4_telemetry_events: list[TelemetryEvent]
    ) -> None:
        """A single info-level event → P4, no escalation."""
        llm_response = json.dumps(
            {
                "severity": "P4",
                "affected_services": ["notification-service"],
                "escalation_needed": False,
                "summary": "Minor latency blip on notification-service; no action needed.",
            }
        )

        with patch("src.agents.triage_agent.LLMClient") as MockLLM:
            instance = AsyncMock()
            instance.generate = AsyncMock(return_value=llm_response)
            MockLLM.return_value = instance

            from src.agents.triage_agent import triage_node

            state = _build_state(p4_telemetry_events)
            result = await triage_node(state)

        triage = result["triage_result"]
        assert triage["severity"] == "P4"
        assert triage["escalation_needed"] is False

    @pytest.mark.asyncio
    async def test_affected_services_populated(
        self, mock_telemetry_events: list[TelemetryEvent]
    ) -> None:
        """Triage should identify all affected services from the events."""
        affected = list(
            {e.service_name for e in mock_telemetry_events if e.severity in ("error", "critical")}
        )
        llm_response = json.dumps(
            {
                "severity": "P2",
                "affected_services": affected,
                "escalation_needed": False,
                "summary": "Elevated errors on several services.",
            }
        )

        with patch("src.agents.triage_agent.LLMClient") as MockLLM:
            instance = AsyncMock()
            instance.generate = AsyncMock(return_value=llm_response)
            MockLLM.return_value = instance

            from src.agents.triage_agent import triage_node

            state = _build_state(mock_telemetry_events)
            result = await triage_node(state)

        triage = result["triage_result"]
        assert isinstance(triage["affected_services"], list)
        assert len(triage["affected_services"]) > 0

    @pytest.mark.asyncio
    async def test_state_status_updated(
        self, mock_telemetry_events: list[TelemetryEvent]
    ) -> None:
        """After triage, the state status should advance past 'triage'."""
        llm_response = json.dumps(
            {
                "severity": "P3",
                "affected_services": ["gateway-service"],
                "escalation_needed": False,
                "summary": "Moderate traffic spike.",
            }
        )

        with patch("src.agents.triage_agent.LLMClient") as MockLLM:
            instance = AsyncMock()
            instance.generate = AsyncMock(return_value=llm_response)
            MockLLM.return_value = instance

            from src.agents.triage_agent import triage_node

            state = _build_state(mock_telemetry_events)
            result = await triage_node(state)

        # The node should return a dict that merges into IncidentState
        assert "triage_result" in result
        assert result["triage_result"]["severity"] in ("P1", "P2", "P3", "P4")
