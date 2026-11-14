"""Prompt templates for each agent in the incident resolution pipeline."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

TRIAGE_SYSTEM_PROMPT: str = (
    "You are an expert Site Reliability Engineer performing incident triage. "
    "Analyze the telemetry events provided and produce a structured triage "
    "assessment.  Classify severity as P1 (critical, customer-facing outage), "
    "P2 (major degradation), P3 (minor issue), or P4 (cosmetic / low impact). "
    "Identify all affected services and decide whether human escalation is needed."
)

TRIAGE_USER_TEMPLATE: str = (
    "## Telemetry Events\n\n"
    "{events_json}\n\n"
    "## Instructions\n"
    "1. Classify severity (P1-P4).\n"
    "2. List affected services.\n"
    "3. Decide if escalation is needed (true/false).\n"
    "4. Write a concise summary.\n\n"
    "Respond ONLY with valid JSON matching this schema:\n"
    '{{"severity": "P1|P2|P3|P4", "affected_services": ["svc"], '
    '"escalation_needed": true, "summary": "..."}}'
)

# ---------------------------------------------------------------------------

ROOT_CAUSE_SYSTEM_PROMPT: str = (
    "You are an expert distributed-systems debugger.  Given telemetry events, "
    "triage context, and retrieved documents from past incidents and the "
    "codebase, identify the most likely root cause of the incident."
)

ROOT_CAUSE_USER_TEMPLATE: str = (
    "## Triage Summary\n"
    "Severity: {severity}\n"
    "Affected services: {affected_services}\n"
    "Summary: {triage_summary}\n\n"
    "## Telemetry Events\n\n{events_json}\n\n"
    "## Retrieved Context\n\n{retrieval_context}\n\n"
    "## Instructions\n"
    "Identify the root cause.  Be specific about the component, failure mode, "
    "and the chain of events.  Return a plain-text explanation (no JSON)."
)

# ---------------------------------------------------------------------------

PATCH_SYSTEM_PROMPT: str = (
    "You are a senior software engineer.  Given the root cause analysis and "
    "relevant code context, generate minimal, safe code patches that fix the "
    "underlying issue.  Each patch must compile and pass basic linting."
)

PATCH_USER_TEMPLATE: str = (
    "## Root Cause\n\n{root_cause}\n\n"
    "## Relevant Code Context\n\n{retrieval_context}\n\n"
    "## Instructions\n"
    "Generate one or more code patches.  For each patch provide:\n"
    "- file_path\n"
    "- original_code  (the exact snippet being replaced)\n"
    "- patched_code   (the replacement)\n"
    "- explanation\n"
    "- confidence     (0.0 – 1.0)\n\n"
    "Respond ONLY with a JSON array of patch objects."
)
