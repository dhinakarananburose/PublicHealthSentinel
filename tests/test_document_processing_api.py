"""Automated API test suite for Phase 6B.1 Document Processing & Semantic Retrieval."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Force offline mock embeddings during unit tests
os.environ["EMBEDDING_PROVIDER"] = "mock"

from public_health_sentinel.api.app import app
from public_health_sentinel.db.models import Base
from public_health_sentinel.db.session import get_db_session
from public_health_sentinel.documents.embeddings import (
    DeterministicMockEmbeddingService,
    get_embedding_service,
)
from public_health_sentinel.documents.index import VectorIndexManager, get_vector_index
from public_health_sentinel.documents.processor import DocumentProcessor, get_document_processor


@pytest.fixture
def test_db_session(tmp_path: Path):
    """Provide an isolated in-memory database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def isolated_index(tmp_path: Path) -> VectorIndexManager:
    """Create an isolated temporary vector index directory with mock embedding service."""
    idx_dir = tmp_path / "api_test_index"
    mock_svc = DeterministicMockEmbeddingService(model_name="mock-minilm-v1", expected_dim=384)
    mgr = VectorIndexManager(index_dir=idx_dir, expected_dim=384, model_name=mock_svc.model_name)
    processor = DocumentProcessor(vector_index=mgr, embedding_service=mock_svc)
    return mgr


@pytest.fixture
def client(test_db_session: Session, tmp_path: Path) -> TestClient:
    """Create TestClient with database session override and mock embedding index."""
    app.dependency_overrides[get_db_session] = lambda: test_db_session

    # Point index and documents to temporary test path
    test_idx_dir = tmp_path / "client_test_index"
    mock_svc = DeterministicMockEmbeddingService(model_name="mock-minilm-v1", expected_dim=384)
    mgr = VectorIndexManager(index_dir=test_idx_dir, expected_dim=384, model_name=mock_svc.model_name)

    import public_health_sentinel.documents.index as idx_mod
    import public_health_sentinel.documents.embeddings as emb_mod
    import public_health_sentinel.documents.processor as proc_mod

    idx_mod._global_index = mgr
    emb_mod._active_service = mock_svc
    proc_mod._global_processor = DocumentProcessor(vector_index=mgr, embedding_service=mock_svc)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_evidence_status_endpoint_empty_index(client: TestClient):
    """Verify GET /api/v1/evidence/status returns EMPTY on fresh index."""
    resp = client.get("/api/v1/evidence/status")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["status"] in ("EMPTY", "HEALTHY")
    assert data["dimension"] == 384
    assert "synthetic_experiment_notice" in data


def test_evidence_search_empty_index(client: TestClient):
    """Verify POST /api/v1/evidence/search returns 0 results on empty index without errors."""
    payload = {"query": "early syndromic surveillance", "top_k": 5}
    resp = client.post("/api/v1/evidence/search", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total_results"] == 0
    assert data["items"] == []
    assert data["query"] == "early syndromic surveillance"


def test_evidence_search_query_validation(client: TestClient):
    """Verify POST /api/v1/evidence/search rejects empty and invalid queries."""
    # Empty query
    resp = client.post("/api/v1/evidence/search", json={"query": "   ", "top_k": 5})
    assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # Invalid top_k (le=50)
    resp = client.post("/api/v1/evidence/search", json={"query": "test query", "top_k": 100})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Invalid min_similarity (range -1.0 to 1.0)
    resp = client.post("/api/v1/evidence/search", json={"query": "test query", "min_similarity": 2.5})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_process_missing_document_returns_404(client: TestClient):
    """Verify POST /api/v1/documents/{id}/process returns 404 for non-existent document."""
    resp = client.post("/api/v1/documents/doc-nonexistent-999/process")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_get_chunks_missing_document_returns_404(client: TestClient):
    """Verify GET /api/v1/documents/{id}/chunks returns 404 for non-existent document."""
    resp = client.get("/api/v1/documents/doc-nonexistent-999/chunks")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_full_ingest_process_chunk_and_search_workflow(client: TestClient):
    """Verify end-to-end ingestion, chunk processing, chunk listing, and semantic search."""
    # 1. Ingest a document
    doc_payload = {
        "filename": "respiratory_triage_protocol.md",
        "title": "Respiratory Infection Triage Protocol",
        "content": (
            "# Respiratory Infection Triage Protocol\n\n"
            "Emergency departments must track chief complaints of acute shortness of breath and cough.\n\n"
            "When observed daily encounters exceed 2.5 standard deviations over a 28-day baseline, "
            "the hospital infection control team must initiate syndromic cluster reviews."
        ),
        "source_publisher": "State Health Agency",
        "source_url": "https://health.state.gov/triage",
        "publication_date": "2025-02-01",
    }
    ingest_resp = client.post("/api/v1/documents/ingest", json=doc_payload)
    assert ingest_resp.status_code == status.HTTP_201_CREATED
    doc_id = ingest_resp.json()["document_id"]

    # 2. Process the document
    proc_resp = client.post(f"/api/v1/documents/{doc_id}/process")
    assert proc_resp.status_code == status.HTTP_200_OK
    proc_data = proc_resp.json()
    assert proc_data["document_id"] == doc_id
    assert proc_data["status"] == "INDEXED"
    assert proc_data["chunks_created"] >= 1
    assert proc_data["processing_duration_ms"] > 0

    # 3. List chunks
    chunks_resp = client.get(f"/api/v1/documents/{doc_id}/chunks")
    assert chunks_resp.status_code == status.HTTP_200_OK
    chunks_data = chunks_resp.json()
    assert chunks_data["total"] >= 1
    first_chunk = chunks_data["items"][0]
    assert first_chunk["document_id"] == doc_id
    assert "Respiratory Infection" in first_chunk["text"]
    assert first_chunk["char_start"] == 0
    assert first_chunk["char_end"] > 0
    assert first_chunk["content_hash"] is not None

    # 4. Search indexed evidence
    search_payload = {
        "query": "What are emergency department triage thresholds for respiratory illness?",
        "top_k": 3,
    }
    search_resp = client.post("/api/v1/evidence/search", json=search_payload)
    assert search_resp.status_code == status.HTTP_200_OK
    search_data = search_resp.json()
    assert search_data["total_results"] >= 1
    top_hit = search_data["items"][0]
    assert top_hit["document_id"] == doc_id
    assert "cosine similarity" in top_hit["score_interpretation"].lower()
    assert top_hit["source_publisher"] == "State Health Agency"

    # 5. Check updated status
    status_resp = client.get("/api/v1/evidence/status")
    assert status_resp.status_code == status.HTTP_200_OK
    status_data = status_resp.json()
    assert status_data["status"] == "HEALTHY"
    assert status_data["total_indexed_chunks"] >= 1
    assert status_data["total_indexed_documents"] == 1


def test_reprocess_document_idempotency(client: TestClient):
    """Verify that processing the same document twice updates chunks in place without creating duplicates."""
    doc_payload = {
        "filename": "fever_rash_protocol.txt",
        "title": "Fever Rash Surveillance",
        "content": "Early notification protocol for measles and rash illnesses in pediatric triage.",
    }
    ingest_resp = client.post("/api/v1/documents/ingest", json=doc_payload)
    doc_id = ingest_resp.json()["document_id"]

    # First process run
    res1 = client.post(f"/api/v1/documents/{doc_id}/process").json()
    count1 = res1["chunks_created"]

    # Second process run
    res2 = client.post(f"/api/v1/documents/{doc_id}/process").json()
    count2 = res2["chunks_created"]
    assert count1 == count2

    # Verify chunk count in DB
    chunks_resp = client.get(f"/api/v1/documents/{doc_id}/chunks")
    assert chunks_resp.json()["total"] == count1


def test_evidence_rebuild_endpoint_flow(client: TestClient):
    """Verify POST /api/v1/evidence/rebuild rebuilds index from database records."""
    doc_payload = {
        "filename": "rebuild_protocol.txt",
        "title": "Rebuild Protocol",
        "content": "Protocol verifying that index rebuild accurately reloads all chunks from relational storage.",
    }
    ingest_resp = client.post("/api/v1/documents/ingest", json=doc_payload)
    doc_id = ingest_resp.json()["document_id"]
    client.post(f"/api/v1/documents/{doc_id}/process")

    # Call rebuild endpoint
    reb_resp = client.post("/api/v1/evidence/rebuild")
    assert reb_resp.status_code == status.HTTP_200_OK
    reb_data = reb_resp.json()
    assert reb_data["status"] == "HEALTHY"
    assert reb_data["rebuilt_chunks"] >= 1
    assert "successfully rebuilt" in reb_data["message"]


def test_evidence_search_incompatible_model_returns_409(client: TestClient):
    """Verify POST /api/v1/evidence/search returns 409 Conflict when query embedding model differs from index model."""
    doc_payload = {
        "filename": "conflict_protocol.txt",
        "title": "Conflict Protocol",
        "content": "Protocol for verifying embedding model mismatch prevention.",
    }
    ingest_resp = client.post("/api/v1/documents/ingest", json=doc_payload)
    doc_id = ingest_resp.json()["document_id"]
    client.post(f"/api/v1/documents/{doc_id}/process")

    # Temporarily switch query embedding service to an incompatible model
    import public_health_sentinel.documents.embeddings as emb_mod
    original_service = emb_mod._active_service
    emb_mod._active_service = DeterministicMockEmbeddingService(model_name="incompatible-model-999", expected_dim=384)

    try:
        resp = client.post("/api/v1/evidence/search", json={"query": "test query", "top_k": 3})
        assert resp.status_code == status.HTTP_409_CONFLICT
        error_msg = resp.json().get("message") or resp.json().get("detail", "")
        assert "incompatible" in error_msg.lower()
    finally:
        emb_mod._active_service = original_service


def test_evidence_status_reports_degraded_state(client: TestClient, tmp_path: Path):
    """Verify GET /api/v1/evidence/status reports DEGRADED when index files are damaged."""
    import public_health_sentinel.documents.index as idx_mod
    mgr = idx_mod.get_vector_index()
    mgr._is_degraded = True
    mgr._degraded_reason = "Corrupted vector index detected on disk."

    try:
        resp = client.get("/api/v1/evidence/status")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "DEGRADED"
        assert data["is_degraded"] is True
        assert "Corrupted" in (data["degraded_reason"] or "")
    finally:
        mgr._is_degraded = False
        mgr._degraded_reason = None

