"""Semantic evidence passage retrieval and subsystem status endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from public_health_sentinel.config import get_config
from public_health_sentinel.db.models import DocumentChunkModel
from public_health_sentinel.db.session import get_db_session
from public_health_sentinel.documents.embeddings import get_embedding_service
from public_health_sentinel.documents.index import (
    IncompatibleIndexModelError,
    VectorIndexError,
    get_vector_index,
)
from public_health_sentinel.documents.retrieval import (
    RetrievalValidationError,
    SemanticRetrievalService,
)
from public_health_sentinel.documents.schemas import (
    EvidenceRebuildResponse,
    EvidenceSearchRequest,
    EvidenceSearchResponse,
    EvidenceSubsystemStatusResponse,
    RetrievedEvidenceItem,
)

logger = logging.getLogger("public_health_sentinel.api.v1.routers.evidence")

router = APIRouter(prefix="/evidence", tags=["Evidence Retrieval"])


@router.post(
    "/search",
    response_model=EvidenceSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic retrieval of relevant evidence passages",
    description=(
        "Executes vector similarity search against indexed public health reference documents "
        "using the local embedding model. Returns ranked passages with provenance metadata, "
        "character offsets, and cosine similarity scores."
    ),
    responses={
        200: {"description": "Evidence search completed successfully."},
        400: {"description": "Invalid query or search parameters."},
    },
)
def search_evidence_endpoint(
    request: EvidenceSearchRequest,
    session: Session = Depends(get_db_session),
) -> EvidenceSearchResponse:
    """Execute natural-language semantic evidence retrieval."""
    service = SemanticRetrievalService()

    try:
        search_res = service.search(
            session=session,
            query=request.query,
            top_k=request.top_k,
            document_id=request.document_id,
            source_publisher=request.source_publisher,
            min_similarity=request.min_similarity,
        )
    except RetrievalValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except IncompatibleIndexModelError as exc:
        logger.warning("Evidence search rejected due to incompatible model: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except VectorIndexError as exc:
        logger.warning("Evidence search vector index error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Evidence retrieval failure: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute semantic retrieval. Check embedding model and index status.",
        ) from exc

    items = [
        RetrievedEvidenceItem(
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            title=item.title,
            text=item.text,
            source_publisher=item.source_publisher,
            source_url=item.source_url,
            publication_date=item.publication_date,
            sequence_number=item.sequence_number,
            char_start=item.char_start,
            char_end=item.char_end,
            similarity_score=item.similarity_score,
            embedding_model=item.embedding_model,
            score_interpretation=item.score_interpretation,
        )
        for item in search_res.items
    ]

    return EvidenceSearchResponse(
        query=search_res.query,
        query_id=search_res.query_id,
        total_results=search_res.total_results,
        embedding_model=search_res.embedding_model,
        items=items,
        synthetic_experiment_notice=search_res.synthetic_experiment_notice,
    )


@router.get(
    "/status",
    response_model=EvidenceSubsystemStatusResponse,
    summary="Evidence subsystem operational status",
    description="Inspect vector index state, embedding model configuration, degradation status, and indexed passage counts.",
)
def get_evidence_status_endpoint(
    session: Session = Depends(get_db_session),
) -> EvidenceSubsystemStatusResponse:
    """Report vector indexing and retrieval subsystem health."""
    index = get_vector_index()
    index_status = index.status()

    # Query distinct document count in database
    doc_count_stmt = select(func.count(func.distinct(DocumentChunkModel.document_id)))
    distinct_docs = session.execute(doc_count_stmt).scalar() or 0

    total_vectors = index_status["total_vectors"]
    is_degraded = bool(index_status.get("is_degraded"))
    degraded_reason = index_status.get("degraded_reason")

    if is_degraded:
        overall_status = "DEGRADED"
    elif total_vectors > 0:
        overall_status = "HEALTHY"
    else:
        overall_status = "EMPTY"

    last_updated_val = None
    if index_status["last_updated"]:
        from datetime import datetime
        try:
            last_updated_val = datetime.fromisoformat(index_status["last_updated"])
        except ValueError:
            pass

    return EvidenceSubsystemStatusResponse(
        status=overall_status,
        total_indexed_chunks=total_vectors,
        total_indexed_documents=distinct_docs,
        dimension=index_status["dimension"],
        active_embedding_model=index_status["active_model_name"],
        configured_embedding_model=index_status["configured_model_name"],
        index_file_exists=index_status["index_file_exists"],
        meta_file_exists=index_status["meta_file_exists"],
        is_degraded=is_degraded,
        degraded_reason=degraded_reason,
        last_updated=last_updated_val,
    )


@router.post(
    "/rebuild",
    response_model=EvidenceRebuildResponse,
    status_code=status.HTTP_200_OK,
    summary="Rebuild vector index from relational passage records",
    description="Reconstructs persistent vector index and metadata entirely from database chunk records.",
    responses={
        200: {"description": "Vector index successfully rebuilt."},
        500: {"description": "Index rebuild failed."},
    },
)
def rebuild_evidence_index_endpoint(
    session: Session = Depends(get_db_session),
) -> EvidenceRebuildResponse:
    """Reconstruct vector index from database DocumentChunkModel entries."""
    if get_config().demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vector index rebuilding is disabled in public demonstration mode to protect benchmark data integrity.",
        )

    index = get_vector_index()
    emb_svc = get_embedding_service()

    try:
        rebuilt_count = index.rebuild_from_db(session=session, embedding_service=emb_svc)
    except Exception as exc:
        logger.error("Failed to rebuild vector index: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rebuild vector index: {exc}",
        ) from exc

    overall_status = "HEALTHY" if rebuilt_count > 0 else "EMPTY"
    return EvidenceRebuildResponse(
        status=overall_status,
        rebuilt_chunks=rebuilt_count,
        active_embedding_model=index.active_model_name,
        message=f"Vector index successfully rebuilt from database with {rebuilt_count} passages.",
    )
