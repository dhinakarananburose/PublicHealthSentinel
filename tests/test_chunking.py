"""Tests for Phase 6B.1 document chunking and passage extraction."""

import pytest
from datetime import date

from public_health_sentinel.documents.chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_TARGET_CHUNK_SIZE,
    DocumentChunk,
    compute_chunk_id,
    normalize_text,
    split_text_into_chunks,
)
from public_health_sentinel.documents.service import DocumentValidationError


def test_normalize_text_crlf_and_non_breaking_spaces():
    """Verify that CRLF line endings and NBSP are normalized to LF and spaces."""
    raw = "Header Line\r\nSecond Line\rThird\u00a0Word"
    normalized = normalize_text(raw)
    assert "\r" not in normalized
    assert "\u00a0" not in normalized
    assert normalized == "Header Line\nSecond Line\nThird Word"


def test_chunking_empty_or_whitespace_document_rejected():
    """Verify that empty or whitespace-only documents raise DocumentValidationError."""
    with pytest.raises(DocumentValidationError, match="empty or whitespace-only"):
        split_text_into_chunks("", document_id="doc-test-1")

    with pytest.raises(DocumentValidationError, match="empty or whitespace-only"):
        split_text_into_chunks("   \n\n\t  ", document_id="doc-test-1")


def test_chunking_invalid_parameters_rejected():
    """Verify validation when target_chunk_size or chunk_overlap are out of valid bounds."""
    text = "Valid test document content."
    with pytest.raises(DocumentValidationError, match="target_chunk_size must be positive"):
        split_text_into_chunks(text, document_id="doc-1", target_chunk_size=0)

    with pytest.raises(DocumentValidationError, match="chunk_overlap cannot be negative"):
        split_text_into_chunks(text, document_id="doc-1", chunk_overlap=-5)

    with pytest.raises(DocumentValidationError, match="must be strictly less"):
        split_text_into_chunks(text, document_id="doc-1", target_chunk_size=200, chunk_overlap=200)


def test_chunking_short_document_returns_single_chunk():
    """A document shorter than target_chunk_size should yield exactly one chunk."""
    content = "Syndromic surveillance monitors early clinical indicators of infectious disease outbreaks."
    chunks = split_text_into_chunks(
        text=content,
        document_id="doc-short-001",
        title="Surveillance Intro",
        source_publisher="Public Health Agency",
        source_url="https://example.gov/surveillance",
        publication_date=date(2025, 1, 15),
        target_chunk_size=800,
        chunk_overlap=120,
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.document_id == "doc-short-001"
    assert chunk.sequence_number == 0
    assert chunk.text == content
    assert chunk.char_start == 0
    assert chunk.char_end == len(content)
    assert chunk.title == "Surveillance Intro"
    assert chunk.source_publisher == "Public Health Agency"
    assert chunk.source_url == "https://example.gov/surveillance"
    assert chunk.publication_date == date(2025, 1, 15)
    assert chunk.content_hash is not None
    assert chunk.token_count_estimate > 0


def test_chunking_long_document_splits_with_overlap():
    """Verify long document segmentation, sequence ordering, and overlap behavior."""
    # Generate 5 paragraphs of distinct content (~2500 characters total)
    paragraphs = [
        f"Paragraph {i}: Rapid syndromic surveillance relies on emergency department chief complaints. "
        f"Daily counts exceeding the statistical baseline trigger secondary epidemiological investigations. "
        f"Threshold evaluation incorporates seasonal baseline models, rolling mean absolute deviations, and variance caps. "
        f"Surveillance analysts verify clinical data integrity before classifying an observation as anomalous."
        for i in range(1, 10)
    ]
    full_text = "\n\n".join(paragraphs)

    target_size = 500
    overlap = 100

    chunks = split_text_into_chunks(
        text=full_text,
        document_id="doc-long-002",
        target_chunk_size=target_size,
        chunk_overlap=overlap,
    )

    assert len(chunks) > 1

    # Verify sequence numbers are monotonic starting from 0
    for idx, c in enumerate(chunks):
        assert c.sequence_number == idx
        assert len(c.text) > 0
        assert c.char_start >= 0
        assert c.char_end <= len(full_text)
        assert c.char_start < c.char_end

    # Verify that consecutive chunks advance and have overlapping character intervals
    for i in range(len(chunks) - 1):
        current_chunk = chunks[i]
        next_chunk = chunks[i + 1]
        assert next_chunk.char_start > current_chunk.char_start
        assert next_chunk.char_start < current_chunk.char_end


def test_chunking_deterministic_ids():
    """Verify that identical inputs produce exactly identical deterministic chunk IDs."""
    text = (
        "Case Definition for Viral Hemorrhagic Fever: Acute onset of high fever and unexplained hemorrhage.\n\n"
        "Immediate isolation protocols must be instituted upon patient triage in all emergency facilities."
    )
    doc_id = "doc-stable-003"

    run1 = split_text_into_chunks(text, document_id=doc_id, target_chunk_size=120, chunk_overlap=30)
    run2 = split_text_into_chunks(text, document_id=doc_id, target_chunk_size=120, chunk_overlap=30)

    assert len(run1) == len(run2)
    for c1, c2 in zip(run1, run2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.sequence_number == c2.sequence_number
        assert c1.content_hash == c2.content_hash


def test_chunking_unicode_content_preservation():
    """Verify handling of Unicode characters, accents, and international public health terms."""
    unicode_text = (
        "# Surveillance Épidémiologique Internationale 2026\n\n"
        "Région Sanitaire: Détection précoce des flambées épidémiques.\n"
        "Évaluation des anomalies statistiques (ex. μ + 3σ, valeur p < 0.001).\n"
        "Contrôle de conformité de données: température corporelle ≥ 38.5 °C."
    )

    chunks = split_text_into_chunks(
        text=unicode_text,
        document_id="doc-unicode-004",
        target_chunk_size=200,
        chunk_overlap=40,
    )

    assert len(chunks) >= 1
    combined_text = " ".join(c.text for c in chunks)
    assert "Épidémiologique" in combined_text
    assert "≥ 38.5 °C" in combined_text
