"""Document processing and embedding pipeline for PublicHealthSentinel Phase 6B.1.

Coordinates document text extraction, passage chunking, local vector embedding,
relational persistence, and persistent vector index synchronization.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from public_health_sentinel.config import get_config
from public_health_sentinel.db.models import DocumentChunkModel, DocumentMetadataModel
from public_health_sentinel.documents.chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_TARGET_CHUNK_SIZE,
    DocumentChunk,
    split_text_into_chunks,
)
from public_health_sentinel.documents.embeddings import (
    EmbeddingService,
    get_embedding_service,
)
from public_health_sentinel.documents.index import (
    VectorIndexManager,
    get_vector_index,
)
from public_health_sentinel.documents.service import DocumentValidationError

logger = logging.getLogger("public_health_sentinel.documents.processor")


class DocumentProcessingError(Exception):
    """Base exception for document processing pipeline failures."""
    pass


class DocumentNotFoundError(DocumentProcessingError):
    """Raised when the requested document ID does not exist."""
    pass


@dataclass(frozen=True)
class ProcessingResult:
    """Outcome report for a document processing run."""

    document_id: str
    status: str  # "INDEXED" or "FAILED"
    chunks_created: int
    embedding_model: str
    processing_duration_ms: float
    error_message: Optional[str] = None


class DocumentProcessor:
    """Orchestrates end-to-end document chunking and semantic indexing."""

    def __init__(
        self,
        vector_index: Optional[VectorIndexManager] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self._index = vector_index or get_vector_index()
        self._embedding_service = embedding_service or get_embedding_service()

    def process_document(
        self,
        session: Session,
        document_id: str,
        target_chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> ProcessingResult:
        """Process an ingested document into chunks and vector embeddings.

        Args:
            session: Active SQLAlchemy database session.
            document_id: Unique public identifier of the ingested document.
            target_chunk_size: Optional chunk character size override.
            chunk_overlap: Optional chunk character overlap override.

        Returns:
            ProcessingResult with outcome and chunk counts.

        Raises:
            DocumentNotFoundError: If document_id does not exist.
            DocumentProcessingError: If chunking, embedding, or indexing fails.
        """
        start_time = time.perf_counter()
        config = get_config()

        # 1. Fetch document metadata
        stmt = select(DocumentMetadataModel).where(DocumentMetadataModel.document_id == document_id)
        doc = session.execute(stmt).scalar_one_or_none()
        if doc is None:
            raise DocumentNotFoundError(f"Document with ID '{document_id}' was not found.")

        # 2. Locate and read physical document file
        stored_path_rel = doc.stored_path
        if stored_path_rel:
            full_path = Path(stored_path_rel)
            if not full_path.is_absolute():
                full_path = Path.cwd() / stored_path_rel
        else:
            full_path = config.data_documents_dir / f"{doc.document_id}.{doc.doc_format}"

        if not full_path.exists():
            # Fallback to config directory
            fallback = config.data_documents_dir / f"{doc.document_id}.{doc.doc_format}"
            if fallback.exists():
                full_path = fallback
            else:
                err_msg = f"Document file missing from disk: {full_path}"
                logger.error(err_msg)
                raise DocumentProcessingError(err_msg)

        try:
            content_text = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            err_msg = f"Document encoding error reading {full_path}: {exc}"
            logger.error(err_msg)
            raise DocumentProcessingError(err_msg) from exc

        # 3. Chunk text
        chunk_size = target_chunk_size or config.chunk_target_size
        overlap = chunk_overlap or config.chunk_overlap

        try:
            chunks: list[DocumentChunk] = split_text_into_chunks(
                text=content_text,
                document_id=doc.document_id,
                title=doc.title,
                source_publisher=doc.source_publisher,
                source_url=doc.source_url,
                publication_date=doc.publication_date,
                doc_format=doc.doc_format,
                target_chunk_size=chunk_size,
                chunk_overlap=overlap,
            )
        except DocumentValidationError as exc:
            raise DocumentProcessingError(f"Validation failure during chunking: {exc}") from exc

        # 4. Generate local embeddings
        chunk_texts = [c.text for c in chunks]
        try:
            embedding_matrix = self._embedding_service.embed_batch(chunk_texts)
        except Exception as exc:
            raise DocumentProcessingError(f"Local embedding failed: {exc}") from exc

        model_name = self._embedding_service.model_name

        try:
            # 5. Idempotent persistence: remove existing chunks for this document
            del_stmt = delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
            session.execute(del_stmt)

            # 6. Insert new chunks with serialized vector embedding
            index_entries = []
            for chunk, vec in zip(chunks, embedding_matrix):
                vec_json = json.dumps(vec.tolist())
                model_row = DocumentChunkModel(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    sequence_number=chunk.sequence_number,
                    text=chunk.text,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    title=chunk.title,
                    source_publisher=chunk.source_publisher,
                    source_url=chunk.source_url,
                    publication_date=chunk.publication_date,
                    content_hash=chunk.content_hash,
                    embedding_json=vec_json,
                    embedding_model=model_name,
                )
                session.add(model_row)
                index_entries.append((chunk.chunk_id, chunk.document_id, vec))

            session.commit()

            # 7. Update vector index: remove prior chunks for doc and add new
            try:
                self._index.remove_by_document_id(document_id)
                self._index.add_chunks(index_entries, model_name=model_name)
            except Exception as idx_exc:
                logger.error(
                    "Vector index sync failed for %s after database commit: %s. Attempting index rebuild from database.",
                    document_id,
                    idx_exc,
                )
                try:
                    self._index.rebuild_from_db(session=session)
                except Exception as reb_exc:
                    logger.critical("Automatic index recovery rebuild failed: %s", reb_exc)
                raise DocumentProcessingError(
                    f"Vector index update failed, index was recovered: {idx_exc}"
                ) from idx_exc

        except Exception as exc:
            session.rollback()
            if not isinstance(exc, DocumentProcessingError):
                raise DocumentProcessingError(f"Persistence transaction failed for document '{document_id}': {exc}") from exc
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        logger.info(
            "Processed document %s into %d chunks in %.2f ms (model=%s)",
            document_id,
            len(chunks),
            duration_ms,
            model_name,
        )

        return ProcessingResult(
            document_id=document_id,
            status="INDEXED",
            chunks_created=len(chunks),
            embedding_model=model_name,
            processing_duration_ms=round(duration_ms, 2),
        )


_global_processor: Optional[DocumentProcessor] = None


def get_document_processor(force_new: bool = False) -> DocumentProcessor:
    """Retrieve or initialize singleton DocumentProcessor instance."""
    global _global_processor
    if _global_processor is None or force_new:
        _global_processor = DocumentProcessor()
    return _global_processor
