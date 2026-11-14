"""Redis-backed semantic caching layer for LLM responses."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis

from src.config import get_settings

logger = logging.getLogger(__name__)

# Default TTL for cached entries (1 hour)
_DEFAULT_TTL: int = 3600


class LLMCache:
    """Simple prompt-hash → response cache backed by Redis."""

    def __init__(self, ttl: int = _DEFAULT_TTL) -> None:
        settings = get_settings()
        self._redis: aioredis.Redis = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
        self._ttl = ttl

        # Metrics counters
        self._hits: int = 0
        self._misses: int = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_prompt(prompt: str, system_prompt: str = "") -> str:
        """Create a deterministic cache key from prompt content."""
        blob = json.dumps(
            {"system_prompt": system_prompt, "prompt": prompt}, sort_keys=True
        )
        return f"llm_cache:{hashlib.sha256(blob.encode()).hexdigest()}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(self, prompt: str, system_prompt: str = "") -> str | None:
        """Return cached response or *None* on a miss."""
        key = self._hash_prompt(prompt, system_prompt)
        value = await self._redis.get(key)
        if value is not None:
            self._hits += 1
            logger.debug("Cache HIT for key %s", key)
            return value
        self._misses += 1
        logger.debug("Cache MISS for key %s", key)
        return None

    async def set(
        self,
        prompt: str,
        response: str,
        system_prompt: str = "",
        ttl: int | None = None,
    ) -> None:
        """Store a response in the cache."""
        key = self._hash_prompt(prompt, system_prompt)
        await self._redis.setex(key, ttl or self._ttl, response)

    def metrics(self) -> dict[str, Any]:
        """Return cache hit/miss statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total else 0.0,
            "total_requests": total,
            "timestamp": time.time(),
        }

    async def close(self) -> None:
        """Shut down the Redis connection."""
        await self._redis.aclose()
