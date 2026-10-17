"""Reference document ingestion and metadata retrieval endpoints."""

from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from public_health_sentinel.api.models import PaginatedResponse
from public_health_sentinel.config import get_config
from public_health_sentinel.db.session import get_db_session
from public_health_sentinel.documents.schemas import (
    DocumentChunkResponse,
    DocumentIngestRequest,
    DocumentIngestResponse,
    DocumentMetadataResponse,
    ProcessDocumentResponse,
)
from public_health_sentinel.documents.service import (
    DocumentSizeLimitExceededError,
    DocumentValidationError,
    get_document_by_id,
    ingest_document,
    list_documents,
)

router = APIRouter(prefix="/documents", tags=["Reference Documents"])


@router.post(
    "/ingest",
    response_model=DocumentIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest and register a reference document",
    description=(
        "Registers a plain text (.txt) or Markdown (.md) public health reference document, "
        "computes cryptographic SHA-256 hash, extracts metadata, verifies size limits, "
        "and checks for duplicates."
    ),
    responses={
        201: {"description": "Document successfully ingested and registered."},
        400: {"description": "Invalid format, path traversal, or empty content."},
        409: {"description": "Duplicate document with identical content hash already exists."},
        413: {"description": "Document size exceeds maximum permitted limit."},
    },
)
def ingest_reference_document(
    request: DocumentIngestRequest,
    response: Response,
    session: Session = Depends(get_db_session),
) -> DocumentIngestResponse:
    """Ingest a reference document, extract metadata, and persist to storage."""
    if get_config().demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Document ingestion is disabled in public demonstration mode to protect benchmark data integrity.",
        )

    try:
        model, is_duplicate = ingest_document(
            session=session,
            filename=request.filename,
            content=request.content,
            title=request.title,
            source_publisher=request.source_publisher,
            source_url=request.source_url,
            publication_date=request.publication_date,
        )
    except DocumentSizeLimitExceededError as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        ) from exc
    except DocumentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if is_duplicate:
        response.status_code = status.HTTP_409_CONFLICT
        return DocumentIngestResponse(
            document_id=model.document_id,
            status="DUPLICATE",
            filename=model.filename,
            doc_format=model.doc_format,
            content_hash=model.content_hash,
            document_size_bytes=model.document_size_bytes,
            title=model.title,
            message="Document with identical content hash already ingested.",
        )

    return DocumentIngestResponse(
        document_id=model.document_id,
        status="INGESTED",
        filename=model.filename,
        doc_format=model.doc_format,
        content_hash=model.content_hash,
        document_size_bytes=model.document_size_bytes,
        title=model.title,
        message="Document successfully ingested and registered.",
    )


@router.get(
    "",
    response_model=PaginatedResponse[DocumentMetadataResponse],
    summary="List paginated reference document metadata",
    description="Query registered reference documents with optional filters by format, status, and publisher.",
)
def list_reference_documents(
    doc_format: Optional[str] = Query(None, description="Filter by format ('txt' or 'md')"),
    source_publisher: Optional[str] = Query(None, description="Filter by publisher/agency name"),
    ingestion_status: Optional[str] = Query(None, description="Filter by status ('INGESTED', 'DUPLICATE')"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page (max: 200)"),
    session: Session = Depends(get_db_session),
) -> PaginatedResponse[DocumentMetadataResponse]:
    """Retrieve paginated document metadata records matching query filters."""
    offset = (page - 1) * page_size
    records, total = list_documents(
        session=session,
        doc_format=doc_format,
        source_publisher=source_publisher,
        ingestion_status=ingestion_status,
        limit=page_size,
        offset=offset,
    )

    items = [
        DocumentMetadataResponse(
            id=r.id,
            document_id=r.document_id,
            filename=r.filename,
            title=r.title,
            doc_format=r.doc_format,
            content_hash=r.content_hash,
            source_publisher=r.source_publisher,
            source_url=r.source_url,
            publication_date=r.publication_date,
            document_size_bytes=r.document_size_bytes,
            character_count=r.character_count,
            word_count=r.word_count,
            ingestion_status=r.ingestion_status,
            error_message=r.error_message,
            ingestion_timestamp=r.ingestion_timestamp,
        )
        for r in records
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[DocumentMetadataResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentMetadataResponse,
    summary="Retrieve reference document metadata by ID",
    description="Fetch complete metadata and provenance registration for a single reference document.",
)
def get_reference_document(
    document_id: str,
    session: Session = Depends(get_db_session),
) -> DocumentMetadataResponse:
    """Fetch single document record by unique public document identifier."""
    doc = get_document_by_id(session=session, document_id=document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reference document with identifier '{document_id}' was not found.",
        )

    return DocumentMetadataResponse(
        id=doc.id,
        document_id=doc.document_id,
        filename=doc.filename,
        title=doc.title,
        doc_format=doc.doc_format,
        content_hash=doc.content_hash,
        source_publisher=doc.source_publisher,
        source_url=doc.source_url,
        publication_date=doc.publication_date,
        document_size_bytes=doc.document_size_bytes,
        character_count=doc.character_count,
        word_count=doc.word_count,
        ingestion_status=doc.ingestion_status,
        error_message=doc.error_message,
        ingestion_timestamp=doc.ingestion_timestamp,
    )


@router.post(
    "/{document_id}/process",
    response_model=ProcessDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Process an ingested document into chunks and vector embeddings",
    description=(
        "Splits a registered reference document into structure-aware passage chunks, "
        "computes dense embeddings using the local embedding model, updates database records, "
        "and indexes passage vectors for semantic retrieval."
    ),
    responses={
        200: {"description": "Document successfully chunked, embedded, and indexed."},
        400: {"description": "Processing or validation error."},
        404: {"description": "Target document not found."},
    },
)
def process_document_endpoint(
    document_id: str,
    session: Session = Depends(get_db_session),
) -> ProcessDocumentResponse:
    """Process an existing document into chunks and vector embeddings."""
    if get_config().demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Document chunk processing is disabled in public demonstration mode to protect benchmark data integrity.",
        )

    from public_health_sentinel.documents.processor import (
        DocumentNotFoundError,
        DocumentProcessingError,
        get_document_processor,
    )

    processor = get_document_processor()
    try:
        res = processor.process_document(session=session, document_id=document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return ProcessDocumentResponse(
        document_id=res.document_id,
        status=res.status,
        chunks_created=res.chunks_created,
        embedding_model=res.embedding_model,
        processing_duration_ms=res.processing_duration_ms,
        message=f"Document successfully processed into {res.chunks_created} passages and indexed.",
    )


@router.get(
    "/{document_id}/chunks",
    response_model=PaginatedResponse[DocumentChunkResponse],
    summary="List extracted chunks for a document",
    description="Retrieve paginated passage chunks extracted from the specified reference document.",
    responses={
        200: {"description": "Document chunks retrieved."},
        404: {"description": "Target document not found."},
    },
)
def get_document_chunks_endpoint(
    document_id: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page (max: 200)"),
    session: Session = Depends(get_db_session),
) -> PaginatedResponse[DocumentChunkResponse]:
    """Retrieve ordered passage chunks belonging to the specified document."""
    from sqlalchemy import func, select
    from public_health_sentinel.db.models import DocumentChunkModel

    doc = get_document_by_id(session=session, document_id=document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reference document with identifier '{document_id}' was not found.",
        )

    base_query = select(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total = session.execute(count_stmt).scalar() or 0

    offset = (page - 1) * page_size
    paged_stmt = (
        base_query.order_by(DocumentChunkModel.sequence_number.asc())
        .limit(page_size)
        .offset(offset)
    )
    records = list(session.execute(paged_stmt).scalars().all())

    items = [
        DocumentChunkResponse(
            id=r.id,
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            sequence_number=r.sequence_number,
            text=r.text,
            char_start=r.char_start,
            char_end=r.char_end,
            title=r.title,
            source_publisher=r.source_publisher,
            source_url=r.source_url,
            publication_date=r.publication_date,
            content_hash=r.content_hash,
            embedding_model=r.embedding_model,
            created_at=r.created_at,
        )
        for r in records
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[DocumentChunkResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )

