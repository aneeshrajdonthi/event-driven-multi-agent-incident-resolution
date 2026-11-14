"""Tests for Kafka producer and consumer components."""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.kafka.producer import TelemetryProducer
from src.kafka.consumer import TelemetryConsumer
from src.models import TelemetryEvent


def test_generate_sample_telemetry():
    """Verify sample telemetry generator outputs a valid TelemetryEvent."""
    producer = TelemetryProducer(bootstrap_servers="localhost:9092")
    event = producer.generate_sample_telemetry()
    
    assert isinstance(event, TelemetryEvent)
    assert event.service_name in [
        "order-service",
        "payment-service",
        "inventory-service",
        "notification-service",
        "gateway-service",
    ]
    assert event.severity in ["critical", "error", "warning"]


@pytest.mark.asyncio
async def test_produce_event_mocked():
    """Test produce_event calls underlying Kafka producer."""
    with patch("confluent_kafka.Producer") as mock_kafka:
        instance = mock_kafka.return_value
        producer = TelemetryProducer(bootstrap_servers="localhost:9092")
        
        test_payload = {"service_name": "order-service", "metric_name": "cpu_usage", "value": 95.0}
        await producer.produce_event("telemetry-events", test_payload)
        
        instance.produce.assert_called_once()
        args, kwargs = instance.produce.call_args
        assert args[0] == "telemetry-events"
        assert json.loads(kwargs["value"].decode("utf-8")) == test_payload


@pytest.mark.asyncio
async def test_consumer_poll_dispatch():
    """Test consumer message parsing and dispatch."""
    with patch("confluent_kafka.Consumer") as mock_kafka:
        instance = mock_kafka.return_value
        mock_msg = MagicMock()
        mock_msg.error.return_value = None
        mock_msg.value.return_value = json.dumps({
            "service_name": "payment-service",
            "metric_name": "memory_leak",
            "value": 99.5,
            "timestamp": "2026-11-13T12:00:00Z",
            "severity": "critical",
            "trace_id": "test-trace-123"
        }).encode("utf-8")
        
        instance.poll.side_effect = [mock_msg, None]
        
        consumer = TelemetryConsumer(bootstrap_servers="localhost:9092")
        received_batches = []
        
        async def mock_callback(events):
            received_batches.append(events)
            consumer.stop()
            
        # Run consumer briefly
        consumer._running = True
        # poll_batch
        events = await consumer._poll_batch(batch_size=1)
        assert len(events) == 1
        assert events[0].service_name == "payment-service"
        assert events[0].metric_name == "memory_leak"
