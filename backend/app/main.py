"""FastAPI application — entry point for the Digital Clone AI Chatbot.

Configures: structured logging, CORS, lifespan events, router,
APScheduler for calendar background refresh.
Run with: uvicorn app.main:app --reload
"""

from __future__ import annotations

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.router import router
from app.routers.calendar import router as calendar_router
from app.routers.session import router as session_router


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


def _start_calendar_scheduler() -> None:
    """Start the APScheduler background job for calendar refresh.

    Refreshes calendar cache for all active personas every 15 minutes.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from app.calendar_sync import get_calendar_sync

        scheduler = BackgroundScheduler()
        sync = get_calendar_sync()
        settings = get_settings()

        def refresh_all_calendars() -> None:
            """Refresh calendar cache for all valid clones."""
            import asyncio

            for clone_id in settings.valid_clone_ids:
                try:
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(sync.refresh(clone_id))
                    loop.close()
                except Exception as exc:
                    log = structlog.get_logger("scheduler")
                    log.error(
                        "calendar_refresh_job_failed",
                        clone_id=clone_id,
                        error=str(exc),
                    )

        scheduler.add_job(
            refresh_all_calendars,
            "interval",
            minutes=15,
            id="calendar_refresh",
            replace_existing=True,
        )
        scheduler.start()

        log = structlog.get_logger("scheduler")
        log.info("calendar_scheduler_started", interval_minutes=15)

    except ImportError:
        log = structlog.get_logger("scheduler")
        log.warning("apscheduler_not_installed_calendar_refresh_disabled")
    except Exception as exc:
        log = structlog.get_logger("scheduler")
        log.error("scheduler_start_failed", error=str(exc))


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

    # Start calendar background refresh
    _start_calendar_scheduler()

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

# CORS — specific allowed origins for production frontend
allowed_origins = [
    "http://localhost:3000",           # local dev
    "http://localhost:3001",           # alternate local dev
    "https://ai-bot-psi-three.vercel.app",  # Production Vercel URL
    "https://ai-6cje4v351-abdulmueezs-projects-99b2e67f.vercel.app",
    os.getenv("FRONTEND_URL", ""),     # Vercel URL via env var
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Vercel preview URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)
app.include_router(calendar_router)
app.include_router(session_router)
