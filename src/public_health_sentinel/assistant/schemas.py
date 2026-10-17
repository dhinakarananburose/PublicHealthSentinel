"""Pydantic schemas for Phase 6C Evidence-Grounded AI Assistant."""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class CitationItem(BaseModel):
    """Verifiable citation linking an answer claim to an indexed evidence passage."""

    model_config = ConfigDict(frozen=True)

    citation_id: str = Field(
        ...,
        description="Citation identifier used in inline answer text (e.g. 'E1').",
        examples=["E1"],
    )
    chunk_id: str = Field(
        ...,
        description="Unique relational chunk identifier in the Evidence Library.",
        examples=["chunk-1d5e12408afd-0000"],
    )
    document_id: str = Field(
        ...,
        description="Source document identifier.",
        examples=["doc-1d5e12408afd"],
    )
    title: str = Field(
        ...,
        description="Title of the source protocol or guideline document.",
    )
    source_publisher: Optional[str] = Field(
        default=None,
        description="Authoring agency or organization.",
    )
    char_start: int = Field(
        ...,
        description="Starting character offset in the normalized source document.",
    )
    char_end: int = Field(
        ...,
        description="Ending character offset in the normalized source document.",
    )
    similarity_score: float = Field(
        ...,
        description="Vector cosine similarity between user query and this passage.",
    )
    score_interpretation: str = Field(
        default="Cosine similarity indicates semantic phrasing proximity, not clinical truth or diagnostic confirmation.",
        description="Explicit notice regarding similarity score interpretation.",
    )
    excerpt: str = Field(
        ...,
        description="Text excerpt from the passage supporting the cited claim.",
    )
    is_verified: bool = Field(
        default=True,
        description="True if citation identifier was strictly verified against retrieved evidence.",
    )


class RetrievedPassageReference(BaseModel):
    """Full passage metadata for context inspectability in the assistant UI."""

    model_config = ConfigDict(frozen=True)

    passage_index: int = Field(
        ...,
        description="1-based index matching citation identifiers (1 -> [E1]).",
    )
    chunk_id: str
    document_id: str
    title: str
    source_publisher: Optional[str] = None
    similarity_score: float
    char_start: int
    char_end: int
    text: str


class AssistantAskRequest(BaseModel):
    """Inquiry request payload submitted to the Evidence-Grounded Assistant."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language public-health surveillance question.",
        examples=["What statistical threshold triggers a respiratory surge alert?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of evidence passages to retrieve for grounding.",
    )
    min_similarity: float = Field(
        default=0.30,
        ge=-1.0,
        le=1.0,
        description="Minimum cosine similarity cutoff for evidence inclusion.",
    )
    source_publisher: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Optional filter restricting evidence to a specific authoring agency.",
    )
    mode: Literal["concise", "detailed"] = Field(
        default="detailed",
        description="Response generation mode: 'concise' (approx 20 output tokens) or 'detailed' (approx 40 output tokens).",
    )
    fallback_on_timeout: bool = Field(
        default=True,
        description="When true, returns an evidence-first fallback with retrieved source passages and metadata if synthesis times out.",
    )


class AssistantAskResponse(BaseModel):
    """Structured evidence-grounded response."""

    model_config = ConfigDict(frozen=True)

    query_id: str = Field(
        ...,
        description="Unique request tracing identifier.",
    )
    question: str = Field(
        ...,
        description="Original user inquiry.",
    )
    answer: str = Field(
        ...,
        description="Evidence-grounded response text with [E#] citation tags.",
    )
    evidence_sufficiency: Literal["SUFFICIENT", "PARTIAL", "INSUFFICIENT"] = Field(
        ...,
        description="Assessment of whether retrieved evidence supports a reliable answer.",
    )
    citations: list[CitationItem] = Field(
        default_factory=list,
        description="List of verified evidence citations supporting the answer.",
    )
    retrieved_passages: list[RetrievedPassageReference] = Field(
        default_factory=list,
        description="All evidence passages retrieved and evaluated for this query.",
    )
    provider: str = Field(
        ...,
        description="Generation provider utilized ('ollama' or 'mock').",
    )
    model: str = Field(
        ...,
        description="Model name utilized for generation.",
    )
    latency_seconds: float = Field(
        ...,
        description="Total round-trip execution latency in seconds.",
    )
    response_type: Literal["synthesized", "evidence_fallback", "insufficient_refusal"] = Field(
        default="synthesized",
        description="Type of response: 'synthesized' (LLM-generated answer), 'evidence_fallback' (evidence passages provided directly without generative synthesis due to timeout), or 'insufficient_refusal' (zero-hallucination refusal).",
    )
    finish_reason: Optional[str] = Field(
        default="stop",
        description="Generation completion status: 'stop', 'timeout_fallback', 'insufficient_evidence', or 'incomplete'.",
    )
    response_mode: Optional[Literal["concise", "detailed"]] = Field(
        default="detailed",
        description="Response mode applied during execution ('concise' or 'detailed').",
    )
    warning: Optional[str] = Field(
        default=None,
        description="Optional warning or fallback notice.",
    )
    synthetic_data_notice: str = Field(
        default="SYNTHETIC-DATA NOTICE: All observations, indicators, and benchmark documents are part of a simulated research prototype. Documents represent reference material and guidelines for methodology testing.",
        description="Compliance notice regarding synthetic data prototype.",
    )
    non_clinical_notice: str = Field(
        default="DISCLAIMER: This assistant provides research methodology synthesis based on reference documents. It does not provide patient-specific clinical diagnosis, medical triage, or outbreak confirmation.",
        description="Non-clinical disclosure.",
    )


class AssistantStatusResponse(BaseModel):
    """Health and readiness telemetry for the Assistant subsystem."""

    model_config = ConfigDict(frozen=True)

    status: Literal["READY", "PROVIDER_UNAVAILABLE", "INDEX_DEGRADED", "NOT_CONFIGURED"] = Field(
        ...,
        description="High-level operational status of the assistant service.",
    )
    provider: str
    model: str
    provider_healthy: bool
    provider_message: str
    vector_index_status: str
    indexed_passages_count: int
    available_models: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Phase 6C Assistant grounded in local document evidence. "
        "Operates offline or with local Ollama daemon."
    )
