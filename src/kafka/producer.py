"""Kafka producer for resolution reports and sample telemetry generation."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from confluent_kafka import Producer

from src.config import get_settings
from src.models import TelemetryEvent

logger = logging.getLogger(__name__)

_RESOLUTIONS_TOPIC = "incident-resolutions"


def _delivery_report(err: Any, msg: Any) -> None:
    """Called once per produced message to indicate delivery result."""
    if err is not None:
        logger.error("Message delivery failed: %s", err)
    else:
        logger.debug("Message delivered to %s [%d]", msg.topic(), msg.partition())


class TelemetryProducer:
    """Publish events to Kafka topics."""

    def __init__(self, bootstrap_servers: str | None = None) -> None:
        settings = get_settings()
        self._conf: dict[str, str] = {
            "bootstrap.servers": bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS,
            "client.id": "incident-producer",
        }
        self._producer: Producer | None = None

    def _ensure_producer(self) -> Producer:
        if self._producer is None:
            self._producer = Producer(self._conf)
        return self._producer

    # ------------------------------------------------------------------
    # Produce
    # ------------------------------------------------------------------

    async def produce_event(self, topic: str, event: dict[str, Any] | str) -> None:
        """Serialize and produce a single event to *topic*."""
        producer = self._ensure_producer()
        payload = event if isinstance(event, str) else json.dumps(event, default=str)

        await asyncio.to_thread(
            producer.produce,
            topic,
            value=payload.encode("utf-8"),
            callback=_delivery_report,
        )
        # Trigger delivery callbacks
        await asyncio.to_thread(producer.flush, 5)

    async def publish_resolution(self, report: dict[str, Any]) -> None:
        """Convenience wrapper for publishing to the resolutions topic."""
        await self.produce_event(_RESOLUTIONS_TOPIC, report)

    def close(self) -> None:
        if self._producer is not None:
            self._producer.flush(10)
            self._producer = None

    # ------------------------------------------------------------------
    # Sample telemetry generation (demo / testing)
    # ------------------------------------------------------------------

    @staticmethod
    def generate_sample_telemetry() -> TelemetryEvent:
        """Create a single randomised telemetry event for testing."""
        services = [
            "order-service",
            "payment-service",
            "inventory-service",
            "notification-service",
            "gateway-service",
        ]
        metrics = [
            ("cpu_usage_percent", 0.0, 100.0),
            ("memory_usage_mb", 128.0, 8192.0),
            ("http_5xx_rate", 0.0, 50.0),
            ("request_latency_ms", 5.0, 5000.0),
            ("connection_pool_active", 0.0, 200.0),
            ("disk_usage_percent", 10.0, 99.0),
            ("gc_pause_ms", 0.0, 3000.0),
        ]
        severities = ["info", "warning", "error", "critical"]

        metric_name, lo, hi = random.choice(metrics)
        value = round(random.uniform(lo, hi), 2)
        severity = "info"
        if value > (hi - lo) * 0.7 + lo:
            severity = "warning"
        if value > (hi - lo) * 0.85 + lo:
            severity = "error"
        if value > (hi - lo) * 0.95 + lo:
            severity = "critical"

        return TelemetryEvent(
            service_name=random.choice(services),
            metric_name=metric_name,
            value=value,
            timestamp=datetime.now(tz=timezone.utc),
            severity=severity,
            trace_id=uuid.uuid4().hex,
            metadata={"host": f"host-{random.randint(1, 10)}"},
        )
