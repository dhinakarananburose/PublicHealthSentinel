import json
import math
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from public_health_sentinel.api.models import (
    MobilityEvaluationResponse,
    MobilityIndicatorResponse,
    PaginatedResponse,
)
from public_health_sentinel.db.service import get_mobility_indicators
from public_health_sentinel.db.session import get_db_session

router = APIRouter(prefix="/mobility", tags=["Mobility"])


def _find_mobility_evaluation_path() -> Path:
    """Resolve the mobility evaluation model comparison JSON file path."""
    candidates = [
        Path("reports/mobility/model_comparison.json"),
        Path(__file__).resolve().parents[4] / "reports" / "mobility" / "model_comparison.json",
        Path(__file__).resolve().parents[3] / "reports" / "mobility" / "model_comparison.json",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]


@router.get(
    "/evaluation",
    response_model=MobilityEvaluationResponse,
    summary="Get empirical mobility model comparison evaluation",
    description="Retrieve the chronological benchmark evaluation results comparing surveillance-only baseline vs mobility-augmented models.",
)
def get_mobility_evaluation() -> MobilityEvaluationResponse:
    """Fetch empirical Phase 4 predictive evaluation results from stored report."""
    report_file = _find_mobility_evaluation_path()
    if not report_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mobility evaluation report has not been generated yet. Run mobility analysis pipeline first.",
        )
    try:
        with open(report_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return MobilityEvaluationResponse(**data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read mobility evaluation report: {exc}",
        )


@router.get(
    "",
    response_model=PaginatedResponse[MobilityIndicatorResponse],
    summary="Query population mobility indicators",
    description="Retrieve paginated mobility indicators with optional filtering by date range, region, and metric name.",
)
def list_mobility_indicators(
    start_date: Optional[date] = Query(None, description="Earliest observation date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Latest observation date (YYYY-MM-DD)"),
    region_id: Optional[str] = Query(None, min_length=1, max_length=64, description="Region identifier"),
    mobility_metric: Optional[str] = Query(
        None, min_length=1, max_length=64, description="Metric name (e.g. transit_station_pct_change)"
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page (max: 500)"),
    session: Session = Depends(get_db_session),
) -> PaginatedResponse[MobilityIndicatorResponse]:
    """Fetch paginated mobility indicators matching query filters."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start_date ({start_date}) must be less than or equal to end_date ({end_date}).",
        )

    offset = (page - 1) * page_size
    records, total = get_mobility_indicators(
        session=session,
        start_date=start_date,
        end_date=end_date,
        region_id=region_id,
        mobility_metric=mobility_metric,
        limit=page_size,
        offset=offset,
    )

    items = [
        MobilityIndicatorResponse(
            id=r.id,
            observation_date=r.observation_date,
            region_id=r.region_id,
            mobility_metric=r.mobility_metric,
            mobility_value=r.mobility_value,
            data_source=r.data_source,
            data_status=r.data_status,
            ingestion_timestamp=r.ingestion_timestamp,
        )
        for r in records
    ]

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[MobilityIndicatorResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
