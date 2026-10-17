"""FastAPI endpoint integration tests for Phase 6C Evidence-Grounded Assistant."""

import json
from pathlib import Path
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from public_health_sentinel.api.app import app
from public_health_sentinel.db.models import Base, DocumentChunkModel
from public_health_sentinel.db.session import get_db_session
from public_health_sentinel.documents.embeddings import DeterministicMockEmbeddingService
from public_health_sentinel.documents.index import VectorIndexManager
from public_health_sentinel.documents.retrieval import SemanticRetrievalService
from public_health_sentinel.assistant.provider import (
    MockAnswerGenerationProvider,
    ProviderUnavailableError,
    set_generation_provider,
)
from public_health_sentinel.assistant.service import EvidenceGroundedAssistant


@pytest.fixture
def test_db_session() -> Session:
    """Isolated in-memory database session."""
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
def client(test_db_session: Session, tmp_path: Path):
    """TestClient wired with in-memory DB, temporary vector index, and mock provider."""
    app.dependency_overrides[get_db_session] = lambda: test_db_session

    mock_svc = DeterministicMockEmbeddingService(model_name="mock-minilm-v1", expected_dim=384)
    idx_dir = tmp_path / "api_test_index"
    index_mgr = VectorIndexManager(index_dir=idx_dir, expected_dim=384, model_name=mock_svc.model_name)

    # Ingest a sample passage
    text = "Statistical surge alerts trigger when counts exceed baseline plus 2.5 times the median absolute deviation."
    vec = mock_svc.embed_text(text)
    chunk = DocumentChunkModel(
        chunk_id="chunk-api-01",
        document_id="doc-api-01",
        sequence_number=0,
        text=text,
        char_start=0,
        char_end=len(text),
        title="Surveillance Protocol API Test",
        source_publisher="Test Publisher",
        content_hash="hash-api-01",
        embedding_json=json.dumps(vec.tolist()),
        embedding_model=mock_svc.model_name,
    )
    test_db_session.add(chunk)
    test_db_session.commit()
    index_mgr.add_chunks([("chunk-api-01", "doc-api-01", vec)], model_name=mock_svc.model_name)

    mock_provider = MockAnswerGenerationProvider(model_name="mock-llama3.2")
    retrieval_svc = SemanticRetrievalService(vector_index=index_mgr, embedding_service=mock_svc)
    assistant = EvidenceGroundedAssistant(
        retrieval_service=retrieval_svc,
        generation_provider=mock_provider,
    )

    import public_health_sentinel.assistant.service as asst_mod
    import public_health_sentinel.documents.index as idx_mod
    original_assistant = asst_mod._global_assistant
    original_index = idx_mod._global_index

    asst_mod._global_assistant = assistant
    idx_mod._global_index = index_mgr
    set_generation_provider(mock_provider)

    with TestClient(app) as test_client:
        yield test_client, mock_provider

    asst_mod._global_assistant = original_assistant
    idx_mod._global_index = original_index
    set_generation_provider(None)
    app.dependency_overrides.clear()


def test_assistant_ask_endpoint_success(client):
    """Verify POST /api/v1/assistant/ask generates grounded response with citations."""
    test_client, mock_provider = client

    query_text = "Statistical surge alerts trigger when counts exceed baseline plus 2.5 times the median absolute deviation."
    payload = {
        "question": query_text,
        "top_k": 3,
        "min_similarity": 0.20,
    }
    resp = test_client.post("/api/v1/assistant/ask", json=payload)
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert data["question"] == payload["question"]
    assert "answer" in data
    assert data["evidence_sufficiency"] in ("SUFFICIENT", "PARTIAL")
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["citation_id"] == "E1"
    assert "2.5 times the median absolute deviation" in data["citations"][0]["excerpt"]
    assert "SYNTHETIC-DATA NOTICE" in data["synthetic_data_notice"]


def test_assistant_ask_endpoint_empty_inquiry_returns_400(client):
    """Verify POST /api/v1/assistant/ask rejects empty questions with 400 Bad Request."""
    test_client, _ = client

    payload = {"question": "   ", "top_k": 3}
    resp = test_client.post("/api/v1/assistant/ask", json=payload)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_assistant_ask_endpoint_provider_unavailable_returns_503(client):
    """Verify POST /api/v1/assistant/ask returns 503 when the generation provider is unavailable."""
    test_client, mock_provider = client

    mock_provider.set_failure(ProviderUnavailableError("Ollama daemon unreachable"))

    query_text = "Statistical surge alerts trigger when counts exceed baseline plus 2.5 times the median absolute deviation."
    payload = {
        "question": query_text,
        "min_similarity": 0.10,
    }
    resp = test_client.post("/api/v1/assistant/ask", json=payload)
    assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    err_body = resp.json()
    assert "Ollama daemon unreachable" in (err_body.get("message") or err_body.get("detail", ""))

    mock_provider.clear_failure()


def test_assistant_status_endpoint(client):
    """Verify GET /api/v1/assistant/status returns provider readiness and index status."""
    test_client, mock_provider = client

    resp = test_client.get("/api/v1/assistant/status")
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert data["status"] == "READY"
    assert data["provider"] == "mock"
    assert data["provider_healthy"] is True
    assert data["indexed_passages_count"] >= 1

    # Simulate provider failure
    mock_provider.set_failure(ProviderUnavailableError("Offline"))
    resp2 = test_client.get("/api/v1/assistant/status")
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["status"] == "PROVIDER_UNAVAILABLE"
    assert resp2.json()["provider_healthy"] is False

    mock_provider.clear_failure()


def test_assistant_ask_endpoint_concise_mode(client):
    """Verify POST /api/v1/assistant/ask supports concise response mode with appropriate token budget."""
    test_client, mock_provider = client

    query_text = "Statistical surge alerts trigger when counts exceed baseline plus 2.5 times the median absolute deviation."
    payload = {
        "question": query_text,
        "mode": "concise",
        "min_similarity": 0.20,
    }
    resp = test_client.post("/api/v1/assistant/ask", json=payload)
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert data["response_mode"] == "concise"
    assert data["response_type"] == "synthesized"
    # Check that concise num_predict (20) was passed to the provider
    assert len(mock_provider.call_history) >= 1
    last_call = mock_provider.call_history[-1]
    assert last_call["kwargs"].get("num_predict") == 20


def test_assistant_ask_endpoint_timeout_fallback_enabled(client):
    """Verify POST /api/v1/assistant/ask returns evidence-first fallback when LLM times out."""
    from public_health_sentinel.assistant.provider import ProviderTimeoutError
    test_client, mock_provider = client

    mock_provider.set_failure(ProviderTimeoutError("Ollama generation timed out after 90.0s"))

    query_text = "Statistical surge alerts trigger when counts exceed baseline plus 2.5 times the median absolute deviation."
    payload = {
        "question": query_text,
        "fallback_on_timeout": True,
        "min_similarity": 0.20,
    }
    resp = test_client.post("/api/v1/assistant/ask", json=payload)
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert data["response_type"] == "evidence_fallback"
    assert data["finish_reason"] == "timeout_fallback"
    assert "LLM answer synthesis timed out" in data["answer"]
    assert "authoritative guidance directly from published surveillance protocols" in data["answer"]
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["citation_id"] == "E1"
    assert data["citations"][0]["is_verified"] is True
    assert len(data["retrieved_passages"]) >= 1
    assert data["warning"] is not None

    mock_provider.clear_failure()


def test_assistant_ask_endpoint_timeout_fallback_disabled_returns_504(client):
    """Verify POST /api/v1/assistant/ask returns 504 Gateway Timeout when fallback is explicitly disabled."""
    from public_health_sentinel.assistant.provider import ProviderTimeoutError
    test_client, mock_provider = client

    mock_provider.set_failure(ProviderTimeoutError("Ollama generation timed out after 90.0s"))

    query_text = "Statistical surge alerts trigger when counts exceed baseline plus 2.5 times the median absolute deviation."
    payload = {
        "question": query_text,
        "fallback_on_timeout": False,
        "min_similarity": 0.20,
    }
    resp = test_client.post("/api/v1/assistant/ask", json=payload)
    assert resp.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    err_body = resp.json()
    assert "timed out" in (err_body.get("message") or err_body.get("detail", ""))

    mock_provider.clear_failure()


def test_assistant_ask_endpoint_backward_compatibility(client):
    """Verify existing API payload with only question succeeds with default detailed mode and fallback."""
    test_client, _ = client

    query_text = "Statistical surge alerts trigger when counts exceed baseline plus 2.5 times the median absolute deviation."
    payload = {"question": query_text}
    resp = test_client.post("/api/v1/assistant/ask", json=payload)
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert data["response_mode"] == "detailed"
    assert data["response_type"] == "synthesized"
    assert data["finish_reason"] == "stop"

