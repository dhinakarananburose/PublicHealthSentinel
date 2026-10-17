"""FastAPI router for Phase 6C Evidence-Grounded AI Assistant."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from public_health_sentinel.db.session import get_db_session
from public_health_sentinel.documents.index import get_vector_index
from public_health_sentinel.documents.retrieval import RetrievalValidationError
from public_health_sentinel.assistant.provider import (
    AssistantProviderError,
    ModelNotFoundError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    get_generation_provider,
)
from public_health_sentinel.assistant.schemas import (
    AssistantAskRequest,
    AssistantAskResponse,
    AssistantStatusResponse,
)
from public_health_sentinel.assistant.service import (
    EvidenceGroundedAssistant,
    get_assistant,
)

logger = logging.getLogger("public_health_sentinel.api.v1.routers.assistant")

router = APIRouter(prefix="/assistant", tags=["Evidence-Grounded Assistant"])


@router.post(
    "/ask",
    response_model=AssistantAskResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask an inquiry grounded in indexed public health evidence",
    description=(
        "Retrieves relevant reference passages, constructs an isolated context, generates a "
        "synthesized answer through the configured generation provider (Ollama or Mock), "
        "and strictly verifies all cited passage identifiers."
    ),
    responses={
        200: {"description": "Grounded answer generated successfully."},
        400: {"description": "Invalid inquiry or search parameters."},
        503: {"description": "Local generation provider (Ollama) unavailable or model missing."},
        504: {"description": "Answer generation timed out."},
    },
)
def ask_assistant_endpoint(
    request: AssistantAskRequest,
    session: Session = Depends(get_db_session),
) -> AssistantAskResponse:
    """Execute evidence-grounded research synthesis."""
    assistant = get_assistant()

    try:
        return assistant.ask(session=session, request=request)
    except RetrievalValidationError as exc:
        logger.warning("Assistant request validation failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except (ProviderUnavailableError, ModelNotFoundError) as exc:
        logger.error("Generation provider unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ProviderTimeoutError as exc:
        logger.error("Generation provider timed out: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except AssistantProviderError as exc:
        logger.error("Generation provider error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during assistant execution: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during assistant evidence synthesis.",
        ) from exc


@router.get(
    "/status",
    response_model=AssistantStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get assistant readiness and provider health",
    description="Returns telemetry on local Ollama/mock provider availability, active models, and vector index status.",
)
def assistant_status_endpoint(
    session: Session = Depends(get_db_session),
) -> AssistantStatusResponse:
    """Retrieve operational readiness status for the assistant subsystem."""
    from public_health_sentinel.config import get_config
    from public_health_sentinel.db.models import DocumentChunkModel

    cfg = get_config()
    provider = get_generation_provider()
    health = provider.check_health()
    index_mgr = get_vector_index()

    total_passages = index_mgr.total_vectors
    if total_passages == 0 and cfg.demo_mode:
        try:
            total_passages = session.query(DocumentChunkModel).count()
        except Exception:
            total_passages = 0

    idx_status = "HEALTHY" if not index_mgr.is_degraded else "DEGRADED"
    if total_passages == 0:
        idx_status = "EMPTY"

    if index_mgr.is_degraded and not cfg.demo_mode:
        overall_status = "INDEX_DEGRADED"
    elif not health.is_healthy:
        overall_status = "PROVIDER_UNAVAILABLE"
    else:
        overall_status = "READY"

    return AssistantStatusResponse(
        status=overall_status,  # type: ignore[arg-type]
        provider=provider.provider_name,
        model=provider.model_name,
        provider_healthy=health.is_healthy,
        provider_message=health.message,
        vector_index_status=idx_status,
        indexed_passages_count=total_passages,
        available_models=health.available_models,
    )
