"""Hybrid retriever – dense (Qdrant) + sparse (BM25) + cross-encoder reranker."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from src.retrieval.bm25_index import BM25Index
from src.retrieval.reranker import Reranker
from src.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# RetrievalResult model
# ------------------------------------------------------------------


class RetrievalResult(BaseModel):
    """A single search result returned by the hybrid retriever."""

    content: str
    score: float
    source: str  # "vector" | "bm25" | "hybrid"
    metadata: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------
# Reciprocal Rank Fusion helper
# ------------------------------------------------------------------

_RRF_K = 60  # standard RRF constant


def _reciprocal_rank_fusion(
    *ranked_lists: list[str],
    k: int = _RRF_K,
) -> list[tuple[str, float]]:
    """Merge several ranked document lists via RRF and return fused scores."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ------------------------------------------------------------------
# HybridRetriever
# ------------------------------------------------------------------


class HybridRetriever:
    """Compose vector search, BM25, and cross-encoder reranking.

    Retrieval strategy:
    1. Top-20 from Qdrant dense search.
    2. Top-20 from BM25 sparse search.
    3. Merge via Reciprocal Rank Fusion.
    4. Rerank top-15 with the cross-encoder.
    5. Return top-k results.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        reranker: Reranker,
    ) -> None:
        self._vector = vector_store
        self._bm25 = bm25_index
        self._reranker = reranker

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Run the full hybrid retrieval pipeline and return *top_k* results."""

        # 1. Dense retrieval -----------------------------------------------
        dense_results = await self._vector.search(query, top_k=20)
        dense_docs: list[str] = [r["content"] for r in dense_results]
        dense_meta: dict[str, dict[str, Any]] = {
            r["content"]: r.get("metadata", {}) for r in dense_results
        }

        # 2. Sparse retrieval ----------------------------------------------
        bm25_hits = self._bm25.search(query, top_k=20)
        sparse_docs: list[str] = [
            self._bm25.get_document(doc_id) for doc_id, _score in bm25_hits
        ]

        # 3. Reciprocal Rank Fusion ----------------------------------------
        fused = _reciprocal_rank_fusion(dense_docs, sparse_docs)
        fused_docs = [doc for doc, _ in fused[:15]]

        # 4. Cross-encoder reranking ---------------------------------------
        reranked = self._reranker.rerank(query, fused_docs, top_k=top_k)

        # 5. Package results -----------------------------------------------
        results: list[RetrievalResult] = []
        for doc, score in reranked:
            source = "hybrid"
            if doc in dense_meta and doc not in sparse_docs:
                source = "vector"
            elif doc not in dense_meta and doc in sparse_docs:
                source = "bm25"

            results.append(
                RetrievalResult(
                    content=doc,
                    score=score,
                    source=source,
                    metadata=dense_meta.get(doc, {}),
                )
            )

        logger.info(
            "Hybrid retrieval: dense=%d, sparse=%d, fused=%d, returned=%d",
            len(dense_docs),
            len(sparse_docs),
            len(fused_docs),
            len(results),
        )
        return results
