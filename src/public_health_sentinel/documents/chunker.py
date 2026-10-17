"""Document chunking and passage extraction module for PublicHealthSentinel Phase 6B.1.

Implements deterministic, traceable, structure-aware document chunking for
plain text (.txt) and Markdown (.md) reference documents.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Optional

from public_health_sentinel.documents.service import DocumentValidationError

DEFAULT_TARGET_CHUNK_SIZE: int = 800
DEFAULT_CHUNK_OVERLAP: int = 120


@dataclass(frozen=True)
class DocumentChunk:
    """Immutable representation of an extracted document passage chunk."""

    chunk_id: str
    document_id: str
    sequence_number: int
    text: str
    char_start: int
    char_end: int
    title: Optional[str]
    source_publisher: Optional[str]
    source_url: Optional[str]
    publication_date: Optional[date]
    content_hash: str
    created_at: datetime
    token_count_estimate: int

    def to_dict(self) -> dict:
        """Serialize chunk to dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        if self.publication_date:
            data["publication_date"] = self.publication_date.isoformat()
        return data


def normalize_text(text: str) -> str:
    """Normalize line endings and control characters without removing meaningful layout."""
    if not text:
        return ""
    # Normalize Windows CRLF and classic Mac CR to Unix LF
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    # Replace non-breaking spaces with standard space
    normalized = normalized.replace("\u00a0", " ")
    return normalized


def compute_chunk_id(document_id: str, sequence_number: int, chunk_text: str) -> str:
    """Generate deterministic, unique chunk ID combining doc, sequence, and text digest."""
    digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:8]
    return f"{document_id}_c{sequence_number:04d}_{digest}"


def split_text_into_chunks(
    text: str,
    document_id: str,
    title: Optional[str] = None,
    source_publisher: Optional[str] = None,
    source_url: Optional[str] = None,
    publication_date: Optional[date] = None,
    doc_format: str = "txt",
    target_chunk_size: int = DEFAULT_TARGET_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Split normalized document text into traceable, overlapping passage chunks.

    Args:
        text: Raw document text string.
        document_id: Identifier of the source document.
        title: Document title metadata.
        source_publisher: Authoring organization or department.
        source_url: Source link or DOI.
        publication_date: Published date.
        doc_format: Format string ('txt' or 'md').
        target_chunk_size: Desired chunk size in characters (~800 chars).
        chunk_overlap: Overlap between consecutive chunks in characters (~120 chars).

    Returns:
        List of DocumentChunk instances.

    Raises:
        DocumentValidationError: If content is empty or parameters are invalid.
    """
    if not text or not text.strip():
        raise DocumentValidationError("Document content cannot be empty or whitespace-only.")

    if target_chunk_size <= 0:
        raise DocumentValidationError(f"target_chunk_size must be positive, got {target_chunk_size}")

    if chunk_overlap < 0:
        raise DocumentValidationError(f"chunk_overlap cannot be negative, got {chunk_overlap}")

    if chunk_overlap >= target_chunk_size:
        raise DocumentValidationError(
            f"chunk_overlap ({chunk_overlap}) must be strictly less than target_chunk_size ({target_chunk_size})"
        )

    norm_text = normalize_text(text)
    total_len = len(norm_text)

    # If the total text is within target_chunk_size, return single chunk
    if total_len <= target_chunk_size:
        chunk_text = norm_text.strip()
        leading_ws = len(norm_text) - len(norm_text.lstrip())
        trailing_ws = len(norm_text) - len(norm_text.rstrip())
        exact_start = leading_ws
        exact_end = total_len - trailing_ws
        c_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        c_id = compute_chunk_id(document_id, 0, chunk_text)
        single_chunk = DocumentChunk(
            chunk_id=c_id,
            document_id=document_id,
            sequence_number=0,
            text=chunk_text,
            char_start=exact_start,
            char_end=exact_end,
            title=title,
            source_publisher=source_publisher,
            source_url=source_url,
            publication_date=publication_date,
            content_hash=c_hash,
            created_at=datetime.now(timezone.utc),
            token_count_estimate=max(1, len(chunk_text) // 4),
        )
        return [single_chunk]

    # Structure-aware paragraph & sentence segmentation
    chunks: list[DocumentChunk] = []
    start_idx = 0
    seq = 0

    while start_idx < total_len:
        # Determine candidate end boundary
        candidate_end = min(start_idx + target_chunk_size, total_len)

        if candidate_end < total_len:
            # Look backwards from candidate_end for a natural paragraph break (\n\n)
            search_window_start = max(start_idx + chunk_overlap, candidate_end - 200)
            para_break = norm_text.rfind("\n\n", search_window_start, candidate_end)
            if para_break != -1 and para_break > start_idx:
                candidate_end = para_break + 2
            else:
                # Look backwards for a sentence boundary: period, question mark, exclamation followed by space or newline
                sentence_match = list(re.finditer(r"[.!?](?:\s+|\n+)", norm_text[search_window_start:candidate_end]))
                if sentence_match:
                    last_match = sentence_match[-1]
                    candidate_end = search_window_start + last_match.end()
                else:
                    # Look for whitespace boundary to avoid breaking a word
                    space_idx = norm_text.rfind(" ", search_window_start, candidate_end)
                    if space_idx != -1 and space_idx > start_idx:
                        candidate_end = space_idx + 1

        chunk_raw = norm_text[start_idx:candidate_end]
        chunk_text = chunk_raw.strip()

        if chunk_text:
            leading_ws = len(chunk_raw) - len(chunk_raw.lstrip())
            trailing_ws = len(chunk_raw) - len(chunk_raw.rstrip())
            exact_start = start_idx + leading_ws
            exact_end = candidate_end - trailing_ws

            c_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            c_id = compute_chunk_id(document_id, seq, chunk_text)

            chunk = DocumentChunk(
                chunk_id=c_id,
                document_id=document_id,
                sequence_number=seq,
                text=chunk_text,
                char_start=exact_start,
                char_end=exact_end,
                title=title,
                source_publisher=source_publisher,
                source_url=source_url,
                publication_date=publication_date,
                content_hash=c_hash,
                created_at=datetime.now(timezone.utc),
                token_count_estimate=max(1, len(chunk_text) // 4),
            )
            chunks.append(chunk)
            seq += 1

        if candidate_end >= total_len:
            break

        # Calculate next start index using overlap
        next_start = candidate_end - chunk_overlap
        # Guard against zero or negative progress
        if next_start <= start_idx:
            next_start = start_idx + 1
        start_idx = next_start

    return chunks
