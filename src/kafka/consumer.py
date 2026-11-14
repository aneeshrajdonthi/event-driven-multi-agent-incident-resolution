"""Async Kafka consumer for telemetry events."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException

from src.config import get_settings
from src.models import TelemetryEvent

logger = logging.getLogger(__name__)

_DEFAULT_TOPIC = "telemetry-events"
_BATCH_SIZE = 50
_POLL_TIMEOUT = 1.0  # seconds


class TelemetryConsumer:
    """Consume telemetry events from Kafka and dispatch them in batches."""

    def __init__(
        self,
        topic: str = _DEFAULT_TOPIC,
        group_id: str = "incident-resolution-group",
        bootstrap_servers: str | None = None,
    ) -> None:
        settings = get_settings()
        self._topic = topic
        self._conf: dict[str, Any] = {
            "bootstrap.servers": bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "max.poll.interval.ms": 300_000,
        }
        self._consumer: Consumer | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_consumer(self) -> Consumer:
        if self._consumer is None:
            self._consumer = Consumer(self._conf)
            self._consumer.subscribe([self._topic])
            logger.info(
                "Kafka consumer subscribed to '%s' (group=%s)",
                self._topic,
                self._conf["group.id"],
            )
        return self._consumer

    async def consume_events(
        self,
        callback: Callable[[list[TelemetryEvent]], Coroutine[Any, Any, None]],
        batch_size: int = _BATCH_SIZE,
    ) -> None:
        """Poll Kafka in a loop, batching messages and invoking *callback*.

        The *callback* receives a list of ``TelemetryEvent`` objects.  After
        a successful callback the consumer commits offsets.
        """
        consumer = self._ensure_consumer()
        self._running = True
        batch: list[TelemetryEvent] = []

        try:
            while self._running:
                msg = await asyncio.to_thread(consumer.poll, _POLL_TIMEOUT)

                if msg is None:
                    # No message within timeout – flush any partial batch
                    if batch:
                        await self._flush(batch, callback, consumer)
                        batch = []
                    continue

                if msg.error():
                    self._handle_error(msg.error())
                    continue

                try:
                    payload = json.loads(msg.value().decode("utf-8"))
                    event = TelemetryEvent(**payload)
                    batch.append(event)
                except (json.JSONDecodeError, ValueError) as exc:
                    logger.warning("Skipping malformed message: %s", exc)
                    continue

                if len(batch) >= batch_size:
                    await self._flush(batch, callback, consumer)
                    batch = []
        except KeyboardInterrupt:
            logger.info("Consumer interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        """Signal the consumer loop to stop and clean up."""
        self._running = False
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None
            logger.info("Kafka consumer closed")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _flush(
        batch: list[TelemetryEvent],
        callback: Callable[[list[TelemetryEvent]], Coroutine[Any, Any, None]],
        consumer: Consumer,
    ) -> None:
        try:
            await callback(batch)
            consumer.commit(asynchronous=False)
            logger.debug("Committed offsets after processing %d events", len(batch))
        except Exception:
            logger.exception("Callback failed; offsets NOT committed")

    @staticmethod
    def _handle_error(error: KafkaError) -> None:
        if error.code() == KafkaError._PARTITION_EOF:
            logger.debug("Reached end of partition")
        elif error.code() == KafkaError._ALL_BROKERS_DOWN:
            logger.error("All Kafka brokers are down")
            raise KafkaException(error)
        else:
            logger.error("Kafka error: %s", error)
