"""FastAPI application — entry point for the Digital Clone AI Chatbot.

Configures: structured logging, CORS, lifespan events, router.
Run with: uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.router import router


def _configure_logging() -> None:
    """Configure structlog for structured JSON logging.

    Every log entry includes timestamp, level, logger name.
    Application code adds clone_id and session_id via bind().
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if get_settings().environment == "development"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(get_settings().log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown events."""
    _configure_logging()
    log = structlog.get_logger("lifespan")

    settings = get_settings()
    log.info(
        "app_starting",
        environment=settings.environment,
        version=settings.app_version,
        valid_clones=sorted(settings.valid_clone_ids),
        chroma_dir=str(settings.chroma_path),
    )

    yield  # Application runs here

    log.info("app_shutting_down")


# ── FastAPI App ────────────────────────────────────────────────────────

app = FastAPI(
    title="Digital Clone AI Chatbot",
    description=(
        "Multi-tenant AI chatbot backend that hosts digital clones of real individuals. "
        "Each clone has its own persona, knowledge base, and memory."
    ),
    version=get_settings().app_version,
    lifespan=lifespan,
)

# CORS — permissive for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router
app.include_router(router)
