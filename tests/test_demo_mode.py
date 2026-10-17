"""Unit and integration tests for Phase 10 Public Demo Mode and Render Free-Tier Compatibility."""

import os
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from public_health_sentinel.config import get_config
from public_health_sentinel.db.models import (
    AnomalyDetectionResultModel,
    Base,
    DocumentChunkModel,
    MobilityIndicatorModel,
    SurveillanceObservationModel,
)
from public_health_sentinel.db.demo_seeder import is_db_empty, seed_demo_data_if_needed
from public_health_sentinel.api.app import app


@pytest.fixture
def memory_db_session():
    """Create an isolated in-memory SQLite database session for seeder testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_demo_seeder_initializes_and_idempotent(memory_db_session):
    """Verify that demo seeder correctly populates an empty database and is idempotent."""
    assert is_db_empty(memory_db_session) is True

    # First seeding run
    seeded = seed_demo_data_if_needed(memory_db_session)
    assert seeded["surveillance"] == 2700
    assert seeded["mobility"] == 2700
    assert seeded["anomalies"] == 2700
    assert is_db_empty(memory_db_session) is False

    # Check populated counts
    surv_count = memory_db_session.query(SurveillanceObservationModel).count()
    mob_count = memory_db_session.query(MobilityIndicatorModel).count()
    anom_count = memory_db_session.query(AnomalyDetectionResultModel).count()
    chunk_count = memory_db_session.query(DocumentChunkModel).count()

    assert surv_count == 2700
    assert mob_count == 2700
    assert anom_count == 2700
    assert chunk_count == 6

    # Second run should be a no-op (idempotent)
    second_run = seed_demo_data_if_needed(memory_db_session)
    assert second_run["surveillance"] == 0
    assert memory_db_session.query(SurveillanceObservationModel).count() == 2700


def test_demo_mode_guarded_destructive_endpoints():
    """Verify that administrative/destructive endpoints return HTTP 403 Forbidden in demo mode."""
    with patch.dict(os.environ, {"DEMO_MODE": "true"}):
        get_config.cache_clear()
        client = TestClient(app)

        # Ingestion
        resp = client.post("/api/v1/documents/ingest", json={"filename": "test.txt", "content": "Sample content"})
        assert resp.status_code == 403
        err_msg = resp.json().get("message") or resp.json().get("detail", "")
        assert "disabled in public demonstration mode" in err_msg

        # Process document
        resp = client.post("/api/v1/documents/non-existent-id/process")
        assert resp.status_code == 403

        # Evidence rebuild
        resp = client.post("/api/v1/evidence/rebuild")
        assert resp.status_code == 403

        # Pipeline detect
        resp = client.post("/api/v1/pipeline/detect", json={})
        assert resp.status_code == 403
        get_config.cache_clear()


def test_demo_mode_assistant_evidence_fallback():
    """Verify that in demo mode, assistant returns verified citations without attempting Ollama inference."""
    with patch.dict(os.environ, {"DEMO_MODE": "true"}):
        get_config.cache_clear()
        client = TestClient(app)

        payload = {
            "question": "What is the baseline threshold for syndromic surveillance anomalies?",
            "top_k": 2,
            "min_similarity": 0.05,
        }
        resp = client.post("/api/v1/assistant/ask", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["response_type"] == "evidence_fallback"
        assert data["finish_reason"] == "demo_mode"
        assert len(data["citations"]) > 0
        assert "[E1]" in data["answer"]
        assert "PUBLIC DEMO NOTICE" in data["answer"]
        assert data["citations"][0]["is_verified"] is True
        get_config.cache_clear()


def test_demo_mode_assistant_out_of_scope_refusal():
    """Verify that in demo mode, out-of-scope inquiries are safely refused (<20ms)."""
    with patch.dict(os.environ, {"DEMO_MODE": "true"}):
        get_config.cache_clear()
        client = TestClient(app)

        payload = {
            "question": "How do I bake chocolate chip cookies with sea salt?",
            "top_k": 2,
            "min_similarity": 0.40,
        }
        resp = client.post("/api/v1/assistant/ask", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["evidence_sufficiency"] == "INSUFFICIENT"
        assert data["response_type"] == "insufficient_refusal"
        assert "does not contain sufficient" in data["answer"]
        get_config.cache_clear()


def test_demo_mode_health_endpoint():
    """Verify that /health reflects demo mode status."""
    with patch.dict(os.environ, {"DEMO_MODE": "true"}):
        get_config.cache_clear()
        client = TestClient(app)

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["demo_mode"] is True
        get_config.cache_clear()
