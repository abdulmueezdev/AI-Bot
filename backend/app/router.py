"""FastAPI router — API endpoints for the Digital Clone system.

Endpoints:
  POST /chat/{clone_id}   — Main chat interaction
  POST /ingest/{clone_id} — Trigger data ingestion for a clone
  GET  /health            — Health check
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.ingest import ingest_clone_data
from app.llm_client import LLMUnavailableError
from app.orchestrator import handle_chat
from app.safety import validate_clone_id
from app.vector_store import get_collection_count

logger = structlog.get_logger(__name__)

router = APIRouter()


# ── Request / Response Models ──────────────────────────────────────────


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's message to the clone.",
        examples=["What is Kafka's view on hope?"],
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session ID for conversation continuity.",
    )


class ChatResponse(BaseModel):
    """Response body from the chat endpoint."""

    response: str = Field(description="The clone's response.")
    clone_id: str = Field(description="The clone that responded.")
    session_id: str = Field(description="Session ID for this conversation.")
    model_used: str = Field(description="LLM model used for generation.")
    context_chunks_used: int = Field(description="Number of RAG chunks used.")
    latency_ms: float = Field(description="Total pipeline latency in ms.")


class IngestRequest(BaseModel):
    """Optional request body for ingestion."""

    force: bool = Field(
        default=False,
        description="If true, delete existing data and re-ingest from scratch.",
    )


class IngestResponse(BaseModel):
    """Response body from the ingest endpoint."""

    clone_id: str
    files_processed: int
    chunks_created: int
    errors: list[str] = Field(default_factory=list)
    elapsed_ms: float


class HealthResponse(BaseModel):
    """Response body for the health check."""

    status: str
    version: str
    clones: dict[str, int] = Field(
        description="Map of clone_id to document count."
    )


# ── Endpoints ──────────────────────────────────────────────────────────


@router.post(
    "/chat/{clone_id}",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with a digital clone",
    description="Send a message to a specific clone and receive a response in character.",
)
async def chat_endpoint(clone_id: str, request: ChatRequest) -> ChatResponse:
    """Main chat endpoint — full RAG pipeline."""
    session_id = request.session_id or uuid.uuid4().hex[:12]

    log = logger.bind(clone_id=clone_id, session_id=session_id)
    log.info("chat_request_received", message_length=len(request.message))

    try:
        result = await handle_chat(
            clone_id=clone_id,
            message=request.message,
            session_id=session_id,
        )

        return ChatResponse(
            response=result.response,
            clone_id=result.clone_id,
            session_id=result.session_id,
            model_used=result.model_used,
            context_chunks_used=result.context_chunks_used,
            latency_ms=result.latency_ms,
        )

    except LLMUnavailableError:
        log.error("llm_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="All language model providers are currently unavailable. Please try again later.",
        )
    except HTTPException:
        raise  # Re-raise HTTP exceptions (e.g., 404 from validate_clone_id)
    except Exception as exc:
        log.error("chat_unexpected_error", error=str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. The machinery has failed.",
        )


@router.post(
    "/ingest/{clone_id}",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest clone knowledge base",
    description="Trigger document ingestion for a specific clone's data directory.",
)
async def ingest_endpoint(
    clone_id: str, request: IngestRequest | None = None
) -> IngestResponse:
    """Trigger ingestion of a clone's knowledge base."""
    validate_clone_id(clone_id)
    force = request.force if request else False

    log = logger.bind(clone_id=clone_id)
    log.info("ingest_request_received", force=force)

    try:
        stats = await ingest_clone_data(clone_id, force=force)

        if stats.errors and stats.chunks_created == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ingestion failed: {'; '.join(stats.errors)}",
            )

        return IngestResponse(
            clone_id=stats.clone_id,
            files_processed=stats.files_processed,
            chunks_created=stats.chunks_created,
            errors=stats.errors,
            elapsed_ms=round(stats.elapsed_ms, 1),
        )

    except HTTPException:
        raise
    except Exception as exc:
        log.error("ingest_unexpected_error", error=str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed unexpectedly: {exc}",
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
)
async def health_endpoint() -> HealthResponse:
    """Health check with clone collection counts."""
    settings = get_settings()
    clones: dict[str, int] = {}

    for clone_id in settings.valid_clone_ids:
        count = await get_collection_count(clone_id)
        clones[clone_id] = count

    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        clones=clones,
    )
