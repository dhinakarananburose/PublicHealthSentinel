"""Pydantic schemas for Phase 6A reference document ingestion and metadata retrieval."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

SYNTHETIC_DATA_NOTICE: str = (
    "SYNTHETIC-DATA NOTICE: All observations, indicators, and benchmark documents are part of a simulated "
    "research prototype. Documents represent reference material and guidelines for methodology testing."
)


class DocumentIngestRequest(BaseModel):
    """Payload for submitting a public health reference document for ingestion."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Filename with extension (.txt or .md).",
        examples=["cdc_syndromic_guidelines_2024.md"],
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Raw UTF-8 text or markdown content of the reference document.",
    )
    title: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional title. If omitted, extracted from content or filename.",
        examples=["CDC Syndromic Surveillance Guidelines"],
    )
    source_publisher: Optional[str] = Field(
        None,
        max_length=255,
        description="Authoring agency, publisher, or health department.",
        examples=["Centers for Disease Control and Prevention"],
    )
    source_url: Optional[str] = Field(
        None,
        max_length=1024,
        description="Source reference URL or DOI.",
        examples=["https://www.cdc.gov/surveillance/guidelines.html"],
    )
    publication_date: Optional[date] = Field(
        None,
        description="Original date of publication (YYYY-MM-DD).",
        examples=["2024-01-15"],
    )


class DocumentIngestResponse(BaseModel):
    """Response returned upon document ingestion attempt."""

    model_config = ConfigDict(extra="ignore")

    document_id: str = Field(..., description="Unique document tracking identifier.")
    status: str = Field(..., description="Ingestion outcome status ('INGESTED' or 'DUPLICATE').")
    filename: str = Field(..., description="Stored document filename.")
    doc_format: str = Field(..., description="Detected format ('txt' or 'md').")
    content_hash: str = Field(..., description="SHA-256 cryptographic digest of document content.")
    document_size_bytes: int = Field(..., description="Content size in bytes.")
    title: Optional[str] = Field(None, description="Extracted or user-supplied document title.")
    message: str = Field(..., description="Status description.")
    synthetic_experiment_notice: str = Field(
        default=SYNTHETIC_DATA_NOTICE,
        description="Standard notice identifying synthetic research benchmark context.",
    )


class DocumentMetadataResponse(BaseModel):
    """Detailed metadata and provenance representation of an ingested document."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(..., description="Internal database surrogate key.")
    document_id: str = Field(..., description="Public unique identifier.")
    filename: str = Field(..., description="Original filename.")
    title: Optional[str] = Field(None, description="Document title.")
    doc_format: str = Field(..., description="Format extension ('txt' or 'md').")
    content_hash: str = Field(..., description="SHA-256 content digest.")
    source_publisher: Optional[str] = Field(None, description="Authoring agency or publisher.")
    source_url: Optional[str] = Field(None, description="Source reference link.")
    publication_date: Optional[date] = Field(None, description="Publication date.")
    document_size_bytes: int = Field(..., description="Document size in bytes.")
    character_count: int = Field(..., description="Total character count.")
    word_count: int = Field(..., description="Estimated word count.")
    ingestion_status: str = Field(..., description="Ingestion status.")
    error_message: Optional[str] = Field(None, description="Failure reason if ingestion failed.")
    ingestion_timestamp: datetime = Field(..., description="Timestamp of document ingestion.")
    synthetic_experiment_notice: str = Field(
        default=SYNTHETIC_DATA_NOTICE,
        description="Standard notice identifying synthetic research benchmark context.",
    )


class ProcessDocumentResponse(BaseModel):
    """Result of processing an ingested document into passage chunks and embeddings."""

    model_config = ConfigDict(extra="ignore")

    document_id: str = Field(..., description="Target document identifier.")
    status: str = Field(..., description="Processing outcome ('INDEXED' or 'FAILED').")
    chunks_created: int = Field(..., description="Count of chunks extracted and indexed.")
    embedding_model: str = Field(..., description="Model identifier used to produce passage embeddings.")
    processing_duration_ms: float = Field(..., description="Wall clock duration of the processing run in ms.")
    message: str = Field(..., description="Descriptive status message.")
    synthetic_experiment_notice: str = Field(
        default=SYNTHETIC_DATA_NOTICE,
        description="Standard notice identifying synthetic research benchmark context.",
    )


class DocumentChunkResponse(BaseModel):
    """Detailed metadata and content for an extracted document chunk passage."""

    model_config = ConfigDict(extra="ignore")

    id: int = Field(..., description="Internal surrogate database key.")
    chunk_id: str = Field(..., description="Unique deterministic chunk identifier.")
    document_id: str = Field(..., description="Source document identifier.")
    sequence_number: int = Field(..., description="Zero-based sequence order in document.")
    text: str = Field(..., description="Passage text content.")
    char_start: int = Field(..., description="Starting character offset in normalized document.")
    char_end: int = Field(..., description="Ending character offset in normalized document.")
    title: Optional[str] = Field(None, description="Document title.")
    source_publisher: Optional[str] = Field(None, description="Authoring agency or publisher.")
    source_url: Optional[str] = Field(None, description="Source reference link.")
    publication_date: Optional[date] = Field(None, description="Original publication date.")
    content_hash: str = Field(..., description="Cryptographic SHA-256 hash of the passage text.")
    embedding_model: Optional[str] = Field(None, description="Embedding model used for this chunk.")
    created_at: datetime = Field(..., description="Timestamp of chunk creation.")


class EvidenceSearchRequest(BaseModel):
    """Natural-language semantic query payload for evidence passage retrieval."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question or search query.",
        examples=["What are the early syndromic surveillance thresholds for respiratory surges?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of relevant evidence passages to retrieve.",
    )
    document_id: Optional[str] = Field(
        None,
        max_length=64,
        description="Optional document ID to restrict search scope.",
    )
    source_publisher: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional agency or publisher filter.",
    )
    min_similarity: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Minimum cosine similarity cutoff (-1.0 to 1.0).",
    )


class RetrievedEvidenceItem(BaseModel):
    """Retrieved passage with provenance metadata and cosine similarity score."""

    model_config = ConfigDict(extra="ignore")

    chunk_id: str = Field(..., description="Passage chunk identifier.")
    document_id: str = Field(..., description="Source document identifier.")
    title: Optional[str] = Field(None, description="Source document title.")
    text: str = Field(..., description="Extracted passage text.")
    source_publisher: Optional[str] = Field(None, description="Source agency or publisher.")
    source_url: Optional[str] = Field(None, description="Source reference URL.")
    publication_date: Optional[date] = Field(None, description="Publication date.")
    sequence_number: int = Field(..., description="Chunk sequence number.")
    char_start: int = Field(..., description="Passage character start offset.")
    char_end: int = Field(..., description="Passage character end offset.")
    similarity_score: float = Field(..., description="Cosine similarity score between query and passage.")
    embedding_model: str = Field(..., description="Embedding model used for semantic comparison.")
    score_interpretation: str = Field(
        ...,
        description="Explanation of score meaning and non-clinical nature of vector similarity.",
    )


class EvidenceSearchResponse(BaseModel):
    """Response payload for evidence semantic query retrieval."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(..., description="Original submitted query.")
    query_id: str = Field(..., description="Unique query execution identifier.")
    total_results: int = Field(..., description="Count of retrieved matching passages.")
    embedding_model: str = Field(..., description="Embedding model active during retrieval.")
    items: list[RetrievedEvidenceItem] = Field(default_factory=list, description="Ranked evidence passages.")
    synthetic_experiment_notice: str = Field(
        default=SYNTHETIC_DATA_NOTICE,
        description="Standard notice identifying synthetic research benchmark context.",
    )


class EvidenceSubsystemStatusResponse(BaseModel):
    """Operational health and configuration status of the document processing subsystem."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="Subsystem status ('HEALTHY', 'EMPTY', 'DEGRADED').")
    total_indexed_chunks: int = Field(..., description="Total passage vectors currently in the active index.")
    total_indexed_documents: int = Field(..., description="Distinct count of documents indexed.")
    dimension: int = Field(..., description="Embedding vector dimensionality.")
    active_embedding_model: str = Field(..., description="Embedding model of the current active index.")
    configured_embedding_model: str = Field(..., description="Embedding model configured in settings.")
    index_file_exists: bool = Field(..., description="Whether evidence_vector_index.npz exists on disk.")
    meta_file_exists: bool = Field(..., description="Whether evidence_vector_index_meta.json exists on disk.")
    is_degraded: bool = Field(default=False, description="Flag indicating degraded or out-of-sync vector index.")
    degraded_reason: Optional[str] = Field(None, description="Diagnostic detail if subsystem is degraded.")
    last_updated: Optional[datetime] = Field(None, description="Timestamp of last index modification.")
    synthetic_experiment_notice: str = Field(
        default=SYNTHETIC_DATA_NOTICE,
        description="Standard notice identifying synthetic research benchmark context.",
    )


class EvidenceRebuildResponse(BaseModel):
    """Outcome payload for rebuilding the vector index from database records."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="Rebuild outcome status ('HEALTHY' or 'EMPTY').")
    rebuilt_chunks: int = Field(..., description="Total chunks indexed during rebuild.")
    active_embedding_model: str = Field(..., description="Embedding model used for index rebuild.")
    message: str = Field(..., description="Descriptive status message.")
    synthetic_experiment_notice: str = Field(
        default=SYNTHETIC_DATA_NOTICE,
        description="Standard notice identifying synthetic research benchmark context.",
    )

