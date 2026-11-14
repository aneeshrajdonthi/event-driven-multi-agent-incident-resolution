"""FastAPI application — lifespan, middleware, and app factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise shared resources on startup and tear them down on shutdown."""
    settings = get_settings()

    # Configure logging
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Redis
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    logger.info("Redis connected at %s", settings.REDIS_URL)

    # Qdrant (sync client — used inside retrieval module lazily)
    logger.info("Qdrant configured at %s:%s", settings.QDRANT_HOST, settings.QDRANT_PORT)

    # Kafka consumer (lazy — import here to validate config early)
    try:
        from confluent_kafka import Consumer  # noqa: F401

        logger.info("Kafka consumer library available (bootstrap=%s)", settings.KAFKA_BOOTSTRAP_SERVERS)
    except ImportError:
        logger.warning("confluent-kafka not installed — Kafka features disabled")

    yield

    # Teardown
    await app.state.redis.aclose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title="Incident Resolution API",
        description="Event-driven multi-agent incident resolution system",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from src.api.routes import router

    app.include_router(router)

    return app


app = create_app()
