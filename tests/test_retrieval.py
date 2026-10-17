"""Tests for Phase 6B.1 persistent vector indexing and semantic retrieval service."""

import json
from datetime import date
from pathlib import Path
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from public_health_sentinel.db.models import Base, DocumentChunkModel
from public_health_sentinel.documents.embeddings import DeterministicMockEmbeddingService
from public_health_sentinel.documents.index import (
    IncompatibleIndexModelError,
    VectorIndexError,
    VectorIndexManager,
)
from public_health_sentinel.documents.retrieval import (
    RetrievalValidationError,
    SemanticRetrievalService,
)


@pytest.fixture
def temp_index_dir(tmp_path: Path) -> Path:
    idx_dir = tmp_path / "test_index"
    idx_dir.mkdir(parents=True, exist_ok=True)
    return idx_dir


@pytest.fixture
def mock_embedding_svc() -> DeterministicMockEmbeddingService:
    return DeterministicMockEmbeddingService(model_name="mock-minilm-v1", expected_dim=384)


@pytest.fixture
def in_memory_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_empty_vector_index(temp_index_dir: Path):
    """Verify an empty index initializes safely and returns 0 hits."""
    mgr = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name="mock-model")
    assert mgr.total_vectors == 0
    assert mgr.dimension == 384

    query_vec = np.ones(384, dtype=np.float32)
    hits = mgr.search(query_vec, top_k=5)
    assert hits == []


def test_vector_index_add_and_search_ranking(temp_index_dir: Path, mock_embedding_svc):
    """Verify adding vectors, persistence, and descending cosine similarity ranking."""
    mgr = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name=mock_embedding_svc.model_name)

    # Create 3 passages
    texts = [
        "Asthma and respiratory distress syndrome triage guidelines in ambulatory clinics.",
        "Foodborne outbreak investigation methods and stool pathogen testing protocols.",
        "Transit station passenger density and mobility volume indicators.",
    ]
    vecs = mock_embedding_svc.embed_batch(texts)

    chunks = [
        ("chunk-resp-01", "doc-resp", vecs[0]),
        ("chunk-food-02", "doc-food", vecs[1]),
        ("chunk-mobi-03", "doc-mobi", vecs[2]),
    ]
    mgr.add_chunks(chunks, model_name=mock_embedding_svc.model_name)
    assert mgr.total_vectors == 3

    # Query with identical text to passage 0
    query_vec = mock_embedding_svc.embed_text("Asthma and respiratory distress syndrome triage guidelines in ambulatory clinics.")
    hits = mgr.search(query_vec, top_k=3)

    assert len(hits) == 3
    # Top hit must be chunk-resp-01 with cosine similarity near 1.0
    top_chunk, top_score = hits[0]
    assert top_chunk == "chunk-resp-01"
    assert pytest.approx(top_score, rel=1e-4) == 1.0

    # Remaining hits should have lower scores
    assert hits[0][1] >= hits[1][1] >= hits[2][1]


def test_vector_index_persistence_and_reload(temp_index_dir: Path, mock_embedding_svc):
    """Verify that saving and creating a new manager reloads persisted vectors accurately."""
    mgr1 = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name="test-model")
    v1 = mock_embedding_svc.embed_text("Persistent evidence chunk 1.")
    v2 = mock_embedding_svc.embed_text("Persistent evidence chunk 2.")

    mgr1.add_chunks([("c1", "d1", v1), ("c2", "d2", v2)], model_name="test-model")
    assert mgr1.total_vectors == 2

    # Instantiate separate manager pointing to same directory
    mgr2 = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name="test-model")
    assert mgr2.total_vectors == 2
    assert mgr2.active_model_name == "test-model"

    hits = mgr2.search(v1, top_k=1)
    assert len(hits) == 1
    assert hits[0][0] == "c1"


def test_vector_index_incompatible_model_rejection(temp_index_dir: Path, mock_embedding_svc):
    """Verify that attempting to add embeddings from an incompatible model is rejected."""
    mgr = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name="model-alpha")
    v = mock_embedding_svc.embed_text("Test passage.")
    mgr.add_chunks([("c1", "d1", v)], model_name="model-alpha")

    # Attempt adding with model-beta
    with pytest.raises(IncompatibleIndexModelError, match="Cannot add vectors generated with model 'model-beta'"):
        mgr.add_chunks([("c2", "d2", v)], model_name="model-beta")


def test_vector_index_rebuild_from_db(temp_index_dir: Path, in_memory_db: Session, mock_embedding_svc):
    """Verify rebuilding the index from relational DocumentChunkModel rows."""
    mgr = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name=mock_embedding_svc.model_name)

    v1 = mock_embedding_svc.embed_text("Rebuilt passage 1.")
    c1 = DocumentChunkModel(
        chunk_id="chunk-reb-1",
        document_id="doc-reb",
        sequence_number=0,
        text="Rebuilt passage 1.",
        char_start=0,
        char_end=19,
        title="Rebuild Test",
        source_publisher="Test Publisher",
        content_hash="abc1",
        embedding_json=json.dumps(v1.tolist()),
        embedding_model=mock_embedding_svc.model_name,
    )
    in_memory_db.add(c1)
    in_memory_db.commit()

    rebuilt_count = mgr.rebuild_from_db(session=in_memory_db, embedding_service=mock_embedding_svc)
    assert rebuilt_count == 1
    assert mgr.total_vectors == 1

    hits = mgr.search(v1, top_k=1)
    assert hits[0][0] == "chunk-reb-1"


def test_semantic_retrieval_service_filters_and_validation(temp_index_dir: Path, in_memory_db: Session, mock_embedding_svc):
    """Verify SemanticRetrievalService query validation and metadata filtering."""
    mgr = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name=mock_embedding_svc.model_name)

    # Ingest 2 chunks from different publishers
    v_cdc = mock_embedding_svc.embed_text("CDC guidelines for respiratory outbreaks.")
    v_who = mock_embedding_svc.embed_text("WHO international health regulations.")

    c_cdc = DocumentChunkModel(
        chunk_id="c-cdc",
        document_id="doc-cdc",
        sequence_number=0,
        text="CDC guidelines for respiratory outbreaks.",
        char_start=0,
        char_end=41,
        title="CDC Guidelines",
        source_publisher="CDC",
        content_hash="hash-cdc",
        embedding_json=json.dumps(v_cdc.tolist()),
        embedding_model=mock_embedding_svc.model_name,
    )
    c_who = DocumentChunkModel(
        chunk_id="c-who",
        document_id="doc-who",
        sequence_number=0,
        text="WHO international health regulations.",
        char_start=0,
        char_end=37,
        title="WHO Regulations",
        source_publisher="WHO",
        content_hash="hash-who",
        embedding_json=json.dumps(v_who.tolist()),
        embedding_model=mock_embedding_svc.model_name,
    )
    in_memory_db.add_all([c_cdc, c_who])
    in_memory_db.commit()

    mgr.add_chunks([("c-cdc", "doc-cdc", v_cdc), ("c-who", "doc-who", v_who)], model_name=mock_embedding_svc.model_name)

    svc = SemanticRetrievalService(vector_index=mgr, embedding_service=mock_embedding_svc)

    # Invalid empty query
    with pytest.raises(RetrievalValidationError, match="cannot be empty"):
        svc.search(in_memory_db, query="   ")

    # Invalid top_k
    with pytest.raises(RetrievalValidationError, match="top_k must be between"):
        svc.search(in_memory_db, query="respiratory", top_k=0)

    # Filter by publisher "CDC"
    res_cdc = svc.search(in_memory_db, query="respiratory outbreaks", source_publisher="CDC", top_k=5)
    assert res_cdc.total_results == 1
    assert res_cdc.items[0].chunk_id == "c-cdc"
    assert res_cdc.items[0].source_publisher == "CDC"

    # Filter by non-existent publisher
    res_none = svc.search(in_memory_db, query="respiratory outbreaks", source_publisher="State Agency", top_k=5)
    assert res_none.total_results == 0


def test_vector_index_degradation_on_missing_or_corrupt_files(temp_index_dir: Path, mock_embedding_svc):
    """Verify index degradation is detected and reported when files are missing or corrupted."""
    mgr = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name="test-model")
    v = mock_embedding_svc.embed_text("Test passage.")
    mgr.add_chunks([("c1", "d1", v)], model_name="test-model")

    # Corrupt the npz file
    npz_path = temp_index_dir / "evidence_vector_index.npz"
    npz_path.write_bytes(b"CORRUPTED_GARBAGE_BYTES")

    mgr2 = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name="test-model")
    assert mgr2.is_degraded is True
    assert "Corrupted or incompatible" in (mgr2.degraded_reason or "")
    assert mgr2.total_vectors == 0


def test_vector_index_degradation_on_dimension_mismatch(temp_index_dir: Path):
    """Verify dimension mismatch flags index as degraded."""
    meta_path = temp_index_dir / "evidence_vector_index_meta.json"
    npz_path = temp_index_dir / "evidence_vector_index.npz"
    meta_path.write_text(json.dumps({"dimension": 512, "embedding_model": "test-model"}), encoding="utf-8")
    npz_path.write_bytes(b"placeholder")

    mgr = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name="test-model")
    assert mgr.is_degraded is True
    assert "dimension mismatch" in (mgr.degraded_reason or "").lower()


def test_vector_index_deterministic_tie_breaking(temp_index_dir: Path, mock_embedding_svc):
    """Verify that identical vectors produce deterministic ranking tie-broken by chunk_id."""
    mgr = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name="test-model")
    v = mock_embedding_svc.embed_text("Identical passage text.")

    # Insert two chunks with identical vectors in reverse order
    mgr.add_chunks([("chunk_beta", "doc1", v), ("chunk_alpha", "doc1", v)], model_name="test-model")

    hits = mgr.search(v, top_k=2)
    assert len(hits) == 2
    # chunk_alpha must precede chunk_beta due to alphabetical tie-breaking
    assert hits[0][0] == "chunk_alpha"
    assert hits[1][0] == "chunk_beta"


def test_vector_index_rejects_nan_query(temp_index_dir: Path):
    """Verify search rejects queries containing NaN or Infinite values."""
    mgr = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name="test-model")
    nan_query = np.ones(384, dtype=np.float32)
    nan_query[10] = np.nan

    with pytest.raises(VectorIndexError, match="NaN or Infinite"):
        mgr.search(nan_query, top_k=5)


def test_semantic_retrieval_incompatible_model_detection(temp_index_dir: Path, in_memory_db: Session, mock_embedding_svc):
    """Verify SemanticRetrievalService rejects search when query service model differs from index model."""
    mgr = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name="model-alpha")
    v = mock_embedding_svc.embed_text("Test passage.")
    mgr.add_chunks([("c1", "d1", v)], model_name="model-alpha")

    # Retrieval service configured with model-beta
    query_svc = DeterministicMockEmbeddingService(model_name="model-beta", expected_dim=384)
    retrieval_svc = SemanticRetrievalService(vector_index=mgr, embedding_service=query_svc)

    with pytest.raises(IncompatibleIndexModelError, match="is incompatible with current query embedding model"):
        retrieval_svc.search(in_memory_db, query="test query")


def test_semantic_retrieval_orphaned_chunk_skipping(temp_index_dir: Path, in_memory_db: Session, mock_embedding_svc):
    """Verify that vectors in index whose database records have been deleted are skipped."""
    mgr = VectorIndexManager(index_dir=temp_index_dir, expected_dim=384, model_name=mock_embedding_svc.model_name)
    v1 = mock_embedding_svc.embed_text("Existing passage.")
    v2 = mock_embedding_svc.embed_text("Orphaned passage.")

    # Only c1 is added to database
    c1 = DocumentChunkModel(
        chunk_id="c-exist",
        document_id="doc-1",
        sequence_number=0,
        text="Existing passage.",
        char_start=0,
        char_end=17,
        title="Doc 1",
        source_publisher="Agency",
        content_hash="h1",
        embedding_json=json.dumps(v1.tolist()),
        embedding_model=mock_embedding_svc.model_name,
    )
    in_memory_db.add(c1)
    in_memory_db.commit()

    # Index contains both c-exist and c-orphaned
    mgr.add_chunks([("c-exist", "doc-1", v1), ("c-orphaned", "doc-1", v2)], model_name=mock_embedding_svc.model_name)

    svc = SemanticRetrievalService(vector_index=mgr, embedding_service=mock_embedding_svc)
    res = svc.search(in_memory_db, query="passage", top_k=5)

    # Only c-exist should be returned; c-orphaned must be excluded
    assert res.total_results == 1
    assert res.items[0].chunk_id == "c-exist"


def test_chunk_exact_char_offsets_slice_fidelity():
    """Verify that normalized_text[char_start:char_end] exactly matches chunk.text."""
    from public_health_sentinel.documents.chunker import split_text_into_chunks, normalize_text

    raw_text = (
        "\n\n# Syndromic Surveillance Protocol\n\n"
        "Section 1: Initial Assessment.\n"
        "Emergency departments monitor daily encounters for respiratory symptoms.\n\n"
        "Section 2: Secondary Evaluation.\n"
        "Epidemiology teams verify chief complaint data within 4 hours of alert.\n\n"
    )
    norm = normalize_text(raw_text)

    chunks = split_text_into_chunks(raw_text, document_id="doc-test", target_chunk_size=120, chunk_overlap=30)
    assert len(chunks) >= 2

    for c in chunks:
        sliced = norm[c.char_start:c.char_end]
        assert sliced == c.text
        assert len(c.content_hash) == 64

