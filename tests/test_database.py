"""Automated tests for Phase 5 database persistence, ORM models, and services."""

from __future__ import annotations

from datetime import date, datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from public_health_sentinel.db.models import Base
from public_health_sentinel.db.service import (
    get_anomaly_results,
    get_mobility_indicators,
    get_surveillance_observations,
    ingest_mobility_indicators,
    ingest_surveillance_observations,
    persist_anomaly_results,
    record_pipeline_execution,
)
from public_health_sentinel.detection.baseline import DetectionResult, EvaluationStatus
from public_health_sentinel.schemas import AggregatedObservation, DataStatus, MobilityIndicator


@pytest.fixture
def in_memory_db():
    """Fixture providing an isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()

    yield session

    session.close()
    engine.dispose()


class TestDatabaseSurveillancePersistence:
    """Tests for surveillance observation ingestion, query, and null preservation."""

    def test_ingest_surveillance_preserves_nulls(self, in_memory_db: Session):
        """Verify that missing reporting facility counts and denominators remain NULL, not zero."""
        record = AggregatedObservation(
            observation_date=date(2026, 1, 15),
            region_id="REGION_A",
            syndrome="Respiratory",
            report_count=42,
            reporting_facility_count=None,
            population_denominator=None,
            data_source="STATE_DOH",
            data_status=DataStatus.SIMULATED,
        )

        inserted, skipped = ingest_surveillance_observations(in_memory_db, [record])
        in_memory_db.commit()

        assert inserted == 1
        assert skipped == 0

        obs, count = get_surveillance_observations(in_memory_db, region_id="REGION_A")
        assert count == 1
        assert len(obs) == 1
        row = obs[0]
        assert row.report_count == 42
        assert row.reporting_facility_count is None
        assert row.population_denominator is None

    def test_duplicate_surveillance_ingestion_prevents_row_multiplication(self, in_memory_db: Session):
        """Verify that repeated ingestion of identical natural keys does not duplicate rows."""
        record = AggregatedObservation(
            observation_date=date(2026, 1, 15),
            region_id="REGION_A",
            syndrome="Respiratory",
            report_count=20,
            data_source="STATE_DOH",
            data_status=DataStatus.SIMULATED,
        )

        # First ingestion
        ins1, skip1 = ingest_surveillance_observations(in_memory_db, [record])
        in_memory_db.commit()
        assert ins1 == 1

        # Second ingestion with updated count
        updated_record = AggregatedObservation(
            observation_date=date(2026, 1, 15),
            region_id="REGION_A",
            syndrome="Respiratory",
            report_count=25,
            data_source="STATE_DOH",
            data_status=DataStatus.SIMULATED,
        )
        ins2, skip2 = ingest_surveillance_observations(
            in_memory_db, [updated_record], on_conflict="update"
        )
        in_memory_db.commit()
        assert ins2 == 0
        assert skip2 == 1

        # Verify only 1 row exists with updated value
        obs, count = get_surveillance_observations(in_memory_db)
        assert count == 1
        assert obs[0].report_count == 25

    def test_surveillance_filtering_and_pagination(self, in_memory_db: Session):
        """Verify date range, region, syndrome filtering, and pagination limits."""
        records = [
            AggregatedObservation(
                observation_date=date(2026, 1, i),
                region_id="REGION_A" if i % 2 == 0 else "REGION_B",
                syndrome="Respiratory" if i <= 5 else "Febrile",
                report_count=10 + i,
                data_source="STATE_DOH",
                data_status=DataStatus.SIMULATED,
            )
            for i in range(1, 11)
        ]
        ingest_surveillance_observations(in_memory_db, records)
        in_memory_db.commit()

        # Date range filter
        res, count = get_surveillance_observations(
            in_memory_db,
            start_date=date(2026, 1, 3),
            end_date=date(2026, 1, 6),
        )
        assert count == 4
        assert len(res) == 4

        # Region filter
        res_a, count_a = get_surveillance_observations(in_memory_db, region_id="REGION_A")
        assert count_a == 5

        # Pagination
        paged_res, total = get_surveillance_observations(in_memory_db, limit=3, offset=0)
        assert total == 10
        assert len(paged_res) == 3


class TestDatabaseMobilityPersistence:
    """Tests for mobility indicator ingestion and duplicate prevention."""

    def test_ingest_mobility_indicators_and_query(self, in_memory_db: Session):
        """Verify mobility indicators store and retrieve with correct metric values."""
        records = [
            MobilityIndicator(
                observation_date=date(2026, 2, 1),
                region_id="REGION_A",
                mobility_metric="transit_station_pct_change",
                mobility_value=-12.5,
                data_source="MOCK_PROVIDER",
                data_status=DataStatus.SIMULATED,
            ),
            MobilityIndicator(
                observation_date=date(2026, 2, 1),
                region_id="REGION_A",
                mobility_metric="residential_pct_change",
                mobility_value=8.2,
                data_source="MOCK_PROVIDER",
                data_status=DataStatus.SIMULATED,
            ),
        ]
        inserted, _ = ingest_mobility_indicators(in_memory_db, records)
        in_memory_db.commit()
        assert inserted == 2

        # Query by metric
        transit, count = get_mobility_indicators(
            in_memory_db, mobility_metric="transit_station_pct_change"
        )
        assert count == 1
        assert transit[0].mobility_value == -12.5

    def test_duplicate_mobility_skipped(self, in_memory_db: Session):
        """Verify duplicate mobility key is skipped when on_conflict='skip'."""
        mob = MobilityIndicator(
            observation_date=date(2026, 2, 1),
            region_id="REGION_A",
            mobility_metric="workplace_pct_change",
            mobility_value=-5.0,
            data_source="MOCK_PROVIDER",
            data_status=DataStatus.SIMULATED,
        )
        ins1, _ = ingest_mobility_indicators(in_memory_db, [mob])
        ins2, skip2 = ingest_mobility_indicators(in_memory_db, [mob], on_conflict="skip")
        in_memory_db.commit()

        assert ins1 == 1
        assert ins2 == 0
        assert skip2 == 1


class TestDatabaseAnomalyPersistence:
    """Tests for anomaly detection results storage and filtering."""

    def test_persist_anomaly_results_and_filtering(self, in_memory_db: Session):
        """Verify anomaly scores, thresholds, and flags persist and filter accurately."""
        results = [
            DetectionResult(
                observation_date=date(2026, 3, 1),
                region_id="REGION_A",
                syndrome="Respiratory",
                observed_count=50,
                expected_baseline=20.0,
                anomaly_score=3.5,
                detection_threshold=3.0,
                is_anomaly=True,
                detection_method="rolling_mad",
                history_count=14,
                evaluation_status=EvaluationStatus.EVALUATED,
                data_source="TEST_SYSTEM",
                data_status=DataStatus.SIMULATED,
            ),
            DetectionResult(
                observation_date=date(2026, 3, 2),
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
                data_source="TEST_SYSTEM",
                data_status=DataStatus.SIMULATED,
            ),
        ]

        ins, upd = persist_anomaly_results(in_memory_db, results)
        in_memory_db.commit()
        assert ins == 2

        # Filter is_anomaly_only
        anoms, count = get_anomaly_results(in_memory_db, is_anomaly=True)
        assert count == 1
        assert anoms[0].observed_count == 50
        assert anoms[0].anomaly_score == 3.5


class TestDatabasePipelineExecutionLogging:
    """Tests for pipeline execution audit log."""

    def test_record_pipeline_execution(self, in_memory_db: Session):
        """Verify pipeline execution record stores parameters and summaries."""
        now = datetime.now(timezone.utc)
        record = record_pipeline_execution(
            in_memory_db,
            pipeline_type="anomaly_detection",
            status="SUCCESS",
            started_at=now,
            completed_at=now,
            parameters={"method": "rolling_mad", "threshold": 3.0},
            summary={"anomalies_detected": 4},
            records_processed=180,
            anomalies_detected=4,
        )
        in_memory_db.commit()

        assert record.id is not None
        assert record.pipeline_type == "anomaly_detection"
        assert record.status == "SUCCESS"
        assert record.anomalies_detected == 4
        assert "rolling_mad" in record.parameters_json
