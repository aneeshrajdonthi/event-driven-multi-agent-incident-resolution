"""Qdrant vector store wrapper with sentence-transformers embeddings."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

from src.config import get_settings

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_MAX_RETRIES = 3
_RETRY_DELAY = 2.0  # seconds


class VectorStore:
    """Thin async wrapper around Qdrant for incident-related document storage."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        embedding_model: str = _DEFAULT_MODEL,
    ) -> None:
        settings = get_settings()
        self._host = host or settings.QDRANT_HOST
        self._port = port or settings.QDRANT_PORT
        self._client = AsyncQdrantClient(host=self._host, port=self._port)
        self._encoder = SentenceTransformer(embedding_model)
        self._collection: str | None = None
        self._vector_size: int = 384

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(
        self,
        collection_name: str | None = None,
        vector_size: int = 384,
    ) -> None:
        """Create the Qdrant collection if it does not already exist.

        Retries up to ``_MAX_RETRIES`` times on transient connection errors.
        """
        settings = get_settings()
        self._collection = collection_name or settings.QDRANT_COLLECTION
        self._vector_size = vector_size

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                collections = await self._client.get_collections()
                existing = {c.name for c in collections.collections}
                if self._collection not in existing:
                    await self._client.create_collection(
                        collection_name=self._collection,
                        vectors_config=VectorParams(
                            size=self._vector_size,
                            distance=Distance.COSINE,
                        ),
                    )
                    logger.info("Created Qdrant collection '%s'", self._collection)
                else:
                    logger.info("Qdrant collection '%s' already exists", self._collection)
                return
            except (ConnectionError, OSError, UnexpectedResponse) as exc:
                logger.warning(
                    "Qdrant connection attempt %d/%d failed: %s",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                )
                if attempt == _MAX_RETRIES:
                    raise
                await asyncio.sleep(_RETRY_DELAY * attempt)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def upsert(
        self,
        documents: list[str],
        metadata: list[dict[str, Any]],
    ) -> None:
        """Embed *documents* and upsert them (with metadata) into Qdrant."""
        if not documents:
            return
        assert self._collection, "Call initialize() before upsert()"

        vectors = self._encoder.encode(documents).tolist()

        points = [
            PointStruct(
                id=idx,
                vector=vec,
                payload={"content": doc, **(meta or {})},
            )
            for idx, (doc, vec, meta) in enumerate(
                zip(documents, vectors, metadata)
            )
        ]

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                await self._client.upsert(
                    collection_name=self._collection,
                    points=points,
                )
                logger.info("Upserted %d points into '%s'", len(points), self._collection)
                return
            except (ConnectionError, OSError, UnexpectedResponse) as exc:
                logger.warning("Upsert attempt %d/%d failed: %s", attempt, _MAX_RETRIES, exc)
                if attempt == _MAX_RETRIES:
                    raise
                await asyncio.sleep(_RETRY_DELAY * attempt)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Return the *top_k* nearest documents with scores."""
        assert self._collection, "Call initialize() before search()"

        query_vector = self._encoder.encode(query).tolist()

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                results = await self._client.search(
                    collection_name=self._collection,
                    query_vector=query_vector,
                    limit=top_k,
                )
                return [
                    {
                        "content": hit.payload.get("content", ""),
                        "score": hit.score,
                        "id": hit.id,
                        "metadata": {
                            k: v for k, v in (hit.payload or {}).items() if k != "content"
                        },
                    }
                    for hit in results
                ]
            except (ConnectionError, OSError, UnexpectedResponse) as exc:
                logger.warning("Search attempt %d/%d failed: %s", attempt, _MAX_RETRIES, exc)
                if attempt == _MAX_RETRIES:
                    raise
                await asyncio.sleep(_RETRY_DELAY * attempt)

        return []  # unreachable, keeps type-checkers happy
