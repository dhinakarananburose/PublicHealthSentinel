"""FastAPI router for Phase 7 Geospatial Intelligence & Surveillance Mapping."""

from __future__ import annotations

from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from public_health_sentinel.db.session import get_db_session
from public_health_sentinel.geospatial.registry import (
    get_regions_geojson,
    list_all_regions,
    normalize_region_id,
)
from public_health_sentinel.geospatial.schemas import (
    GeoJSONFeatureCollection,
    GeospatialLaggedCorrelationResponse,
    GeospatialMobilityOverlayResponse,
    GeospatialSurveillanceResponse,
    GeospatialTimeSeriesResponse,
    SyntheticRegionMetadata,
)
from public_health_sentinel.geospatial.service import (
    compute_geospatial_lagged_correlation,
    get_geospatial_mobility_overlay,
    get_geospatial_timeseries,
    get_regional_surveillance_summary,
)

router = APIRouter(prefix="/geospatial", tags=["Geospatial Intelligence"])


@router.get(
    "/regions",
    response_model=List[SyntheticRegionMetadata],
    summary="List synthetic geographic surveillance regions",
    description="Returns metadata, centroid coordinates, and bounding boxes for all synthetic surveillance sectors.",
)
def list_regions_endpoint() -> List[SyntheticRegionMetadata]:
    """Retrieve all registered synthetic geographic regions."""
    return list_all_regions()


@router.get(
    "/geojson",
    response_model=GeoJSONFeatureCollection,
    summary="Get GeoJSON polygons for synthetic surveillance grid",
    description="Returns RFC 7946 GeoJSON FeatureCollection defining regional polygon boundaries for interactive mapping.",
)
def get_geojson_endpoint() -> GeoJSONFeatureCollection:
    """Retrieve GeoJSON polygons for interactive choropleth/boundary visualization."""
    return get_regions_geojson()


@router.get(
    "/surveillance",
    response_model=GeospatialSurveillanceResponse,
    summary="Get aggregated surveillance and anomaly metrics across regions",
    description="Calculates case totals, crude incidence rates, and anomaly counts per region within the specified date window.",
)
def get_surveillance_summary_endpoint(
    start_date: Optional[date] = Query(None, description="Earliest observation date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Latest observation date (YYYY-MM-DD)"),
    syndrome: Optional[str] = Query(None, description="Filter by syndrome cluster (Respiratory, Gastrointestinal, Febrile)"),
    session: Session = Depends(get_db_session),
) -> GeospatialSurveillanceResponse:
    """Fetch regional surveillance aggregations and anomaly indicators."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start_date ({start_date}) must be less than or equal to end_date ({end_date}).",
        )

    return get_regional_surveillance_summary(
        session=session,
        start_date=start_date,
        end_date=end_date,
        syndrome=syndrome,
    )


@router.get(
    "/timeseries",
    response_model=GeospatialTimeSeriesResponse,
    summary="Get daily time series with anomaly flags for a region",
    description="Returns time-series counts, baseline estimations, detection thresholds, and anomaly flags for a specific region.",
)
def get_timeseries_endpoint(
    region_id: str = Query("REGION_A", description="Region identifier (e.g. REGION_A)"),
    syndrome: str = Query("Respiratory", description="Syndrome cluster"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    detection_method: str = Query("rolling_mad", description="Anomaly detection algorithm (rolling_mad, ewma, zscore)"),
    session: Session = Depends(get_db_session),
) -> GeospatialTimeSeriesResponse:
    """Fetch time series data aligned with algorithmic anomaly indicators."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start_date ({start_date}) must be less than or equal to end_date ({end_date}).",
        )

    return get_geospatial_timeseries(
        session=session,
        region_id=region_id,
        syndrome=syndrome,
        start_date=start_date,
        end_date=end_date,
        detection_method=detection_method,
    )


@router.get(
    "/mobility",
    response_model=GeospatialMobilityOverlayResponse,
    summary="Get aligned surveillance and mobility time series",
    description="Returns dual-axis time series matching clinical symptom reports against population mobility deviations.",
)
def get_mobility_overlay_endpoint(
    region_id: str = Query("REGION_A", description="Region identifier (e.g. REGION_A)"),
    syndrome: str = Query("Respiratory", description="Syndrome cluster"),
    mobility_metric: str = Query("transit_station_pct_change", description="Mobility metric name"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    session: Session = Depends(get_db_session),
) -> GeospatialMobilityOverlayResponse:
    """Fetch aligned surveillance observations and mobility indicators."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start_date ({start_date}) must be less than or equal to end_date ({end_date}).",
        )

    return get_geospatial_mobility_overlay(
        session=session,
        region_id=region_id,
        syndrome=syndrome,
        mobility_metric=mobility_metric,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/correlations",
    response_model=GeospatialLaggedCorrelationResponse,
    summary="Compute lagged cross-correlations between mobility and symptoms",
    description="Calculates Pearson and Spearman cross-correlations across temporal lag offsets (-7 to +14 days).",
)
def get_lagged_correlations_endpoint(
    region_id: str = Query("REGION_A", description="Region identifier (e.g. REGION_A)"),
    syndrome: str = Query("Respiratory", description="Syndrome cluster"),
    mobility_metric: str = Query("transit_station_pct_change", description="Mobility metric name"),
    min_lag: int = Query(-7, ge=-30, le=30, description="Minimum temporal lag offset (days)"),
    max_lag: int = Query(14, ge=-30, le=60, description="Maximum temporal lag offset (days)"),
    session: Session = Depends(get_db_session),
) -> GeospatialLaggedCorrelationResponse:
    """Fetch lagged cross-correlation curve for the selected region and metric."""
    if min_lag >= max_lag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"min_lag ({min_lag}) must be strictly less than max_lag ({max_lag}).",
        )

    return compute_geospatial_lagged_correlation(
        session=session,
        region_id=region_id,
        syndrome=syndrome,
        mobility_metric=mobility_metric,
        min_lag=min_lag,
        max_lag=max_lag,
    )
