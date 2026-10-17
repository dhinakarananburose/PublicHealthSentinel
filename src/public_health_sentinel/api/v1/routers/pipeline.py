"""Pipeline execution endpoint for anomaly detection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from public_health_sentinel.api.models import (
    RunDetectionRequest,
    RunDetectionResponse,
)
from public_health_sentinel.config import get_config
from public_health_sentinel.db.service import (
    get_surveillance_observations,
    persist_anomaly_results,
    record_pipeline_execution,
)
from public_health_sentinel.db.session import get_db_session
from public_health_sentinel.detection.baseline import BaseAnomalyDetector, DetectionResult
from public_health_sentinel.detection.ewma import EWMADetector
from public_health_sentinel.detection.rolling_mad import RollingMADDetector
from public_health_sentinel.detection.zscore import ZScoreDetector
from public_health_sentinel.loader import load_surveillance_csv

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.post(
    "/detect",
    response_model=RunDetectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger statistical anomaly detection pipeline",
    description=(
        "Executes statistical anomaly detection using historical surveillance observations. "
        "Results can optionally be persisted to the database."
    ),
)
def execute_detection_pipeline(
    request: RunDetectionRequest,
    session: Session = Depends(get_db_session),
) -> RunDetectionResponse:
    """Execute statistical anomaly detection pipeline with validated parameters."""
    config = get_config()
    if config.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analytical pipeline execution is disabled in public demonstration mode to protect benchmark data integrity.",
        )

    start_time = datetime.now(timezone.utc)
    exec_id = f"api-exec-{uuid.uuid4().hex[:12]}"

    # Step 1: Source surveillance data from DB; fall back to processed CSV if DB empty
    db_obs, total_db = get_surveillance_observations(session, limit=100000)
    if total_db > 0:
        rows = [
            {
                "observation_date": r.observation_date,
                "region_id": r.region_id,
                "syndrome": r.syndrome,
                "report_count": r.report_count,
                "reporting_facility_count": r.reporting_facility_count,
                "population_denominator": r.population_denominator,
                "data_source": r.data_source,
                "data_status": r.data_status,
            }
            for r in db_obs
        ]
        df = pd.DataFrame(rows)
    else:
        # Fallback to local processed surveillance CSV
        default_csv = config.data_processed_dir / "surveillance_observations.csv"
        if not default_csv.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No surveillance records found in database or processed storage. Run ingestion pipeline first.",
            )
        try:
            df = load_surveillance_csv(default_csv)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to load surveillance observations: {exc}",
            )

    if df.empty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Surveillance dataset is empty. Cannot perform detection.",
        )

    # Step 2: Configure detectors
    detectors: list[BaseAnomalyDetector] = []
    try:
        if request.method in ("rolling_mad", "all"):
            detectors.append(
                RollingMADDetector(
                    window_size=request.window_size,
                    threshold=request.threshold,
                    min_history=request.min_history,
                )
            )
        if request.method in ("ewma", "all"):
            detectors.append(
                EWMADetector(
                    lambda_=request.ewma_lambda,
                    threshold=request.threshold,
                    min_history=request.min_history,
                )
            )
        if request.method in ("zscore", "all"):
            detectors.append(
                ZScoreDetector(
                    window_size=request.window_size,
                    threshold=request.threshold,
                    min_history=request.min_history,
                )
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid detector parameters: {exc}",
        )

    # Step 3: Run detection
    all_results: list[DetectionResult] = []
    anomalies_by_method: dict[str, int] = {}
    methods_run: list[str] = [d.name for d in detectors]

    for detector in detectors:
        res = detector.detect(df)
        all_results.extend(res)
        anomalies_by_method[detector.name] = sum(1 for r in res if r.is_anomaly is True)

    total_evaluated = len(df)
    total_anomalies = sum(anomalies_by_method.values())

    # Step 4: Optional database persistence
    persisted_count = 0
    if request.persist_results:
        ins, upd = persist_anomaly_results(session, all_results, on_conflict="update")
        persisted_count = ins + upd

    # Step 5: Audit log
    end_time = datetime.now(timezone.utc)
    record_pipeline_execution(
        session=session,
        pipeline_type="api_anomaly_detection",
        status="SUCCESS",
        started_at=start_time,
        completed_at=end_time,
        parameters=request.model_dump(),
        summary={
            "methods_run": methods_run,
            "total_evaluated": total_evaluated,
            "anomalies_by_method": anomalies_by_method,
            "database_records_persisted": persisted_count,
        },
        records_processed=total_evaluated,
        anomalies_detected=total_anomalies,
        execution_id=exec_id,
    )

    return RunDetectionResponse(
        execution_id=exec_id,
        status="SUCCESS",
        methods_run=methods_run,
        total_evaluated_observations=total_evaluated,
        anomalies_detected_by_method=anomalies_by_method,
        database_records_persisted=persisted_count,
    )
