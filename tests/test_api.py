"""Integration tests for FastAPI endpoints."""

from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.models import ResolutionReport, CodePatch


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    """Test /health returns 200 and ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_endpoint(client):
    """Test /metrics endpoint returns expected structure."""
    with patch("src.api.routes.LLMCache") as mock_cache_cls:
        mock_cache = mock_cache_cls.return_value
        mock_cache.get_metrics = AsyncMock(return_value={"hits": 5, "misses": 2, "hit_rate": 0.71})
        
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "incidents_processed" in data


def test_analyze_empty_events_bad_request(client):
    """Test /incidents/analyze with empty list returns 400."""
    response = client.post("/incidents/analyze", json=[])
    assert response.status_code == 400
    assert "At least one event is required" in response.json()["detail"]


def test_analyze_incident_and_get(client):
    """Test analyzing an incident and subsequently retrieving it."""
    mock_report = ResolutionReport(
        incident_id="INC-TEST-999",
        root_cause="Database pool exhausted by unclosed connections",
        patches=[
            CodePatch(
                file_path="payment_service.py",
                original_code="conn = acquire()",
                patched_code="async with acquire() as conn:",
                explanation="Proper connection pooling",
                confidence=0.95
            )
        ],
        metrics={"duration_ms": 120.5},
        timestamp=datetime.now(timezone.utc)
    )

    with patch("src.api.routes.run_incident_pipeline", new_callable=AsyncMock) as mock_pipeline:
        mock_pipeline.return_value = mock_report
        
        payload = [
            {
                "service_name": "payment-service",
                "metric_name": "connection_pool_active",
                "value": 200.0,
                "timestamp": "2026-11-13T12:00:00Z",
                "severity": "critical",
                "trace_id": "test-trace-api"
            }
        ]
        
        # Analyze
        res = client.post("/incidents/analyze", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["incident_id"] == "INC-TEST-999"
        assert len(data["patches"]) == 1

        # Get by ID
        get_res = client.get(f"/incidents/INC-TEST-999")
        assert get_res.status_code == 200
        assert get_res.json()["incident_id"] == "INC-TEST-999"
