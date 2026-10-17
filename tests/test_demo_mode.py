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
from public_health_sentinel.assistant.service import get_assistant
from public_health_sentinel.assistant.schemas import AssistantAskRequest
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
    assert chunk_count == 10

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


def test_lightweight_app_import_and_mobility_analytics_without_matplotlib():
    """Verify that PublicHealthSentinel core and API operate cleanly when matplotlib is absent."""
    import sys
    import pandas as pd
    from public_health_sentinel.mobility.correlation import compute_correlations, compute_descriptive_statistics
    from public_health_sentinel.mobility.lag_analysis import compute_lagged_correlations

    with patch.dict(sys.modules, {"matplotlib": None, "matplotlib.pyplot": None, "matplotlib.dates": None}):
        # 1. API client and app must function
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

        # 2. Mobility analytics must compute properly without matplotlib
        df = pd.DataFrame(
            {
                "observation_date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
                "region_id": ["REGION_A", "REGION_A", "REGION_A", "REGION_A"],
                "syndrome": ["Respiratory", "Respiratory", "Respiratory", "Respiratory"],
                "report_count": [10.0, 15.0, 20.0, 25.0],
                "transit_station_pct_change": [-5.0, -10.0, -12.0, -15.0],
            }
        )
        stats_dict = compute_descriptive_statistics(df, ["transit_station_pct_change"])
        assert "mobility_by_metric" in stats_dict

        corrs = compute_correlations(df, ["transit_station_pct_change"])
        assert len(corrs) == 1

        lags = compute_lagged_correlations(df, "transit_station_pct_change", min_lag=-1, max_lag=1)
        assert len(lags) == 1


def test_figure_generation_requires_matplotlib(tmp_path):
    """Verify that calling plotting functions without matplotlib raises an informative ImportError."""
    import sys
    import pandas as pd
    from public_health_sentinel.mobility.correlation import generate_mobility_figures
    from public_health_sentinel.mobility.lag_analysis import plot_cross_correlation_profile

    df = pd.DataFrame(
        {
            "observation_date": ["2026-01-01", "2026-01-02"],
            "region_id": ["REGION_A", "REGION_A"],
            "syndrome": ["Respiratory", "Respiratory"],
            "report_count": [10.0, 15.0],
            "transit_station_pct_change": [-5.0, -10.0],
        }
    )

    with patch.dict(sys.modules, {"matplotlib": None, "matplotlib.pyplot": None, "matplotlib.dates": None}):
        with pytest.raises(ImportError, match="matplotlib is required for mobility figure generation"):
            generate_mobility_figures(df, ["transit_station_pct_change"], tmp_path)

        with pytest.raises(ImportError, match="matplotlib is required for plotting cross-correlation profiles"):
            plot_cross_correlation_profile([], tmp_path / "test.png")


def test_rolling_mad_retrieval_ranking_and_content_verification(memory_db_session):
    """Verify that theoretical Rolling MAD queries retrieve the methodology protocol as top rank.

    Validates Phase 2 requirements:
    1. Rolling MAD question retrieves methodology document as its top-ranked result.
    2. Top result contains the MAD formula, scaling factor, and outlier-robustness explanation.
    3. The respiratory threshold protocol is not the primary result for theoretical MAD questions.
    4. The respiratory threshold question still retrieves the respiratory protocol.
    5. Queries with genuinely insufficient evidence remain insufficient (< 0.30 cutoff).
    6. Existing evidence citation identifiers and offsets remain valid.
    """
    seed_demo_data_if_needed(memory_db_session)

    with patch.dict(os.environ, {"DEMO_MODE": "true", "EMBEDDING_PROVIDER": "tfidf", "GENERATION_PROVIDER": "demo"}):
        get_config.cache_clear()
        assistant = get_assistant()

        # 1 & 2: Theoretical Rolling MAD query
        mad_request = AssistantAskRequest(
            question="How does Rolling Median Absolute Deviation (MAD) calculate dispersion and handle outliers?",
            min_similarity=0.30,
        )
        mad_resp = assistant.ask(session=memory_db_session, request=mad_request)

        assert mad_resp.evidence_sufficiency in {"SUFFICIENT", "PARTIAL"}
        assert len(mad_resp.retrieved_passages) > 0

        # Requirement 1: Methodology document is top-ranked
        top_passage = mad_resp.retrieved_passages[0]
        assert "Syndromic Surveillance Statistical Anomaly Detection Methodology Protocol" in top_passage.title

        # Requirement 2: Top result contains the MAD formula and outlier-robustness explanation
        assert "raw_mad = median(|X_i - median(X)|)" in top_passage.text
        assert "scale = 1.4826 * raw_mad" in top_passage.text
        assert "50% breakdown point" in top_passage.text
        assert "outlier" in top_passage.text.lower()
        assert "dispersion" in top_passage.text.lower()

        # Requirement 3: Respiratory protocol is NOT the primary result
        assert top_passage.title != "Respiratory Surge Statistical Threshold Protocol"

        # Requirement 4: Respiratory threshold question still retrieves respiratory protocol as primary
        resp_request = AssistantAskRequest(
            question="What is the threshold for respiratory surge alerts in emergency departments?",
            min_similarity=0.30,
        )
        resp_resp = assistant.ask(session=memory_db_session, request=resp_request)
        assert len(resp_resp.retrieved_passages) > 0
        assert resp_resp.retrieved_passages[0].title == "Respiratory Surge Statistical Threshold Protocol"

        # Requirement 5: Queries with genuinely insufficient evidence remain insufficient
        unrelated_request = AssistantAskRequest(
            question="What are the pediatric cardiac catheterization trial inclusion criteria?",
            min_similarity=0.30,
        )
        unrelated_resp = assistant.ask(session=memory_db_session, request=unrelated_request)
        assert unrelated_resp.evidence_sufficiency == "INSUFFICIENT"
        assert len(unrelated_resp.citations) == 0
        assert unrelated_resp.response_type == "insufficient_refusal"

        # Requirement 6: Citation identifiers and offsets remain valid
        assert len(mad_resp.citations) > 0
        for citation in mad_resp.citations:
            assert citation.citation_id.startswith("E")
            assert citation.char_start >= 0
            assert citation.char_end > citation.char_start
            assert len(citation.excerpt) > 0
            assert citation.is_verified is True

        get_config.cache_clear()

