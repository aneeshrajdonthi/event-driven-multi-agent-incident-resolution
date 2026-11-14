"""BM25 (Okapi) sparse retrieval index."""

from __future__ import annotations

import logging
import re
from typing import Sequence

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# Simple stop-words list (extend as needed)
_STOP_WORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "of", "in", "to", "for",
    "with", "on", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "and", "but", "or", "nor", "not", "so", "yet",
    "it", "its", "this", "that", "these", "those",
}


def _tokenize(text: str) -> list[str]:
    """Lower-case, strip non-alpha-numeric, remove stop-words."""
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS]


class BM25Index:
    """In-memory BM25 sparse retrieval index over a set of documents."""

    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._corpus_tokens: list[list[str]] = []
        self._documents: list[str] = []

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build_index(self, documents: list[str]) -> None:
        """Tokenize *documents* and build the BM25Okapi index."""
        self._documents = list(documents)
        self._corpus_tokens = [_tokenize(doc) for doc in self._documents]
        self._bm25 = BM25Okapi(self._corpus_tokens)
        logger.info("BM25 index built with %d documents", len(self._documents))

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """Return *(doc_id, score)* pairs sorted by descending BM25 score."""
        if self._bm25 is None:
            raise RuntimeError("Index not built – call build_index() first")

        query_tokens = _tokenize(query)
        scores = self._bm25.get_scores(query_tokens)

        scored = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_document(self, doc_id: int) -> str:
        """Retrieve the original document text by index."""
        return self._documents[doc_id]

    @property
    def size(self) -> int:
        return len(self._documents)
