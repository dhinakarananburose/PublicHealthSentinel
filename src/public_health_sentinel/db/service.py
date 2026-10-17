"""Persistence services for PublicHealthSentinel relational operations.

Encapsulates all database queries and transactions:
- Ingesting validated surveillance observations with duplicate prevention
- Ingesting validated mobility indicators with duplicate prevention
- Querying surveillance observations with filtering and pagination
- Querying mobility indicators with filtering and pagination
- Persisting and querying anomaly detection outputs
- Logging pipeline execution status and summary metrics

Enforces:
- Preserving missing values as NULL (never coercing to 0)
- Zero Cartesian row multiplication on repeated ingestion
- Separation of concerns: pure business logic; no FastAPI coupling
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from public_health_sentinel.db.models import (
    AnomalyDetectionResultModel,
    MobilityIndicatorModel,
    PipelineExecutionModel,
    SurveillanceObservationModel,
)
from public_health_sentinel.detection.baseline import DetectionResult
from public_health_sentinel.schemas import AggregatedObservation, MobilityIndicator


def ingest_surveillance_observations(
    session: Session,
    records: Sequence[AggregatedObservation | dict[str, Any]],
    on_conflict: str = "skip",
) -> tuple[int, int]:
    """Persist surveillance observations into the database.

    Args:
        session: Active SQLAlchemy session.
        records: Collection of AggregatedObservation schemas or dictionaries.
        on_conflict: Conflict strategy ('skip' to ignore duplicates, 'update' to refresh).

    Returns:
        Tuple of (inserted_count, updated_or_skipped_count).
    """
    if not records:
        return 0, 0

    # Ensure Pydantic validation
    validated_records: list[AggregatedObservation] = []
    for r in records:
        if isinstance(r, AggregatedObservation):
            validated_records.append(r)
        else:
            validated_records.append(AggregatedObservation.model_validate(r))

    inserted = 0
    updated_or_skipped = 0

    for r in validated_records:
        stmt = select(SurveillanceObservationModel).where(
            SurveillanceObservationModel.observation_date == r.observation_date,
            SurveillanceObservationModel.region_id == r.region_id,
            SurveillanceObservationModel.syndrome == r.syndrome,
        )
        existing = session.execute(stmt).scalar_one_or_none()

        if existing is not None:
            if on_conflict == "update":
                existing.report_count = r.report_count
                existing.reporting_facility_count = r.reporting_facility_count
                existing.population_denominator = r.population_denominator
                existing.data_source = r.data_source
                existing.data_status = r.data_status.value
                existing.ingestion_timestamp = r.ingestion_timestamp
            updated_or_skipped += 1
        else:
            model = SurveillanceObservationModel(
                observation_date=r.observation_date,
                region_id=r.region_id,
                syndrome=r.syndrome,
                report_count=r.report_count,
                reporting_facility_count=r.reporting_facility_count,
                population_denominator=r.population_denominator,
                data_source=r.data_source,
                data_status=r.data_status.value,
                ingestion_timestamp=r.ingestion_timestamp,
            )
            session.add(model)
            inserted += 1

    session.flush()
    return inserted, updated_or_skipped


def ingest_mobility_indicators(
    session: Session,
    records: Sequence[MobilityIndicator | dict[str, Any]],
    on_conflict: str = "skip",
) -> tuple[int, int]:
    """Persist mobility indicators into the database.

    Args:
        session: Active SQLAlchemy session.
        records: Collection of MobilityIndicator schemas or dictionaries.
        on_conflict: Conflict strategy ('skip' to ignore duplicates, 'update' to refresh).

    Returns:
        Tuple of (inserted_count, updated_or_skipped_count).
    """
    if not records:
        return 0, 0

    validated_records: list[MobilityIndicator] = []
    for r in records:
        if isinstance(r, MobilityIndicator):
            validated_records.append(r)
        else:
            validated_records.append(MobilityIndicator.model_validate(r))

    inserted = 0
    updated_or_skipped = 0

    for r in validated_records:
        stmt = select(MobilityIndicatorModel).where(
            MobilityIndicatorModel.observation_date == r.observation_date,
            MobilityIndicatorModel.region_id == r.region_id,
            MobilityIndicatorModel.mobility_metric == r.mobility_metric,
        )
        existing = session.execute(stmt).scalar_one_or_none()

        if existing is not None:
            if on_conflict == "update":
                existing.mobility_value = r.mobility_value
                existing.data_source = r.data_source
                existing.data_status = r.data_status.value
                existing.ingestion_timestamp = r.ingestion_timestamp
            updated_or_skipped += 1
        else:
            model = MobilityIndicatorModel(
                observation_date=r.observation_date,
                region_id=r.region_id,
                mobility_metric=r.mobility_metric,
                mobility_value=r.mobility_value,
                data_source=r.data_source,
                data_status=r.data_status.value,
                ingestion_timestamp=r.ingestion_timestamp,
            )
            session.add(model)
            inserted += 1

    session.flush()
    return inserted, updated_or_skipped


def get_surveillance_observations(
    session: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    region_id: Optional[str] = None,
    syndrome: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[SurveillanceObservationModel], int]:
    """Retrieve filtered surveillance observations with total matching count."""
    query = select(SurveillanceObservationModel)

    if start_date is not None:
        query = query.where(SurveillanceObservationModel.observation_date >= start_date)
    if end_date is not None:
        query = query.where(SurveillanceObservationModel.observation_date <= end_date)
    if region_id is not None:
        query = query.where(SurveillanceObservationModel.region_id == region_id)
    if syndrome is not None:
        query = query.where(SurveillanceObservationModel.syndrome == syndrome)

    # Count query
    count_stmt = select(func.count()).select_from(query.subquery())
    total_count = session.execute(count_stmt).scalar() or 0

    # Paginated results ordered chronologically
    paged_stmt = (
        query.order_by(
            SurveillanceObservationModel.observation_date.asc(),
            SurveillanceObservationModel.region_id.asc(),
            SurveillanceObservationModel.syndrome.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    records = list(session.execute(paged_stmt).scalars().all())
    return records, total_count


def get_mobility_indicators(
    session: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    region_id: Optional[str] = None,
    mobility_metric: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[MobilityIndicatorModel], int]:
    """Retrieve filtered mobility indicators with total matching count."""
    query = select(MobilityIndicatorModel)

    if start_date is not None:
        query = query.where(MobilityIndicatorModel.observation_date >= start_date)
    if end_date is not None:
        query = query.where(MobilityIndicatorModel.observation_date <= end_date)
    if region_id is not None:
        query = query.where(MobilityIndicatorModel.region_id == region_id)
    if mobility_metric is not None:
        query = query.where(MobilityIndicatorModel.mobility_metric == mobility_metric)

    count_stmt = select(func.count()).select_from(query.subquery())
    total_count = session.execute(count_stmt).scalar() or 0

    paged_stmt = (
        query.order_by(
            MobilityIndicatorModel.observation_date.asc(),
            MobilityIndicatorModel.region_id.asc(),
            MobilityIndicatorModel.mobility_metric.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    records = list(session.execute(paged_stmt).scalars().all())
    return records, total_count


def persist_anomaly_results(
    session: Session,
    results: Sequence[DetectionResult | dict[str, Any]],
    on_conflict: str = "update",
) -> tuple[int, int]:
    """Persist anomaly detection results into the database."""
    if not results:
        return 0, 0

    validated_results: list[DetectionResult] = []
    for res in results:
        if isinstance(res, DetectionResult):
            validated_results.append(res)
        else:
            validated_results.append(DetectionResult.model_validate(res))

    inserted = 0
    updated_or_skipped = 0

    for r in validated_results:
        stmt = select(AnomalyDetectionResultModel).where(
            AnomalyDetectionResultModel.observation_date == r.observation_date,
            AnomalyDetectionResultModel.region_id == r.region_id,
            AnomalyDetectionResultModel.syndrome == r.syndrome,
            AnomalyDetectionResultModel.detection_method == r.detection_method,
        )
        existing = session.execute(stmt).scalar_one_or_none()

        if existing is not None:
            if on_conflict == "update":
                existing.observed_count = r.observed_count
                existing.expected_baseline = r.expected_baseline
                existing.anomaly_score = r.anomaly_score
                existing.detection_threshold = r.detection_threshold
                existing.is_anomaly = r.is_anomaly
                existing.history_count = r.history_count
                existing.evaluation_status = (
                    r.evaluation_status.value
                    if hasattr(r.evaluation_status, "value")
                    else str(r.evaluation_status)
                )
                existing.data_source = r.data_source
                existing.data_status = (
                    r.data_status.value
                    if hasattr(r.data_status, "value")
                    else str(r.data_status)
                )
            updated_or_skipped += 1
        else:
            model = AnomalyDetectionResultModel(
                observation_date=r.observation_date,
                region_id=r.region_id,
                syndrome=r.syndrome,
                detection_method=r.detection_method,
                observed_count=r.observed_count,
                expected_baseline=r.expected_baseline,
                anomaly_score=r.anomaly_score,
                detection_threshold=r.detection_threshold,
                is_anomaly=r.is_anomaly,
                history_count=r.history_count,
                evaluation_status=(
                    r.evaluation_status.value
                    if hasattr(r.evaluation_status, "value")
                    else str(r.evaluation_status)
                ),
                data_source=r.data_source,
                data_status=(
                    r.data_status.value
                    if hasattr(r.data_status, "value")
                    else str(r.data_status)
                ),
            )
            session.add(model)
            inserted += 1

    session.flush()
    return inserted, updated_or_skipped


def get_anomaly_results(
    session: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    region_id: Optional[str] = None,
    syndrome: Optional[str] = None,
    detection_method: Optional[str] = None,
    is_anomaly: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AnomalyDetectionResultModel], int]:
    """Retrieve filtered anomaly detection results with total matching count."""
    query = select(AnomalyDetectionResultModel)

    if start_date is not None:
        query = query.where(AnomalyDetectionResultModel.observation_date >= start_date)
    if end_date is not None:
        query = query.where(AnomalyDetectionResultModel.observation_date <= end_date)
    if region_id is not None:
        query = query.where(AnomalyDetectionResultModel.region_id == region_id)
    if syndrome is not None:
        query = query.where(AnomalyDetectionResultModel.syndrome == syndrome)
    if detection_method is not None:
        query = query.where(AnomalyDetectionResultModel.detection_method == detection_method)
    if is_anomaly is not None:
        query = query.where(AnomalyDetectionResultModel.is_anomaly == is_anomaly)

    count_stmt = select(func.count()).select_from(query.subquery())
    total_count = session.execute(count_stmt).scalar() or 0

    paged_stmt = (
        query.order_by(
            AnomalyDetectionResultModel.observation_date.desc(),
            AnomalyDetectionResultModel.region_id.asc(),
            AnomalyDetectionResultModel.syndrome.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    records = list(session.execute(paged_stmt).scalars().all())
    return records, total_count


def record_pipeline_execution(
    session: Session,
    pipeline_type: str,
    status: str,
    started_at: datetime,
    completed_at: Optional[datetime] = None,
    parameters: Optional[dict[str, Any]] = None,
    summary: Optional[dict[str, Any]] = None,
    records_processed: int = 0,
    anomalies_detected: Optional[int] = None,
    error_message: Optional[str] = None,
    execution_id: Optional[str] = None,
) -> PipelineExecutionModel:
    """Record or update a pipeline execution audit log."""
    exec_id = execution_id or f"exec-{uuid.uuid4().hex[:12]}"

    model = PipelineExecutionModel(
        execution_id=exec_id,
        pipeline_type=pipeline_type,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        parameters_json=json.dumps(parameters, default=str) if parameters else None,
        summary_json=json.dumps(summary, default=str) if summary else None,
        records_processed=records_processed,
        anomalies_detected=anomalies_detected,
        error_message=error_message,
    )
    session.add(model)
    session.flush()
    return model
