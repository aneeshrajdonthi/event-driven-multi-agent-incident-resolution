"""Tests for the root cause agent — mocked retrieval + LLM analysis."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models import IncidentState, TelemetryEvent, TriageResult


def _build_analysis_state(
    events: list[TelemetryEvent],
) -> IncidentState:
    """State that has already passed triage and is ready for root-cause."""
    return IncidentState(
        events=[e.model_dump(mode="json") for e in events],
        triage_result=TriageResult(
            severity="P1",
            affected_services=["payment-service", "order-service"],
            escalation_needed=True,
            summary="Cascading failure.",
        ),
        root_cause="",
        affected_services=["payment-service", "order-service"],
        patches=[],
        status="analysis",
        retrieval_context=[],
        conversation_history=[],
    )


class TestRootCauseAgent:
    """Root-cause agent should produce valid analysis from retrieval context."""

    @pytest.mark.asyncio
    async def test_produces_root_cause_string(
        self, p1_telemetry_events: list[TelemetryEvent]
    ) -> None:
        """The agent must set a non-empty root_cause in the state."""
        mock_retrieval_results = [
            "Past incident INC-2024-042: payment-service OOM caused by connection pool leak.",
            "Runbook: restart payment-service pods and increase pool size.",
        ]
        root_cause_text = (
            "Connection pool exhaustion in payment-service caused cascading "
            "5xx responses across downstream services."
        )

        with (
            patch("src.agents.root_cause_agent.HybridRetriever") as MockRetriever,
            patch("src.agents.root_cause_agent.LLMClient") as MockLLM,
        ):
            retriever_inst = AsyncMock()
            retriever_inst.retrieve = AsyncMock(
                return_value=[
                    type("R", (), {"text": t, "score": 0.9 - i * 0.1})()
                    for i, t in enumerate(mock_retrieval_results)
                ]
            )
            MockRetriever.return_value = retriever_inst

            llm_inst = AsyncMock()
            llm_inst.generate = AsyncMock(return_value=root_cause_text)
            MockLLM.return_value = llm_inst

            from src.agents.root_cause_agent import root_cause_node

            state = _build_analysis_state(p1_telemetry_events)
            result = await root_cause_node(state)

        assert "root_cause" in result
        assert isinstance(result["root_cause"], str)
        assert len(result["root_cause"]) > 10

    @pytest.mark.asyncio
    async def test_retrieval_context_populated(
        self, p1_telemetry_events: list[TelemetryEvent]
    ) -> None:
        """Retrieval context should be stored in the state for downstream use."""
        contexts = [
            "Database connection pool exhaustion pattern.",
            "Similar incident resolved by increasing max_connections.",
        ]

        with (
            patch("src.agents.root_cause_agent.HybridRetriever") as MockRetriever,
            patch("src.agents.root_cause_agent.LLMClient") as MockLLM,
        ):
            retriever_inst = AsyncMock()
            retriever_inst.retrieve = AsyncMock(
                return_value=[
                    type("R", (), {"text": t, "score": 0.85})()
                    for t in contexts
                ]
            )
            MockRetriever.return_value = retriever_inst

            llm_inst = AsyncMock()
            llm_inst.generate = AsyncMock(return_value="Root cause identified.")
            MockLLM.return_value = llm_inst

            from src.agents.root_cause_agent import root_cause_node

            state = _build_analysis_state(p1_telemetry_events)
            result = await root_cause_node(state)

        assert "retrieval_context" in result
        assert isinstance(result["retrieval_context"], list)
        assert len(result["retrieval_context"]) > 0

    @pytest.mark.asyncio
    async def test_handles_empty_retrieval(
        self, p1_telemetry_events: list[TelemetryEvent]
    ) -> None:
        """When retrieval returns nothing, the agent should still produce output."""
        with (
            patch("src.agents.root_cause_agent.HybridRetriever") as MockRetriever,
            patch("src.agents.root_cause_agent.LLMClient") as MockLLM,
        ):
            retriever_inst = AsyncMock()
            retriever_inst.retrieve = AsyncMock(return_value=[])
            MockRetriever.return_value = retriever_inst

            llm_inst = AsyncMock()
            llm_inst.generate = AsyncMock(
                return_value="Unable to find similar past incidents. Analysis based on telemetry alone."
            )
            MockLLM.return_value = llm_inst

            from src.agents.root_cause_agent import root_cause_node

            state = _build_analysis_state(p1_telemetry_events)
            result = await root_cause_node(state)

        assert "root_cause" in result
        assert len(result["root_cause"]) > 0
