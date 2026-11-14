"""Root-cause analysis agent — LangGraph node."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.llm.client import LLMClient
from src.llm.cache import LLMCache
from src.llm.prompts import ROOT_CAUSE_SYSTEM_PROMPT, ROOT_CAUSE_USER_TEMPLATE
from src.models import IncidentState

logger = logging.getLogger(__name__)

_llm = LLMClient()
_cache = LLMCache()

# Lazy singleton for the retrieval layer — initialised on first call.
_retriever: Any | None = None


def _get_retriever() -> Any:
    """Build a :class:`HybridRetriever` on first access."""
    global _retriever
    if _retriever is None:
        from src.retrieval.hybrid import HybridRetriever
        from src.retrieval.vector_store import VectorStore
        from src.retrieval.bm25_index import BM25Index
        from src.retrieval.reranker import Reranker

        _retriever = HybridRetriever(
            vector_store=VectorStore(),
            bm25_index=BM25Index(),
            reranker=Reranker(),
        )
    return _retriever


async def root_cause_node(state: IncidentState) -> dict[str, Any]:
    """Identify the root cause using triage context and hybrid retrieval.

    Returns partial state update with ``root_cause`` and ``retrieval_context``.
    """
    triage = state.get("triage_result", {})
    events_json = json.dumps(state.get("events", []), indent=2, default=str)

    # Hybrid retrieval (Qdrant dense + BM25 sparse + cross-encoder reranking)
    query = (
        f"Incident affecting {', '.join(triage.get('affected_services', []))}. "
        f"{triage.get('summary', '')}"
    )
    try:
        retriever = _get_retriever()
        results = await retriever.retrieve(query, top_k=5)
        retrieval_docs = [r.content for r in results]
    except Exception:
        logger.warning("Retrieval failed — proceeding without context", exc_info=True)
        retrieval_docs = []

    retrieval_text = "\n---\n".join(retrieval_docs) if retrieval_docs else "(none)"

    prompt = ROOT_CAUSE_USER_TEMPLATE.format(
        severity=triage.get("severity", "unknown"),
        affected_services=", ".join(triage.get("affected_services", [])),
        triage_summary=triage.get("summary", ""),
        events_json=events_json,
        retrieval_context=retrieval_text,
    )

    cached = await _cache.get(prompt, ROOT_CAUSE_SYSTEM_PROMPT)
    if cached is not None:
        root_cause = cached
    else:
        root_cause = await _llm.generate(
            prompt,
            system_prompt=ROOT_CAUSE_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=2048,
        )
        await _cache.set(prompt, root_cause, ROOT_CAUSE_SYSTEM_PROMPT)

    logger.info("Root-cause analysis complete (%d chars)", len(root_cause))

    return {
        "root_cause": root_cause,
        "retrieval_context": retrieval_docs,
        "status": "patching",
        "conversation_history": state.get("conversation_history", [])
        + [{"role": "assistant", "content": f"Root cause: {root_cause[:200]}…"}],
    }
