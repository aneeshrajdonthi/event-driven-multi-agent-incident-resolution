"""Tests for Pydantic domain models — serialization & validation."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.models import (
    CodePatch,
    IncidentState,
    ResolutionReport,
    TelemetryEvent,
    TriageResult,
)


# ── TelemetryEvent ─────────────────────────────────────────────────────────

class TestTelemetryEvent:
    """Round-trip and validation tests for TelemetryEvent."""

    def test_serialize_deserialize(self) -> None:
        event = TelemetryEvent(
            service_name="order-service",
            metric_name="latency_p99",
            value=320.5,
            timestamp=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            severity="warning",
            trace_id="abc123",
            metadata={"unit": "ms"},
        )
        raw = event.model_dump(mode="json")
        restored = TelemetryEvent.model_validate(raw)

        assert restored.service_name == "order-service"
        assert restored.metric_name == "latency_p99"
        assert restored.value == 320.5
        assert restored.severity == "warning"
        assert restored.trace_id == "abc123"
        assert restored.metadata == {"unit": "ms"}

    def test_json_round_trip(self) -> None:
        event = TelemetryEvent(
            service_name="api-gw",
            metric_name="error_rate",
            value=0.12,
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        json_str = event.model_dump_json()
        restored = TelemetryEvent.model_validate_json(json_str)
        assert restored.service_name == event.service_name
        assert restored.value == event.value

    def test_defaults(self) -> None:
        event = TelemetryEvent(
            service_name="svc",
            metric_name="cpu",
            value=55.0,
            timestamp=datetime.now(tz=timezone.utc),
        )
        assert event.severity == "info"
        assert isinstance(event.trace_id, str) and len(event.trace_id) > 0
        assert event.metadata == {}

    def test_invalid_value_type_rejected(self) -> None:
        with pytest.raises(Exception):  # ValidationError
            TelemetryEvent(
                service_name="svc",
                metric_name="cpu",
                value="not-a-number",  # type: ignore[arg-type]
                timestamp=datetime.now(tz=timezone.utc),
            )


# ── CodePatch ──────────────────────────────────────────────────────────────

class TestCodePatch:
    """Round-trip and validation tests for CodePatch."""

    def test_serialize_deserialize(self) -> None:
        patch = CodePatch(
            file_path="app/main.py",
            original_code="x = 1",
            patched_code="x = 2",
            explanation="Fix off-by-one.",
            confidence=0.95,
        )
        data = patch.model_dump(mode="json")
        restored = CodePatch.model_validate(data)
        assert restored.file_path == "app/main.py"
        assert restored.confidence == 0.95
        assert restored.explanation == "Fix off-by-one."

    def test_confidence_bounds(self) -> None:
        with pytest.raises(Exception):
            CodePatch(
                file_path="f.py",
                original_code="",
                patched_code="",
                explanation="",
                confidence=1.5,  # > 1.0
            )
        with pytest.raises(Exception):
            CodePatch(
                file_path="f.py",
                original_code="",
                patched_code="",
                explanation="",
                confidence=-0.1,  # < 0.0
            )

    def test_json_round_trip(self) -> None:
        patch = CodePatch(
            file_path="svc.py",
            original_code="a()",
            patched_code="b()",
            explanation="Refactor",
            confidence=0.5,
        )
        restored = CodePatch.model_validate_json(patch.model_dump_json())
        assert restored == patch


# ── ResolutionReport ───────────────────────────────────────────────────────

class TestResolutionReport:
    """Round-trip tests for ResolutionReport."""

    def test_serialize_deserialize(self) -> None:
        report = ResolutionReport(
            root_cause="Memory leak in connection pool.",
            patches=[
                CodePatch(
                    file_path="pool.py",
                    original_code="size=5",
                    patched_code="size=50",
                    explanation="Increase pool",
                    confidence=0.9,
                )
            ],
            metrics={"mttr_seconds": 120},
        )
        raw = report.model_dump(mode="json")
        restored = ResolutionReport.model_validate(raw)

        assert restored.root_cause == "Memory leak in connection pool."
        assert len(restored.patches) == 1
        assert restored.patches[0].file_path == "pool.py"
        assert restored.metrics["mttr_seconds"] == 120
        assert isinstance(restored.incident_id, str)
        assert isinstance(restored.timestamp, datetime)

    def test_defaults_auto_generated(self) -> None:
        report = ResolutionReport(root_cause="unknown")
        assert len(report.incident_id) > 0
        assert report.patches == []
        assert report.metrics == {}


# ── TriageResult ───────────────────────────────────────────────────────────

class TestTriageResult:
    """Tests for the TriageResult TypedDict."""

    def test_construction(self) -> None:
        result: TriageResult = {
            "severity": "P2",
            "affected_services": ["svc-a", "svc-b"],
            "escalation_needed": False,
            "summary": "Elevated error rate.",
        }
        assert result["severity"] == "P2"
        assert len(result["affected_services"]) == 2

    def test_json_serializable(self) -> None:
        result: TriageResult = {
            "severity": "P1",
            "affected_services": ["payment"],
            "escalation_needed": True,
            "summary": "Critical outage.",
        }
        raw = json.dumps(result)
        restored = json.loads(raw)
        assert restored["severity"] == "P1"
        assert restored["escalation_needed"] is True


# ── IncidentState ──────────────────────────────────────────────────────────

class TestIncidentState:
    """Tests for the IncidentState TypedDict (LangGraph state)."""

    def test_construction_minimal(self) -> None:
        state: IncidentState = {  # type: ignore[typeddict-item]
            "events": [],
            "status": "triage",
        }
        assert state["status"] == "triage"
        assert state["events"] == []

    def test_full_state_round_trip(self, mock_telemetry_events) -> None:
        state: IncidentState = {
            "events": [e.model_dump(mode="json") for e in mock_telemetry_events],
            "triage_result": {
                "severity": "P2",
                "affected_services": ["payment-service"],
                "escalation_needed": False,
                "summary": "test",
            },
            "root_cause": "connection pool exhaustion",
            "affected_services": ["payment-service"],
            "patches": [],
            "status": "analysis",
            "retrieval_context": ["ctx-1"],
            "conversation_history": [{"role": "system", "content": "hello"}],
        }
        raw = json.dumps(state)
        restored = json.loads(raw)

        assert len(restored["events"]) == len(mock_telemetry_events)
        assert restored["root_cause"] == "connection pool exhaustion"
        assert restored["status"] == "analysis"
