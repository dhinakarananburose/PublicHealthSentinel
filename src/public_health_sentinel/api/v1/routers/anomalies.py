"""Anomaly detection query endpoints."""

from __future__ import annotations

import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from public_health_sentinel.api.models import (
    AnomalyResultResponse,
    PaginatedResponse,
)
from public_health_sentinel.db.service import get_anomaly_results
from public_health_sentinel.db.session import get_db_session

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.get(
    "",
    response_model=PaginatedResponse[AnomalyResultResponse],
    summary="Query anomaly detection results",
    description=(
        "Retrieve paginated statistical anomaly results with optional filtering by date range, "
        "region, syndrome, detection method, and anomaly status."
    ),
)
def list_anomaly_results(
    start_date: Optional[date] = Query(None, description="Earliest observation date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Latest observation date (YYYY-MM-DD)"),
    region_id: Optional[str] = Query(None, min_length=1, max_length=64, description="Region identifier"),
    syndrome: Optional[str] = Query(None, min_length=1, max_length=64, description="Syndrome cluster"),
    method: Optional[str] = Query(None, description="Detection algorithm (rolling_mad, ewma, zscore)"),
    is_anomaly: Optional[bool] = Query(None, description="Filter for confirmed anomaly flags (True/False)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page (max: 500)"),
    session: Session = Depends(get_db_session),
) -> PaginatedResponse[AnomalyResultResponse]:
    """Fetch paginated anomaly detection results matching query filters."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start_date ({start_date}) must be less than or equal to end_date ({end_date}).",
        )

    if method and method not in {"rolling_mad", "ewma", "zscore"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid method '{method}'. Must be one of: 'rolling_mad', 'ewma', 'zscore'.",
        )

    offset = (page - 1) * page_size
    records, total = get_anomaly_results(
        session=session,
        start_date=start_date,
        end_date=end_date,
        region_id=region_id,
        syndrome=syndrome,
        detection_method=method,
        is_anomaly=is_anomaly,
        limit=page_size,
        offset=offset,
    )

    items = [
        AnomalyResultResponse(
            id=r.id,
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
            evaluation_status=r.evaluation_status,
            data_source=r.data_source,
            data_status=r.data_status,
            created_at=r.created_at,
        )
        for r in records
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[AnomalyResultResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
