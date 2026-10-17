"""Automated tests for Phase 5 FastAPI service, endpoints, and error handling."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from public_health_sentinel.api.app import app
from public_health_sentinel.db.models import Base
from public_health_sentinel.db.service import (
    ingest_mobility_indicators,
    ingest_surveillance_observations,
    persist_anomaly_results,
)
from public_health_sentinel.db.session import get_db_session
from public_health_sentinel.detection.baseline import DetectionResult, EvaluationStatus
from public_health_sentinel.schemas import AggregatedObservation, DataStatus, MobilityIndicator


@pytest.fixture
def test_db_session():
    """Create an isolated in-memory SQLite database session for API tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()

    # Pre-populate sample test data
    surv_records = [
        AggregatedObservation(
            observation_date=date(2026, 1, i),
            region_id="REGION_A" if i % 2 == 0 else "REGION_B",
            syndrome="Respiratory" if i <= 5 else "Febrile",
            report_count=20 + i,
            reporting_facility_count=4,
            population_denominator=100_000,
            data_source="STATE_DOH",
            data_status=DataStatus.SIMULATED,
        )
        for i in range(1, 11)
    ]
    ingest_surveillance_observations(session, surv_records)

    mob_records = [
        MobilityIndicator(
            observation_date=date(2026, 1, i),
            region_id="REGION_A",
            mobility_metric="transit_station_pct_change",
            mobility_value=-5.0 + float(i),
            data_source="MOCK_PROVIDER",
            data_status=DataStatus.SIMULATED,
        )
        for i in range(1, 6)
    ]
    ingest_mobility_indicators(session, mob_records)

    anom_records = [
        DetectionResult(
            observation_date=date(2026, 1, 5),
            region_id="REGION_A",
            syndrome="Respiratory",
            observed_count=45,
            expected_baseline=20.0,
            anomaly_score=3.8,
            detection_threshold=3.0,
            is_anomaly=True,
            detection_method="rolling_mad",
            history_count=14,
            evaluation_status=EvaluationStatus.EVALUATED,
            data_source="SENTINEL",
            data_status=DataStatus.SIMULATED,
        ),
        DetectionResult(
            observation_date=date(2026, 1, 6),
            region_id="REGION_A",
            syndrome="Respiratory",
            observed_count=21,
            expected_baseline=20.0,
            anomaly_score=0.2,
            detection_threshold=3.0,
            is_anomaly=False,
            detection_method="rolling_mad",
            history_count=15,
            evaluation_status=EvaluationStatus.EVALUATED,
            data_source="SENTINEL",
            data_status=DataStatus.SIMULATED,
        ),
        DetectionResult(
            observation_date=date(2026, 1, 7),
            region_id="REGION_B",
            syndrome="Gastrointestinal",
            observed_count=30,
            expected_baseline=28.0,
            anomaly_score=0.5,
            detection_threshold=3.0,
            is_anomaly=False,
            detection_method="ewma",
            history_count=16,
            evaluation_status=EvaluationStatus.EVALUATED,
            data_source="SENTINEL",
            data_status=DataStatus.SIMULATED,
        ),
    ]
    persist_anomaly_results(session, anom_records)
    session.commit()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def client(test_db_session: Session):
    """FastAPI TestClient with overridden get_db_session dependency."""
    def _override_db_session():
        try:
            yield test_db_session
            test_db_session.commit()
        except Exception:
            test_db_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = _override_db_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestSystemEndpoints:
    """Tests for system health and diagnostics."""

    def test_health_check_healthy(self, client: TestClient):
        """Verify /health returns 200 and healthy status when database is reachable."""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert data["app_name"] == "PublicHealthSentinel"
        assert "timestamp" in data

    def test_health_check_degraded_when_database_down(self, client: TestClient):
        """Verify /health gracefully reports degraded status when connection fails."""
        with patch("public_health_sentinel.api.app.get_engine") as mock_engine:
            mock_engine.side_effect = Exception("Database connection timeout")
            response = client.get("/health")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "degraded"
            assert data["database_connected"] is False


class TestSurveillanceEndpoints:
    """Tests for GET /api/v1/surveillance."""

    def test_list_surveillance_observations_paginated(self, client: TestClient):
        """Verify pagination, crude incidence computation, and synthetic data label."""
        response = client.get("/api/v1/surveillance?page=1&page_size=3")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 10
        assert data["page"] == 1
        assert data["page_size"] == 3
        assert data["total_pages"] == 4
        assert len(data["items"]) == 3
        assert "SYNTHETIC-DATA NOTICE" in data["synthetic_experiment_notice"]

        # Check incidence calculation
        first_item = data["items"][0]
        assert first_item["crude_incidence_per_100k"] is not None

    def test_list_surveillance_filter_by_region_and_syndrome(self, client: TestClient):
        """Verify filtering by geographic jurisdiction and syndrome cluster."""
        response = client.get("/api/v1/surveillance?region_id=REGION_A&syndrome=Respiratory")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for item in data["items"]:
            assert item["region_id"] == "REGION_A"
            assert item["syndrome"] == "Respiratory"

    def test_list_surveillance_invalid_date_range_returns_400(self, client: TestClient):
        """Verify 400 is returned when start_date > end_date."""
        response = client.get("/api/v1/surveillance?start_date=2026-02-01&end_date=2026-01-01")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "must be less than or equal to" in response.json()["message"]


class TestMobilityEndpoints:
    """Tests for GET /api/v1/mobility."""

    def test_list_mobility_indicators_success(self, client: TestClient):
        """Verify mobility query returns paginated items and synthetic notice."""
        response = client.get("/api/v1/mobility?mobility_metric=transit_station_pct_change")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 5
        assert len(data["items"]) == 5
        assert data["items"][0]["mobility_metric"] == "transit_station_pct_change"
        assert "SYNTHETIC-DATA NOTICE" in data["synthetic_experiment_notice"]

    def test_get_mobility_evaluation_success(self, client: TestClient):
        """Verify empirical mobility model comparison evaluation response."""
        response = client.get("/api/v1/mobility/evaluation")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "baseline_model" in data
        assert "augmented_model" in data
        assert data["baseline_model"]["f1_score"] == 0.1864
        assert data["augmented_model"]["f1_score"] == 0.23
        assert data["delta_f1"] == 0.0436
        assert "positive improvement" in data["performance_verdict"]
        assert "SYNTHETIC-DATA EXPERIMENT" in data["synthetic_experiment_notice"]

    def test_get_mobility_evaluation_not_found(self, client: TestClient):
        """Verify 404 response when evaluation report file is absent."""
        with patch("public_health_sentinel.api.v1.routers.mobility._find_mobility_evaluation_path") as mock_path:
            from pathlib import Path
            mock_path.return_value = Path("reports/mobility/non_existent_report.json")
            response = client.get("/api/v1/mobility/evaluation")
            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "has not been generated yet" in response.json()["message"]


class TestAnomalyEndpoints:
    """Tests for GET /api/v1/anomalies."""

    def test_list_anomalies_unfiltered(self, client: TestClient):
        """Verify retrieving persisted anomaly results without optional filters."""
        response = client.get("/api/v1/anomalies")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert "SYNTHETIC-DATA NOTICE" in data["synthetic_experiment_notice"]
        assert "STATISTICAL SURGE ONLY" in data["items"][0]["interpretation_disclaimer"]

    def test_list_anomalies_filtered_by_method(self, client: TestClient):
        """Verify filtering anomaly results by detection method."""
        response_mad = client.get("/api/v1/anomalies?method=rolling_mad")
        assert response_mad.status_code == status.HTTP_200_OK
        data_mad = response_mad.json()
        assert data_mad["total"] == 2
        for item in data_mad["items"]:
            assert item["detection_method"] == "rolling_mad"

        response_ewma = client.get("/api/v1/anomalies?method=ewma")
        assert response_ewma.status_code == status.HTTP_200_OK
        assert response_ewma.json()["total"] == 1
        assert response_ewma.json()["items"][0]["detection_method"] == "ewma"

        response_zscore = client.get("/api/v1/anomalies?method=zscore")
        assert response_zscore.status_code == status.HTTP_200_OK
        assert response_zscore.json()["total"] == 0
        assert response_zscore.json()["items"] == []

    def test_list_anomalies_filtered_by_flag(self, client: TestClient):
        """Verify filtering for confirmed anomalies only."""
        response = client.get("/api/v1/anomalies?is_anomaly=true")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["is_anomaly"] is True
        assert data["items"][0]["observed_count"] == 45
        assert "STATISTICAL SURGE ONLY" in data["items"][0]["interpretation_disclaimer"]

    def test_list_anomalies_filtered_by_status_false(self, client: TestClient):
        """Verify filtering for non-anomalies only (is_anomaly=false)."""
        response = client.get("/api/v1/anomalies?is_anomaly=false")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total"] == 2
        for item in data["items"]:
            assert item["is_anomaly"] is False

    def test_list_anomalies_date_and_region_filtering(self, client: TestClient):
        """Verify filtering by observation date range and geographic region."""
        response = client.get(
            "/api/v1/anomalies?start_date=2026-01-05&end_date=2026-01-05&region_id=REGION_A"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["observation_date"] == "2026-01-05"
        assert data["items"][0]["region_id"] == "REGION_A"

    def test_list_anomalies_pagination_and_total_count_consistency(self, client: TestClient):
        """Verify pagination slicing and total count consistency."""
        response_p1 = client.get("/api/v1/anomalies?page=1&page_size=2")
        assert response_p1.status_code == status.HTTP_200_OK
        data_p1 = response_p1.json()
        assert data_p1["total"] == 3
        assert len(data_p1["items"]) == 2
        assert data_p1["page"] == 1
        assert data_p1["page_size"] == 2
        assert data_p1["total_pages"] == 2

        response_p2 = client.get("/api/v1/anomalies?page=2&page_size=2")
        assert response_p2.status_code == status.HTTP_200_OK
        data_p2 = response_p2.json()
        assert data_p2["total"] == 3
        assert len(data_p2["items"]) == 1
        assert data_p2["page"] == 2

    def test_list_anomalies_empty_result_set(self, client: TestClient):
        """Verify query with non-matching filters returns empty items and total 0."""
        response = client.get(
            "/api/v1/anomalies?start_date=2001-09-09&end_date=2002-05-05&region_id=null&syndrome=yes"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["total_pages"] == 0

    def test_list_anomalies_invalid_method_returns_400(self, client: TestClient):
        """Verify 400 is returned for unknown detection method."""
        response = client.get("/api/v1/anomalies?method=unknown_method")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestPipelineEndpoints:
    """Tests for POST /api/v1/pipeline/detect."""

    def test_execute_detection_pipeline_success(self, client: TestClient):
        """Verify execution of anomaly detection pipeline via API."""
        payload = {
            "method": "rolling_mad",
            "window_size": 7,
            "threshold": 2.5,
            "min_history": 3,
            "persist_results": True,
        }
        response = client.post("/api/v1/pipeline/detect", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "SUCCESS"
        assert "rolling_mad" in data["methods_run"]
        assert data["total_evaluated_observations"] > 0
        assert data["database_records_persisted"] > 0
        assert "execution_id" in data

    def test_execute_detection_pipeline_ewma_success(self, client: TestClient):
        """Verify execution of EWMA detection pipeline via API with valid lambda."""
        payload = {
            "method": "ewma",
            "ewma_lambda": 0.25,
            "threshold": 3.0,
            "min_history": 5,
            "persist_results": False,
        }
        response = client.post("/api/v1/pipeline/detect", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "SUCCESS"
        assert "ewma" in data["methods_run"]
        assert data["total_evaluated_observations"] > 0
        assert "execution_id" in data
        assert "ewma" in data["anomalies_detected_by_method"]

    def test_execute_detection_pipeline_ewma_invalid_lambda_returns_422(self, client: TestClient):
        """Verify 422 is returned when ewma_lambda is outside (0.0, 1.0]."""
        payload = {
            "method": "ewma",
            "ewma_lambda": 0.0,  # gt=0.0 required
            "threshold": 3.0,
        }
        response = client.post("/api/v1/pipeline/detect", json=payload)
        assert response.status_code == 422
        assert response.json()["error"] is True

        payload_high = {
            "method": "ewma",
            "ewma_lambda": 1.5,  # le=1.0 required
            "threshold": 3.0,
        }
        response_high = client.post("/api/v1/pipeline/detect", json=payload_high)
        assert response_high.status_code == 422
        assert response_high.json()["error"] is True

    def test_execute_detection_pipeline_invalid_bounds_returns_422(self, client: TestClient):
        """Verify 422 is returned when parameters violate bounds."""
        payload = {
            "method": "rolling_mad",
            "window_size": 1,  # ge=2 required
            "threshold": -3.0,  # gt=0.0 required
        }
        response = client.post("/api/v1/pipeline/detect", json=payload)
        assert response.status_code == 422
        assert response.json()["error"] is True


class TestErrorSanitization:
    """Tests verifying no stack traces or secrets leak in error responses."""

    def test_unhandled_exception_sanitized(self, client: TestClient):
        """Verify 500 response contains clean error message without stack trace."""
        with patch("public_health_sentinel.api.v1.routers.surveillance.get_surveillance_observations") as mock_srv:
            mock_srv.side_effect = RuntimeError("Sensitive internal database connection failure")
            response = client.get("/api/v1/surveillance")
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            body = response.json()
            assert body["error"] is True
            assert "An internal server error occurred" in body["message"]
            assert "Sensitive internal" not in str(body)
