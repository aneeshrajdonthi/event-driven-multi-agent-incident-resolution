"""Shared pytest fixtures for the incident resolution test suite."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.config import Settings
from src.models import (
    CodePatch,
    IncidentState,
    ResolutionReport,
    TelemetryEvent,
    TriageResult,
)


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_settings() -> Settings:
    """Return a deterministic Settings object for tests (no .env loading)."""
    return Settings(
        KAFKA_BOOTSTRAP_SERVERS="localhost:9092",
        QDRANT_HOST="localhost",
        QDRANT_PORT=6333,
        QDRANT_COLLECTION="test-incidents",
        REDIS_URL="redis://localhost:6379/1",
        VLLM_API_URL="http://localhost:8001/v1",
        GEMINI_API_KEY="test-key-not-real",
        MODEL_NAME="test-model",
        LORA_ADAPTER_PATH="",
        LOG_LEVEL="DEBUG",
    )


# ---------------------------------------------------------------------------
# Telemetry events
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_telemetry_events() -> list[TelemetryEvent]:
    """Return a batch of realistic telemetry events for testing."""
    base_ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    return [
        TelemetryEvent(
            service_name="payment-service",
            metric_name="error_rate",
            value=0.85,
            timestamp=base_ts,
            severity="critical",
            trace_id="trace-001",
            metadata={"http_status": 500, "endpoint": "/api/charge"},
        ),
        TelemetryEvent(
            service_name="payment-service",
            metric_name="latency_p99",
            value=4500.0,
            timestamp=base_ts,
            severity="error",
            trace_id="trace-002",
            metadata={"unit": "ms"},
        ),
        TelemetryEvent(
            service_name="order-service",
            metric_name="cpu_usage",
            value=95.2,
            timestamp=base_ts,
            severity="warning",
            trace_id="trace-003",
            metadata={"threshold": 80},
        ),
        TelemetryEvent(
            service_name="inventory-service",
            metric_name="memory_usage_mb",
            value=3800.0,
            timestamp=base_ts,
            severity="error",
            trace_id="trace-004",
            metadata={"limit_mb": 4096},
        ),
        TelemetryEvent(
            service_name="gateway-service",
            metric_name="request_count",
            value=12000.0,
            timestamp=base_ts,
            severity="info",
            trace_id="trace-005",
            metadata={"window": "1m"},
        ),
    ]


@pytest.fixture()
def p1_telemetry_events() -> list[TelemetryEvent]:
    """Events representing a P1 (critical) incident — cascading failures."""
    ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    return [
        TelemetryEvent(
            service_name="payment-service",
            metric_name="error_rate",
            value=0.95,
            timestamp=ts,
            severity="critical",
            metadata={"http_status": 503},
        ),
        TelemetryEvent(
            service_name="order-service",
            metric_name="error_rate",
            value=0.80,
            timestamp=ts,
            severity="critical",
            metadata={"http_status": 500},
        ),
        TelemetryEvent(
            service_name="gateway-service",
            metric_name="error_rate",
            value=0.70,
            timestamp=ts,
            severity="critical",
            metadata={"http_status": 502},
        ),
    ]


@pytest.fixture()
def p4_telemetry_events() -> list[TelemetryEvent]:
    """Events representing a P4 (low-priority) informational blip."""
    ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    return [
        TelemetryEvent(
            service_name="notification-service",
            metric_name="latency_p50",
            value=120.0,
            timestamp=ts,
            severity="info",
            metadata={"unit": "ms"},
        ),
    ]


# ---------------------------------------------------------------------------
# Qdrant mock
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_qdrant_client() -> MagicMock:
    """Return a mocked Qdrant async client."""
    client = MagicMock()

    # Simulate a search result
    scored_point = MagicMock()
    scored_point.id = "point-1"
    scored_point.score = 0.92
    scored_point.payload = {
        "text": "Previous incident: payment-service OOM due to connection pool leak.",
        "source": "incident-2024-0042",
    }
    scored_point.vector = None

    client.search = AsyncMock(return_value=[scored_point])
    client.upsert = AsyncMock(return_value=None)
    client.get_collection = AsyncMock(
        return_value=MagicMock(points_count=100, vectors_count=100)
    )
    return client


# ---------------------------------------------------------------------------
# Redis mock
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_redis_client() -> AsyncMock:
    """Return a mocked async Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)  # cache miss by default
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    redis.ping = AsyncMock(return_value=True)
    redis.close = AsyncMock(return_value=None)
    return redis


# ---------------------------------------------------------------------------
# Kafka mock
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_kafka_consumer() -> MagicMock:
    """Return a mocked Kafka consumer."""
    consumer = MagicMock()

    # Simulate a consumed message
    msg = MagicMock()
    msg.value.return_value = (
        b'{"service_name":"payment-service","metric_name":"error_rate",'
        b'"value":0.85,"timestamp":"2025-06-15T12:00:00Z",'
        b'"severity":"critical","trace_id":"trace-001","metadata":{}}'
    )
    msg.error.return_value = None
    msg.topic.return_value = "telemetry-events"
    msg.partition.return_value = 0
    msg.offset.return_value = 42

    consumer.poll = MagicMock(return_value=msg)
    consumer.subscribe = MagicMock()
    consumer.close = MagicMock()
    consumer.commit = MagicMock()
    return consumer


# ---------------------------------------------------------------------------
# LLM mock
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_llm_client() -> AsyncMock:
    """Return a mocked LLM client (src.llm.client.LLMClient)."""
    client = AsyncMock()
    client.generate = AsyncMock(return_value="Mocked LLM response")
    client.generate_structured = AsyncMock(
        return_value=MagicMock(model_dump=lambda: {"result": "mocked"})
    )
    return client


# ---------------------------------------------------------------------------
# Pre-built state helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_triage_result() -> TriageResult:
    return TriageResult(
        severity="P1",
        affected_services=["payment-service", "order-service"],
        escalation_needed=True,
        summary="Cascading failure across payment and order services.",
    )


@pytest.fixture()
def sample_code_patch() -> CodePatch:
    return CodePatch(
        file_path="payment_service.py",
        original_code="conn_pool_size = 5",
        patched_code="conn_pool_size = 50",
        explanation="Increased connection pool size to handle load spike.",
        confidence=0.88,
    )


@pytest.fixture()
def sample_incident_state(
    mock_telemetry_events: list[TelemetryEvent],
) -> IncidentState:
    """Build a minimal IncidentState dict ready for the pipeline."""
    return IncidentState(
        events=[e.model_dump(mode="json") for e in mock_telemetry_events],
        triage_result=TriageResult(
            severity="P2",
            affected_services=["payment-service"],
            escalation_needed=False,
            summary="Elevated error rate on payment-service.",
        ),
        root_cause="",
        affected_services=["payment-service"],
        patches=[],
        status="triage",
        retrieval_context=[],
        conversation_history=[],
    )
