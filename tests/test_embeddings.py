"""Tests for Phase 6B.1 embedding generation and validation."""

import numpy as np
import pytest

from public_health_sentinel.documents.embeddings import (
    DeterministicMockEmbeddingService,
    EmbeddingError,
    EmbeddingModelError,
    EmbeddingValueError,
    LocalSentenceTransformerEmbeddingService,
)


def test_deterministic_mock_embedding_dimensions_and_norm():
    """Verify mock embedding produces 384-dimensional unit-normalized vectors."""
    service = DeterministicMockEmbeddingService(model_name="mock-minilm", expected_dim=384)

    vec = service.embed_text("Syndromic surveillance signal.")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (384,)
    assert vec.dtype == np.float32

    # L2 norm must be approximately 1.0
    norm = np.linalg.norm(vec)
    assert pytest.approx(norm, rel=1e-5) == 1.0


def test_deterministic_mock_embedding_stability():
    """Verify that identical texts yield strictly identical vectors across separate calls."""
    service = DeterministicMockEmbeddingService()
    t = "Emergency department daily visits for influenza-like illness."

    v1 = service.embed_text(t)
    v2 = service.embed_text(t)
    np.testing.assert_array_equal(v1, v2)


def test_embedding_rejects_empty_or_whitespace_text():
    """Verify that attempting to embed empty text raises EmbeddingValueError."""
    service = DeterministicMockEmbeddingService()

    with pytest.raises(EmbeddingValueError, match="empty or whitespace-only"):
        service.embed_text("")

    with pytest.raises(EmbeddingValueError, match="empty or whitespace-only"):
        service.embed_text("   \n\t  ")


def test_batch_embedding_matches_individual_embeddings():
    """Verify batch embedding produces stacked matrix matching individual vectors."""
    service = DeterministicMockEmbeddingService()
    texts = [
        "First surveillance report.",
        "Second clinical protocol.",
        "Third mobility indicator series.",
    ]

    batch_matrix = service.embed_batch(texts)
    assert batch_matrix.shape == (3, 384)

    for i, t in enumerate(texts):
        single_vec = service.embed_text(t)
        np.testing.assert_array_almost_equal(batch_matrix[i], single_vec)


def test_batch_embedding_empty_list():
    """Verify embedding an empty list returns an empty (0, 384) matrix."""
    service = DeterministicMockEmbeddingService()
    empty_res = service.embed_batch([])
    assert empty_res.shape == (0, 384)


def test_local_service_vector_validation_catches_nan_and_inf():
    """Verify that _validate_vector rejects NaN and Infinite values."""
    service = LocalSentenceTransformerEmbeddingService(expected_dim=384)

    # Valid vector
    valid_vec = np.ones(384, dtype=np.float32)
    normalized = service._validate_vector(valid_vec)
    assert pytest.approx(np.linalg.norm(normalized), rel=1e-5) == 1.0

    # Vector with NaN
    nan_vec = np.ones(384, dtype=np.float32)
    nan_vec[10] = np.nan
    with pytest.raises(EmbeddingValueError, match="NaN"):
        service._validate_vector(nan_vec)

    # Vector with Inf
    inf_vec = np.ones(384, dtype=np.float32)
    inf_vec[5] = np.inf
    with pytest.raises(EmbeddingValueError, match="infinite"):
        service._validate_vector(inf_vec)

    # Vector with incorrect dimension
    wrong_dim = np.ones(128, dtype=np.float32)
    with pytest.raises(EmbeddingValueError, match="dimension mismatch"):
        service._validate_vector(wrong_dim)


def test_local_service_model_initialization_failure():
    """Verify clear error is raised if an invalid model name cannot be loaded."""
    service = LocalSentenceTransformerEmbeddingService(
        model_name="nonexistent/model-that-does-not-exist-9999",
    )
    with pytest.raises(EmbeddingModelError, match="Failed to load local embedding model"):
        service.load_model()
