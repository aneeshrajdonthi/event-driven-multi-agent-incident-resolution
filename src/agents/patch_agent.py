"""Patch generation agent — LangGraph node with AST validation."""

from __future__ import annotations

import ast
import json
import logging
from typing import Any

from src.llm.client import LLMClient
from src.llm.cache import LLMCache
from src.llm.prompts import PATCH_SYSTEM_PROMPT, PATCH_USER_TEMPLATE
from src.models import CodePatch, IncidentState

logger = logging.getLogger(__name__)

_llm = LLMClient()
_cache = LLMCache()


def _validate_python_syntax(code: str) -> bool:
    """Return True if *code* is syntactically valid Python."""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


async def patch_node(state: IncidentState) -> dict[str, Any]:
    """Generate code patches for the identified root cause.

    Validates each patch with the Python ``ast`` module and drops invalid
    ones.  Returns partial state update with ``patches`` list.
    """
    root_cause = state.get("root_cause", "")
    retrieval_ctx = state.get("retrieval_context", [])
    retrieval_text = "\n---\n".join(retrieval_ctx) if retrieval_ctx else "(none)"

    prompt = PATCH_USER_TEMPLATE.format(
        root_cause=root_cause,
        retrieval_context=retrieval_text,
    )

    cached = await _cache.get(prompt, PATCH_SYSTEM_PROMPT)
    if cached is not None:
        raw = cached
    else:
        raw = await _llm.generate(
            prompt,
            system_prompt=PATCH_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=4096,
        )
        await _cache.set(prompt, raw, PATCH_SYSTEM_PROMPT)

    # Parse patches from LLM response
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        import re

        match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
        parsed = json.loads(match.group(1).strip()) if match else []

    if not isinstance(parsed, list):
        parsed = [parsed]

    valid_patches: list[dict[str, Any]] = []
    for item in parsed:
        try:
            patch = CodePatch.model_validate(item)
        except Exception:
            logger.warning("Skipping invalid patch payload: %s", item)
            continue

        # AST validation for Python files
        if patch.file_path.endswith(".py"):
            if not _validate_python_syntax(patch.patched_code):
                logger.warning(
                    "Patch for %s failed AST validation — skipping",
                    patch.file_path,
                )
                continue

        valid_patches.append(patch.model_dump())

    logger.info(
        "Patch generation complete — %d valid patches out of %d candidates",
        len(valid_patches),
        len(parsed),
    )

    return {
        "patches": valid_patches,
        "status": "review",
        "conversation_history": state.get("conversation_history", [])
        + [
            {
                "role": "assistant",
                "content": f"Generated {len(valid_patches)} patch(es).",
            }
        ],
    }
