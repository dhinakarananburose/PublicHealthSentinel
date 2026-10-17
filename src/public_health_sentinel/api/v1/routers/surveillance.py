"""Surveillance observation query endpoints."""

from __future__ import annotations

import math
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from public_health_sentinel.api.models import (
    PaginatedResponse,
    SurveillanceObservationResponse,
)
from public_health_sentinel.db.service import get_surveillance_observations
from public_health_sentinel.db.session import get_db_session

router = APIRouter(prefix="/surveillance", tags=["Surveillance"])


@router.get(
    "",
    response_model=PaginatedResponse[SurveillanceObservationResponse],
    summary="Query syndromic surveillance observations",
    description="Retrieve paginated surveillance observations with optional filtering by date range, region, and syndrome.",
)
def list_surveillance_observations(
    start_date: Optional[date] = Query(None, description="Earliest observation date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Latest observation date (YYYY-MM-DD)"),
    region_id: Optional[str] = Query(None, min_length=1, max_length=64, description="Region identifier"),
    syndrome: Optional[str] = Query(None, min_length=1, max_length=64, description="Syndrome cluster (e.g. Respiratory)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page (max: 500)"),
    session: Session = Depends(get_db_session),
) -> PaginatedResponse[SurveillanceObservationResponse]:
    """Fetch paginated surveillance observations matching query filters."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start_date ({start_date}) must be less than or equal to end_date ({end_date}).",
        )

    offset = (page - 1) * page_size
    records, total = get_surveillance_observations(
        session=session,
        start_date=start_date,
        end_date=end_date,
        region_id=region_id,
        syndrome=syndrome,
        limit=page_size,
        offset=offset,
    )

    items = []
    for r in records:
        crude_rate = (
            round((r.report_count / r.population_denominator) * 100_000.0, 2)
            if r.population_denominator and r.population_denominator > 0
            else None
        )
        items.append(
            SurveillanceObservationResponse(
                id=r.id,
                observation_date=r.observation_date,
                region_id=r.region_id,
                syndrome=r.syndrome,
                report_count=r.report_count,
                reporting_facility_count=r.reporting_facility_count,
                population_denominator=r.population_denominator,
                crude_incidence_per_100k=crude_rate,
                data_source=r.data_source,
                data_status=r.data_status,
                ingestion_timestamp=r.ingestion_timestamp,
            )
        )

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[SurveillanceObservationResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
