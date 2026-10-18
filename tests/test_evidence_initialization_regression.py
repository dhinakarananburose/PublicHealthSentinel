"""Regression tests for evidence index initialization, self-healing, and public demo security.

Validates:
1. Production startup initializes evidence index from database chunks.
2. Missing or ephemeral index files are automatically rebuilt from DB records without duplication.
3. Embedding consistency across evidence/status, evidence/search, and assistant/status.
4. Semantic retrieval respects the >= 0.30 similarity threshold and ranks methodology protocol #1 for Rolling MAD.
5. Incompatible embedding models return 409 Conflict.
6. Public demo mode strictly protects POST /api/v1/evidence/rebuild with HTTP 403 Forbidden.
7. Startup initialization is idempotent across repeated calls.
"""

from datetime import date
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from public_health_sentinel.config import get_config
from public_health_sentinel.db.demo_seeder import is_db_empty, seed_demo_data_if_needed
from public_health_sentinel.db.models import Base, DocumentChunkModel, DocumentMetadataModel
from public_health_sentinel.db.session import get_db_session
from public_health_sentinel.documents.embeddings import (
    DeterministicMockEmbeddingService,
    get_embedding_service,
)
from public_health_sentinel.documents.index import (
    VectorIndexManager,
    ensure_evidence_index_initialized,
    get_vector_index,
)
from public_health_sentinel.documents.retrieval import (
    IncompatibleIndexModelError,
    SemanticRetrievalService,
)
from public_health_sentinel.api.app import app


@pytest.fixture
def regression_db(tmp_path: Path):
    """Create an isolated SQLite database and index directory."""
    db_path = tmp_path / "regression.db"
    index_dir = tmp_path / "index"
    index_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Seed demo data
    seed_demo_data_if_needed(session)

    yield session, index_dir, db_path

    session.close()


def test_startup_initialization_creates_index(regression_db):
    """Test 1: Verify startup initialization safely builds persistent index from DB chunks."""
    session, index_dir, _ = regression_db

    # Initialize index in isolated directory
    with patch.dict(os.environ, {"DEMO_MODE": "true", "EMBEDDING_PROVIDER": "tfidf"}):
        get_config.cache_clear()
        emb_svc = get_embedding_service()
        idx_mgr = get_vector_index(force_new=True, embedding_service=emb_svc, index_dir=index_dir)

        init_result = ensure_evidence_index_initialized(
            session=session,
            embedding_service=emb_svc,
        )

        assert init_result["status"] == "HEALTHY"
        assert init_result["total_vectors"] == 10
        assert (index_dir / "evidence_vector_index.npz").exists()
        assert (index_dir / "evidence_vector_index_meta.json").exists()
        assert idx_mgr.total_vectors == 10
        assert idx_mgr.active_model_name == "lightweight-hashing-384"


def test_startup_initialization_is_idempotent(regression_db):
    """Test 2: Multiple startup calls are idempotent and do not duplicate documents or chunks."""
    session, index_dir, _ = regression_db

    with patch.dict(os.environ, {"DEMO_MODE": "true", "EMBEDDING_PROVIDER": "tfidf"}):
        get_config.cache_clear()
        emb_svc = get_embedding_service()
        get_vector_index(force_new=True, embedding_service=emb_svc, index_dir=index_dir)

        # First run builds index
        res1 = ensure_evidence_index_initialized(session=session, embedding_service=emb_svc)
        assert res1["action"] in {"rebuilt", "none"}

        # Second run must be no-op (action: "none")
        res2 = ensure_evidence_index_initialized(session=session, embedding_service=emb_svc)
        assert res2["action"] == "none"
        assert res2["status"] == "HEALTHY"

        # Verify DB counts remain strictly unchanged
        assert session.query(DocumentMetadataModel).count() == 6
        assert session.query(DocumentChunkModel).count() == 10



def test_ephemeral_missing_index_recovery(regression_db):
    """Test 3: Deleting index files triggers automatic self-healing without chunk duplication."""
    session, index_dir, _ = regression_db

    with patch.dict(os.environ, {"DEMO_MODE": "true", "EMBEDDING_PROVIDER": "tfidf"}):
        get_config.cache_clear()
        emb_svc = get_embedding_service()
        idx = get_vector_index(force_new=True, embedding_service=emb_svc, index_dir=index_dir)

        ensure_evidence_index_initialized(session=session, embedding_service=emb_svc)
        assert (index_dir / "evidence_vector_index.npz").exists()

        # Delete persistent index files simulating ephemeral container restart
        (index_dir / "evidence_vector_index.npz").unlink()
        (index_dir / "evidence_vector_index_meta.json").unlink()

        # Reload index from disk (which is now missing)
        idx_reloaded = get_vector_index(force_new=True, embedding_service=emb_svc, index_dir=index_dir)
        assert idx_reloaded.total_vectors == 0

        # Self-healing rebuild
        res = ensure_evidence_index_initialized(session=session, embedding_service=emb_svc)
        assert res["status"] == "HEALTHY"
        assert res["action"] == "rebuilt"
        assert res["total_vectors"] == 10
        assert (index_dir / "evidence_vector_index.npz").exists()
        assert session.query(DocumentChunkModel).count() == 10


def test_evidence_and_assistant_status_consistency(regression_db):
    """Test 4: Verify evidence/status and assistant/status report consistent, truthful models and counts."""
    session, index_dir, db_path = regression_db

    with patch.dict(os.environ, {"DEMO_MODE": "true", "EMBEDDING_PROVIDER": "tfidf", "DATABASE_URL": f"sqlite:///{db_path}"}):
        get_config.cache_clear()
        emb_svc = get_embedding_service()
        get_vector_index(force_new=True, embedding_service=emb_svc, index_dir=index_dir)
        ensure_evidence_index_initialized(session=session, embedding_service=emb_svc)

        def override_db():
            yield session

        app.dependency_overrides[get_db_session] = override_db
        try:
            client = TestClient(app)

            # Check evidence status
            ev_resp = client.get("/api/v1/evidence/status")
            assert ev_resp.status_code == 200
            ev_data = ev_resp.json()
            assert ev_data["status"] == "HEALTHY"
            assert ev_data["total_indexed_chunks"] == 10
            assert ev_data["total_indexed_documents"] == 6
            assert ev_data["active_embedding_model"] == "lightweight-hashing-384"
            assert ev_data["configured_embedding_model"] == "lightweight-hashing-384"
            assert ev_data["index_file_exists"] is True
            assert ev_data["meta_file_exists"] is True

            # Check assistant status
            as_resp = client.get("/api/v1/assistant/status")
            assert as_resp.status_code == 200
            as_data = as_resp.json()
            assert as_data["vector_index_status"] == "HEALTHY"
            assert as_data["indexed_passages_count"] == 10

            # Check evidence search model
            search_resp = client.post("/api/v1/evidence/search", json={"query": "rolling median absolute deviation", "top_k": 3})
            assert search_resp.status_code == 200
            search_data = search_resp.json()
            assert search_data["embedding_model"] == "lightweight-hashing-384"
            assert search_data["total_results"] > 0
        finally:
            app.dependency_overrides.clear()


def test_evidence_search_rolling_mad_ranking_and_threshold(regression_db):
    """Test 5: Verify Rolling MAD query retrieves methodology protocol #1 with similarity >= 0.30."""
    session, index_dir, _ = regression_db

    with patch.dict(os.environ, {"DEMO_MODE": "true", "EMBEDDING_PROVIDER": "tfidf"}):
        get_config.cache_clear()
        emb_svc = get_embedding_service()
        idx_mgr = get_vector_index(force_new=True, embedding_service=emb_svc, index_dir=index_dir)
        ensure_evidence_index_initialized(session=session, embedding_service=emb_svc)

        retrieval_svc = SemanticRetrievalService(vector_index=idx_mgr, embedding_service=emb_svc)
        results = retrieval_svc.search(
            session=session,
            query="How does Rolling Median Absolute Deviation (MAD) calculate dispersion and handle outliers?",
            top_k=3,
            min_similarity=0.30,
        )

        assert results.total_results >= 1
        top_item = results.items[0]
        assert "Statistical Anomaly Detection Methodology Protocol" in (top_item.title or "")
        assert top_item.similarity_score >= 0.30
        assert "raw_mad = median(|X_i - median(X)|)" in top_item.text
        assert "scale = 1.4826 * raw_mad" in top_item.text
        assert "50% breakdown point" in top_item.text


def test_incompatible_model_detection_returns_409(regression_db):
    """Test 6: Verify mismatched embedding model raises 409 Conflict in evidence search endpoint."""
    session, index_dir, db_path = regression_db

    with patch.dict(os.environ, {"DEMO_MODE": "true", "EMBEDDING_PROVIDER": "tfidf", "DATABASE_URL": f"sqlite:///{db_path}"}):
        get_config.cache_clear()
        # Create index with model-alpha
        idx = VectorIndexManager(index_dir=index_dir, expected_dim=384, model_name="model-alpha")
        emb_svc = get_embedding_service()
        v = emb_svc.embed_text("Sample passage.")
        idx.add_chunks([("chk-1", "doc-1", v)], model_name="model-alpha")

        # Now query with standard embedding service (lightweight-hashing-384)
        retrieval_svc = SemanticRetrievalService(vector_index=idx, embedding_service=emb_svc)

        with pytest.raises(IncompatibleIndexModelError, match="is incompatible with current query embedding model"):
            retrieval_svc.search(session=session, query="test query")


def test_public_demo_rebuild_forbidden(regression_db):
    """Test 7: Verify POST /api/v1/evidence/rebuild returns 403 Forbidden in demo mode."""
    session, index_dir, db_path = regression_db

    with patch.dict(os.environ, {"DEMO_MODE": "true", "DATABASE_URL": f"sqlite:///{db_path}"}):
        get_config.cache_clear()

        def override_db():
            yield session

        app.dependency_overrides[get_db_session] = override_db
        try:
            client = TestClient(app)
            resp = client.post("/api/v1/evidence/rebuild")
            assert resp.status_code == 403
            data = resp.json()
            err_msg = data.get("detail", "") or data.get("message", "")
            assert "disabled in public demonstration mode" in err_msg
        finally:
            app.dependency_overrides.clear()


def test_negative_control_queries_rejected(regression_db):
    """Test 8: Verify completely unrelated queries return zero results under >= 0.30 cutoff."""
    session, index_dir, _ = regression_db

    with patch.dict(os.environ, {"DEMO_MODE": "true", "EMBEDDING_PROVIDER": "tfidf"}):
        get_config.cache_clear()
        emb_svc = get_embedding_service()
        idx_mgr = get_vector_index(force_new=True, embedding_service=emb_svc, index_dir=index_dir)
        ensure_evidence_index_initialized(session=session, embedding_service=emb_svc)

        retrieval_svc = SemanticRetrievalService(vector_index=idx_mgr, embedding_service=emb_svc)

        neg_queries = [
            "Quantum computing algorithms for portfolio optimization",
            "Astronomy telescope focal length calibration",
            "What is the capital of France?",
        ]

        for nq in neg_queries:
            res = retrieval_svc.search(session=session, query=nq, top_k=5, min_similarity=0.30)
            assert res.total_results == 0, f"Expected 0 results for negative control query '{nq}', got {res.total_results}"


def test_respiratory_vs_methodology_query_discrimination(regression_db):
    """Test 9: Verify query discrimination between methodology protocol and respiratory operational threshold."""
    session, index_dir, _ = regression_db

    with patch.dict(os.environ, {"DEMO_MODE": "true", "EMBEDDING_PROVIDER": "tfidf"}):
        get_config.cache_clear()
        emb_svc = get_embedding_service()
        idx_mgr = get_vector_index(force_new=True, embedding_service=emb_svc, index_dir=index_dir)
        ensure_evidence_index_initialized(session=session, embedding_service=emb_svc)

        retrieval_svc = SemanticRetrievalService(vector_index=idx_mgr, embedding_service=emb_svc)

        # 1. Methodology query: must retrieve methodology as #1, score >= 0.30, and respiratory must not beat it
        mad_res = retrieval_svc.search(
            session=session,
            query="How does Rolling Median Absolute Deviation (MAD) calculate dispersion and handle outliers?",
            top_k=5,
            min_similarity=0.30,
        )
        assert mad_res.total_results >= 1
        assert "Statistical Anomaly Detection Methodology Protocol" in mad_res.items[0].title
        assert mad_res.items[0].similarity_score >= 0.30

        # Respiratory surge must not be top-1 for the methodology question
        for item in mad_res.items:
            if "Respiratory Surge" in item.title:
                assert item.similarity_score < mad_res.items[0].similarity_score

        # 2. Operational respiratory query: must retrieve respiratory protocol as #1, score >= 0.30
        resp_res = retrieval_svc.search(
            session=session,
            query="What is the threshold for respiratory surge alerts in emergency departments?",
            top_k=5,
            min_similarity=0.30,
        )
        assert resp_res.total_results >= 1
        assert "Respiratory Surge Statistical Threshold Protocol" in resp_res.items[0].title
        assert resp_res.items[0].similarity_score >= 0.30


def test_seeder_heals_missing_methodology_document(tmp_path: Path):
    """Test 10: Verify demo seeder adds missing methodology document when database already has other docs."""
    db_path = tmp_path / "partial.db"
    index_dir = tmp_path / "partial_index"
    index_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    from public_health_sentinel.documents.service import ingest_document
    from public_health_sentinel.documents.chunker import split_text_into_chunks

    # Seed only 1 dummy document simulating a partial or older database
    dummy_doc, _ = ingest_document(
        session=session,
        filename="dummy_older_doc.md",
        content="Dummy document content for legacy test.",
        title="Legacy Dummy Document",
        source_publisher="Legacy Taskforce",
        publication_date=date(2025, 1, 1),
    )
    session.commit()
    dummy_chunks = split_text_into_chunks(
        text="Dummy document content for legacy test.",
        document_id=dummy_doc.document_id,
        title=dummy_doc.title,
        source_publisher=dummy_doc.source_publisher,
        source_url=None,
        publication_date=None,
        doc_format="md",
        target_chunk_size=800,
        chunk_overlap=120,
    )
    for dc in dummy_chunks:
        session.add(
            DocumentChunkModel(
                chunk_id=dc.chunk_id,
                document_id=dummy_doc.document_id,
                sequence_number=dc.sequence_number,
                text=dc.text,
                char_start=dc.char_start,
                char_end=dc.char_end,
                title=dc.title,
                source_publisher=dc.source_publisher,
                content_hash=dc.content_hash,
            )
        )
    session.commit()

    assert session.query(DocumentMetadataModel).count() == 1

    # Now run seed_demo_data_if_needed on this partial database
    with patch.dict(os.environ, {"DEMO_MODE": "true", "EMBEDDING_PROVIDER": "tfidf"}):
        get_config.cache_clear()
        emb_svc = get_embedding_service()
        get_vector_index(force_new=True, embedding_service=emb_svc, index_dir=index_dir)

        counts = seed_demo_data_if_needed(session)
        assert counts["documents"] == 6
        assert counts["chunks"] == 10

        # Verify methodology document was seeded
        meth_doc = session.scalar(
            select(DocumentMetadataModel).where(
                DocumentMetadataModel.filename == "statistical_anomaly_detection_methods.md"
            )
        )
        assert meth_doc is not None
        assert "Statistical Anomaly Detection Methodology Protocol" in meth_doc.title

        # Verify its 4 chunks exist
        meth_chunks = session.scalars(
            select(DocumentChunkModel).where(DocumentChunkModel.document_id == meth_doc.document_id)
        ).all()
        assert len(meth_chunks) == 4

        # Total documents in DB = 1 dummy + 6 fixtures = 7
        assert session.query(DocumentMetadataModel).count() == 7
        assert session.query(DocumentChunkModel).count() == 11

    session.close()

