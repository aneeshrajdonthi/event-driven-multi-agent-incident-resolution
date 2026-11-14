"""Kafka consumer / producer wrappers and schema definitions."""

from src.kafka.consumer import TelemetryConsumer
from src.kafka.producer import TelemetryProducer

__all__ = ["TelemetryConsumer", "TelemetryProducer"]
