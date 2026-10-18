"""Semantic retrieval service for PublicHealthSentinel Phase 6B.1.

Coordinates natural-language query embedding, vector index similarity search,
and database metadata lookup to return ranked, source-attributed evidence passages.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session
import numpy as np

from public_health_sentinel.config import get_config
from public_health_sentinel.db.models import DocumentChunkModel
from public_health_sentinel.documents.embeddings import (
    EmbeddingService,
    get_embedding_service,
)
from public_health_sentinel.documents.index import (
    IncompatibleIndexModelError,
    VectorIndexError,
    VectorIndexManager,
    get_vector_index,
)

logger = logging.getLogger("public_health_sentinel.documents.retrieval")

SIMILARITY_INTERPRETATION_NOTICE = (
    "Similarity scores represent geometric cosine similarity (range: -1.0 to 1.0) "
    "between query and passage embeddings. A high similarity score indicates semantic "
    "alignment of phrasing, NOT clinical truth, empirical outbreak confirmation, or medical consensus."
)


class RetrievalValidationError(ValueError):
    """Raised when query or search parameters violate constraints."""
    pass


@dataclass(frozen=True)
class RetrievedEvidenceChunk:
    """Ranked evidence passage with provenance and similarity attribution."""

    chunk_id: str
    document_id: str
    title: Optional[str]
    text: str
    source_publisher: Optional[str]
    source_url: Optional[str]
    publication_date: Optional[date]
    sequence_number: int
    char_start: int
    char_end: int
    similarity_score: float
    embedding_model: str
    score_interpretation: str = SIMILARITY_INTERPRETATION_NOTICE

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "title": self.title,
            "text": self.text,
            "source_publisher": self.source_publisher,
            "source_url": self.source_url,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "sequence_number": self.sequence_number,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "similarity_score": round(self.similarity_score, 4),
            "embedding_model": self.embedding_model,
            "score_interpretation": self.score_interpretation,
        }


@dataclass(frozen=True)
class EvidenceSearchResult:
    """Container for search response payload."""

    query: str
    query_id: str
    total_results: int
    embedding_model: str
    items: list[RetrievedEvidenceChunk]
    synthetic_experiment_notice: str


class SemanticRetrievalService:
    """Service executing semantic vector search and relational passage retrieval."""

    def __init__(
        self,
        vector_index: Optional[VectorIndexManager] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self._embedding_service = embedding_service or get_embedding_service()
        self._index = vector_index or get_vector_index(embedding_service=self._embedding_service)

    @property
    def vector_index(self) -> VectorIndexManager:
        return self._index

    @property
    def embedding_service(self) -> EmbeddingService:
        return self._embedding_service

    def search(
        self,
        session: Session,
        query: str,
        top_k: int = 5,
        document_id: Optional[str] = None,
        source_publisher: Optional[str] = None,
        min_similarity: float = 0.0,
    ) -> EvidenceSearchResult:
        """Search evidence passages matching a natural language query.

        Args:
            session: Active database session for metadata hydration.
            query: Natural language search string.
            top_k: Maximum candidate passages (1 to 50).
            document_id: Optional filter limiting search to a specific document.
            source_publisher: Optional filter limiting search to a specific agency.
            min_similarity: Floor for cosine similarity score (default: 0.0).

        Returns:
            EvidenceSearchResult with ranked passage items.

        Raises:
            RetrievalValidationError: If query or parameters are invalid.
        """
        if not query or not query.strip():
            raise RetrievalValidationError("Search query cannot be empty or whitespace-only.")

        cleaned_query = query.strip()
        if len(cleaned_query) > 2000:
            raise RetrievalValidationError(
                f"Query length ({len(cleaned_query)}) exceeds maximum limit of 2000 characters."
            )

        if top_k < 1 or top_k > 50:
            raise RetrievalValidationError(f"top_k must be between 1 and 50, got {top_k}")

        if min_similarity < -1.0 or min_similarity > 1.0:
            raise RetrievalValidationError(
                f"min_similarity must be between -1.0 and 1.0, got {min_similarity}"
            )

        query_id = f"qry-{uuid.uuid4().hex[:10]}"

        # Handle missing, empty, or degraded index files by rebuilding safely from existing DB chunks
        if self._index.total_vectors == 0 or self._index.is_degraded:
            chunk_count_stmt = select(func.count(DocumentChunkModel.chunk_id))
            db_chunk_count = session.execute(chunk_count_stmt).scalar() or 0
            if db_chunk_count > 0:
                logger.info(
                    "Vector index requires rebuild (index_vectors=%d, degraded=%s, db_chunks=%d). "
                    "Rebuilding vector index from relational passage records...",
                    self._index.total_vectors,
                    self._index.is_degraded,
                    db_chunk_count,
                )
                self._index.rebuild_from_db(session=session, embedding_service=self._embedding_service)






        # If index remains empty because database contains no chunks, return early
        if self._index.total_vectors == 0:
            return EvidenceSearchResult(
                query=cleaned_query,
                query_id=query_id,
                total_results=0,
                embedding_model=self._embedding_service.model_name,
                items=[],
                synthetic_experiment_notice=(
                    "SYNTHETIC-DATA NOTICE: All observations, indicators, and benchmark documents are part "
                    "of a simulated research prototype. Index currently contains 0 passages."
                ),
            )

        # Verify embedding model compatibility when index is populated
        if self._index.active_model_name != self._embedding_service.model_name:
            raise IncompatibleIndexModelError(
                f"Active vector index model '{self._index.active_model_name}' is incompatible with "
                f"current query embedding model '{self._embedding_service.model_name}'. "
                "Rebuild the vector index from the database to restore retrieval alignment."
            )

        # Generate query embedding
        query_vector = self._embedding_service.embed_text(cleaned_query)

        # Pre-filter candidate chunks if publisher filter is requested
        candidate_chunk_ids: Optional[set[str]] = None
        if source_publisher is not None and source_publisher.strip():
            stmt = select(DocumentChunkModel.chunk_id).where(
                DocumentChunkModel.source_publisher == source_publisher.strip()
            )
            candidate_chunk_ids = set(session.execute(stmt).scalars().all())
            if not candidate_chunk_ids:
                return EvidenceSearchResult(
                    query=cleaned_query,
                    query_id=query_id,
                    total_results=0,
                    embedding_model=self._embedding_service.model_name,
                    items=[],
                    synthetic_experiment_notice=(
                        "SYNTHETIC-DATA NOTICE: No indexed documents match the specified publisher filter."
                    ),
                )

        ranked_hits = self._index.search(
            query_vector=query_vector,
            top_k=top_k,
            document_id=document_id.strip() if document_id else None,
            candidate_chunk_ids=candidate_chunk_ids,
            min_similarity=min_similarity,
        )


        if not ranked_hits:
            return EvidenceSearchResult(
                query=cleaned_query,
                query_id=query_id,
                total_results=0,
                embedding_model=self._embedding_service.model_name,
                items=[],
                synthetic_experiment_notice=(
                    "SYNTHETIC-DATA NOTICE: Reference documents were evaluated; no passage met the similarity threshold."
                ),
            )

        # Hydrate candidate chunk metadata from database with provenance integrity verification
        chunk_ids = [hit[0] for hit in ranked_hits]
        score_map = {hit[0]: hit[1] for hit in ranked_hits}

        chunks_stmt = select(DocumentChunkModel).where(DocumentChunkModel.chunk_id.in_(chunk_ids))
        chunk_models = list(session.execute(chunks_stmt).scalars().all())
        model_map = {cm.chunk_id: cm for cm in chunk_models}

        items: list[RetrievedEvidenceChunk] = []
        for cid in chunk_ids:
            if cid not in model_map:
                logger.warning(
                    "Chunk '%s' present in vector index is missing from relational database. Skipping orphaned vector.",
                    cid,
                )
                continue

            cm = model_map[cid]

            # Additional verification: ensure document_id matches if filter was specified
            if document_id and cm.document_id != document_id.strip():
                continue

            # Additional verification: ensure publisher matches if filter was specified
            if source_publisher and cm.source_publisher != source_publisher.strip():
                continue

            # Ensure chunk text is valid and not empty
            if not cm.text or not cm.text.strip():
                logger.warning("Chunk '%s' has empty content in database. Skipping.", cid)
                continue

            score = score_map.get(cid, 0.0)
            items.append(
                RetrievedEvidenceChunk(
                    chunk_id=cm.chunk_id,
                    document_id=cm.document_id,
                    title=cm.title,
                    text=cm.text,
                    source_publisher=cm.source_publisher,
                    source_url=cm.source_url,
                    publication_date=cm.publication_date,
                    sequence_number=cm.sequence_number,
                    char_start=cm.char_start,
                    char_end=cm.char_end,
                    similarity_score=score,
                    embedding_model=self._embedding_service.model_name,
                )
            )

        return EvidenceSearchResult(
            query=cleaned_query,
            query_id=query_id,
            total_results=len(items),
            embedding_model=self._embedding_service.model_name,
            items=items,
            synthetic_experiment_notice=(
                "SYNTHETIC-DATA NOTICE: Evidence passages retrieved from indexed reference material. "
                "Similarity scores indicate text proximity and do not establish clinical diagnosis or real-world validity."
            ),
        )

    def _search_db_fallback(
        self,
        session: Session,
        cleaned_query: str,
        query_id: str,
        top_k: int,
        min_similarity: float,
        document_id: Optional[str] = None,
        source_publisher: Optional[str] = None,
    ) -> EvidenceSearchResult:
        """Lightweight database passage matching for public demo mode or degraded index fallback."""
        stmt = select(DocumentChunkModel)
        if document_id and document_id.strip():
            stmt = stmt.where(DocumentChunkModel.document_id == document_id.strip())
        if source_publisher and source_publisher.strip():
            stmt = stmt.where(DocumentChunkModel.source_publisher == source_publisher.strip())

        all_chunks = list(session.execute(stmt).scalars().all())
        if not all_chunks:
            return EvidenceSearchResult(
                query=cleaned_query,
                query_id=query_id,
                total_results=0,
                embedding_model=self._embedding_service.model_name,
                items=[],
                synthetic_experiment_notice=(
                    "SYNTHETIC-DATA NOTICE: Reference documents were evaluated; no passages found in database."
                ),
            )

        query_vec = self._embedding_service.embed_text(cleaned_query)

        scored: list[tuple[float, DocumentChunkModel]] = []
        for cm in all_chunks:
            if not cm.text:
                continue
            chunk_vec = self._embedding_service.embed_text(cm.text)
            sim = float(np.dot(query_vec, chunk_vec))
            if sim >= min_similarity:
                scored.append((sim, cm))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_items = scored[:top_k]

        items = [
            RetrievedEvidenceChunk(
                chunk_id=cm.chunk_id,
                document_id=cm.document_id,
                title=cm.title,
                text=cm.text,
                source_publisher=cm.source_publisher,
                source_url=cm.source_url,
                publication_date=cm.publication_date,
                sequence_number=cm.sequence_number,
                char_start=cm.char_start,
                char_end=cm.char_end,
                similarity_score=score,
                embedding_model=self._embedding_service.model_name,
            )
            for score, cm in top_items
        ]

        return EvidenceSearchResult(
            query=cleaned_query,
            query_id=query_id,
            total_results=len(items),
            embedding_model=self._embedding_service.model_name,
            items=items,
            synthetic_experiment_notice=(
                "SYNTHETIC-DATA NOTICE: All observations, indicators, and benchmark documents are part "
                "of a simulated research prototype."
            ),
        )

