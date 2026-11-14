"""Triage agent — LangGraph node that classifies incident severity."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.llm.client import LLMClient
from src.llm.cache import LLMCache
from src.llm.prompts import TRIAGE_SYSTEM_PROMPT, TRIAGE_USER_TEMPLATE
from src.models import IncidentState, TriageResult

logger = logging.getLogger(__name__)

_llm = LLMClient()
_cache = LLMCache()


async def triage_node(state: IncidentState) -> dict[str, Any]:
    """Analyze telemetry events and produce a triage classification.

    Returns partial state update with ``triage_result`` and ``status``.
    """
    events_json = json.dumps(state.get("events", []), indent=2, default=str)

    prompt = TRIAGE_USER_TEMPLATE.format(events_json=events_json)

    # Check cache first
    cached = await _cache.get(prompt, TRIAGE_SYSTEM_PROMPT)
    if cached is not None:
        result = json.loads(cached)
    else:
        raw = await _llm.generate(
            prompt,
            system_prompt=TRIAGE_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=1024,
        )
        # Try to parse JSON from the response
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            import re

            match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
            result = json.loads(match.group(1).strip()) if match else {
                "severity": "P3",
                "affected_services": [],
                "escalation_needed": False,
                "summary": raw,
            }
        await _cache.set(prompt, json.dumps(result), TRIAGE_SYSTEM_PROMPT)

    triage: TriageResult = {
        "severity": result.get("severity", "P3"),
        "affected_services": result.get("affected_services", []),
        "escalation_needed": result.get("escalation_needed", False),
        "summary": result.get("summary", ""),
    }

    logger.info(
        "Triage complete — severity=%s affected=%s escalate=%s",
        triage["severity"],
        triage["affected_services"],
        triage["escalation_needed"],
    )

    return {
        "triage_result": triage,
        "affected_services": triage["affected_services"],
        "status": "analysis",
        "conversation_history": state.get("conversation_history", [])
        + [{"role": "assistant", "content": f"Triage: {triage['summary']}"}],
    }
