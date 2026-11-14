"""Avro-style JSON-schema definitions for telemetry events and resolution reports.

These schemas are used for runtime validation of Kafka messages.  They follow
JSON Schema Draft-7 conventions but are expressed as plain Python dicts so
they can be used with ``jsonschema.validate()`` without an external schema
registry.
"""

from __future__ import annotations

TELEMETRY_EVENT_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "TelemetryEvent",
    "description": "A single telemetry / observability event.",
    "type": "object",
    "required": [
        "service_name",
        "metric_name",
        "value",
        "timestamp",
    ],
    "properties": {
        "service_name": {
            "type": "string",
            "description": "Name of the originating microservice.",
        },
        "metric_name": {
            "type": "string",
            "description": "Metric identifier (e.g. cpu_usage_percent).",
        },
        "value": {
            "type": "number",
            "description": "Numeric metric value.",
        },
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "ISO-8601 timestamp of the event.",
        },
        "severity": {
            "type": "string",
            "enum": ["info", "warning", "error", "critical"],
            "default": "info",
        },
        "trace_id": {
            "type": "string",
            "description": "Distributed-trace correlation ID.",
        },
        "metadata": {
            "type": "object",
            "description": "Arbitrary key-value metadata.",
            "additionalProperties": True,
        },
    },
    "additionalProperties": False,
}


RESOLUTION_REPORT_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "ResolutionReport",
    "description": "Output of the incident-resolution pipeline.",
    "type": "object",
    "required": ["incident_id", "root_cause", "patches", "timestamp"],
    "properties": {
        "incident_id": {
            "type": "string",
        },
        "root_cause": {
            "type": "string",
        },
        "patches": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "file_path",
                    "original_code",
                    "patched_code",
                    "explanation",
                    "confidence",
                ],
                "properties": {
                    "file_path": {"type": "string"},
                    "original_code": {"type": "string"},
                    "patched_code": {"type": "string"},
                    "explanation": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "additionalProperties": False,
            },
        },
        "metrics": {
            "type": "object",
            "additionalProperties": True,
        },
        "timestamp": {
            "type": "string",
            "format": "date-time",
        },
    },
    "additionalProperties": False,
}


CODE_PATCH_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CodePatch",
    "description": "A generated code patch for a single file.",
    "type": "object",
    "required": [
        "file_path",
        "original_code",
        "patched_code",
        "explanation",
        "confidence",
    ],
    "properties": {
        "file_path": {"type": "string"},
        "original_code": {"type": "string"},
        "patched_code": {"type": "string"},
        "explanation": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "additionalProperties": False,
}
