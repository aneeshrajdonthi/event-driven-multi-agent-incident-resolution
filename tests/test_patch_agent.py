"""Tests for the patch agent — generated patches must be AST-parseable Python."""

from __future__ import annotations

import ast
import json
from unittest.mock import AsyncMock, patch

import pytest

from src.models import CodePatch, IncidentState, TelemetryEvent, TriageResult


def _build_patch_state(events: list[TelemetryEvent]) -> IncidentState:
    """State ready for the patch-generation step."""
    return IncidentState(
        events=[e.model_dump(mode="json") for e in events],
        triage_result=TriageResult(
            severity="P1",
            affected_services=["payment-service"],
            escalation_needed=True,
            summary="Critical failure.",
        ),
        root_cause="Connection pool exhaustion in payment-service.",
        affected_services=["payment-service"],
        patches=[],
        status="patching",
        retrieval_context=[
            "Past fix: increase CONN_POOL_MAX from 5 to 50.",
            "payment_service.py contains the connection pool config.",
        ],
        conversation_history=[],
    )


VALID_ORIGINAL = """\
import asyncio

CONN_POOL_MAX = 5

async def get_connection():
    return await pool.acquire()
"""

VALID_PATCHED = """\
import asyncio

CONN_POOL_MAX = 50

async def get_connection():
    return await pool.acquire()
"""


class TestPatchAgent:
    """Patch agent must produce syntactically valid Python code."""

    @pytest.mark.asyncio
    async def test_generated_patch_is_ast_parseable(
        self, p1_telemetry_events: list[TelemetryEvent]
    ) -> None:
        """The patched_code output must parse with ast.parse() without errors."""
        patch_response = json.dumps(
            {
                "file_path": "payment_service.py",
                "original_code": VALID_ORIGINAL,
                "patched_code": VALID_PATCHED,
                "explanation": "Increased connection pool max to handle load.",
                "confidence": 0.92,
            }
        )

        with patch("src.agents.patch_agent.LLMClient") as MockLLM:
            llm_inst = AsyncMock()
            llm_inst.generate = AsyncMock(return_value=patch_response)
            MockLLM.return_value = llm_inst

            from src.agents.patch_agent import patch_node

            state = _build_patch_state(p1_telemetry_events)
            result = await patch_node(state)

        assert "patches" in result
        assert isinstance(result["patches"], list)
        assert len(result["patches"]) >= 1

        for p in result["patches"]:
            patched_code = p.get("patched_code") or p.patched_code if hasattr(p, "patched_code") else p["patched_code"]
            # Must be valid Python — this is the core assertion
            tree = ast.parse(patched_code)
            assert isinstance(tree, ast.Module)

    @pytest.mark.asyncio
    async def test_patch_contains_required_fields(
        self, p1_telemetry_events: list[TelemetryEvent]
    ) -> None:
        """Each patch must have file_path, original_code, patched_code, explanation."""
        patch_response = json.dumps(
            {
                "file_path": "order_service.py",
                "original_code": "timeout = 5",
                "patched_code": "timeout = 30",
                "explanation": "Increased timeout to prevent premature disconnects.",
                "confidence": 0.85,
            }
        )

        with patch("src.agents.patch_agent.LLMClient") as MockLLM:
            llm_inst = AsyncMock()
            llm_inst.generate = AsyncMock(return_value=patch_response)
            MockLLM.return_value = llm_inst

            from src.agents.patch_agent import patch_node

            state = _build_patch_state(p1_telemetry_events)
            result = await patch_node(state)

        for p in result["patches"]:
            raw = p if isinstance(p, dict) else p.model_dump()
            assert "file_path" in raw
            assert "original_code" in raw
            assert "patched_code" in raw
            assert "explanation" in raw
            assert "confidence" in raw

    @pytest.mark.asyncio
    async def test_multiple_patches(
        self, p1_telemetry_events: list[TelemetryEvent]
    ) -> None:
        """Agent can return multiple patches for different files."""
        patches_data = json.dumps(
            [
                {
                    "file_path": "payment_service.py",
                    "original_code": "CONN_POOL_MAX = 5",
                    "patched_code": "CONN_POOL_MAX = 50",
                    "explanation": "Increase pool.",
                    "confidence": 0.9,
                },
                {
                    "file_path": "gateway_service.py",
                    "original_code": "RETRY_COUNT = 0",
                    "patched_code": "RETRY_COUNT = 3",
                    "explanation": "Add retries.",
                    "confidence": 0.8,
                },
            ]
        )

        with patch("src.agents.patch_agent.LLMClient") as MockLLM:
            llm_inst = AsyncMock()
            llm_inst.generate = AsyncMock(return_value=patches_data)
            MockLLM.return_value = llm_inst

            from src.agents.patch_agent import patch_node

            state = _build_patch_state(p1_telemetry_events)
            result = await patch_node(state)

        assert len(result["patches"]) >= 2

    def test_valid_python_ast_parsing(self) -> None:
        """Standalone test that our assertion method (ast.parse) works correctly."""
        valid_code = "x = 1\ndef foo():\n    return x + 1\n"
        tree = ast.parse(valid_code)
        assert isinstance(tree, ast.Module)
        assert len(tree.body) == 2

    def test_invalid_python_fails_ast_parsing(self) -> None:
        """ast.parse must raise SyntaxError on invalid Python."""
        invalid_code = "def foo(\n    return x ++"
        with pytest.raises(SyntaxError):
            ast.parse(invalid_code)
