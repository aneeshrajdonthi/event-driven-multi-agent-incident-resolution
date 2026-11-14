"""Cross-encoder reranker using sentence-transformers."""

from __future__ import annotations

import logging

from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Reranker:
    """Rerank candidate documents against a query using a cross-encoder."""

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        logger.info("Loading cross-encoder model '%s' …", model_name)
        self._model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """Return the *top_k* documents reranked by cross-encoder score.

        Returns a list of ``(document, score)`` pairs sorted by descending
        relevance.
        """
        if not documents:
            return []

        pairs = [[query, doc] for doc in documents]
        scores = self._model.predict(pairs)

        scored = sorted(
            zip(documents, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(doc, float(score)) for doc, score in scored[:top_k]]
