"""Geospatial service layer for regional aggregation, time-series alignment, and spatial intelligence.

Follows strict epidemiological principles:
- Crude rates require explicit non-zero population denominators.
- Preserves missing observation days without coercing them to zero.
- Reuses verified mobility alignment and lagged cross-correlation analytics.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from public_health_sentinel.db.models import (
    AnomalyDetectionResultModel,
    MobilityIndicatorModel,
    SurveillanceObservationModel,
)
from public_health_sentinel.geospatial.registry import (
    SYNTHETIC_REGIONS,
    get_region_metadata,
    normalize_region_id,
)
from public_health_sentinel.geospatial.schemas import (
    GeospatialLaggedCorrelationResponse,
    GeospatialMobilityOverlayResponse,
    GeospatialSurveillanceResponse,
    GeospatialTimeSeriesPoint,
    GeospatialTimeSeriesResponse,
    LaggedCorrelationPointSchema,
    MobilityOverlayPoint,
    RegionalSurveillanceSummary,
)
from public_health_sentinel.mobility.alignment import align_surveillance_and_mobility
from public_health_sentinel.mobility.lag_analysis import compute_lagged_correlations


def get_regional_surveillance_summary(
    session: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    syndrome: Optional[str] = None,
) -> GeospatialSurveillanceResponse:
    """Aggregate surveillance counts and anomaly flags across all regions."""
    # 1. Base query for surveillance observations
    surv_query = select(
        SurveillanceObservationModel.region_id,
        SurveillanceObservationModel.syndrome,
        func.sum(SurveillanceObservationModel.report_count).label("cases"),
        func.count(SurveillanceObservationModel.id).label("record_count"),
        func.count(func.distinct(SurveillanceObservationModel.observation_date)).label("active_days"),
    ).group_by(
        SurveillanceObservationModel.region_id,
        SurveillanceObservationModel.syndrome,
    )

    if start_date:
        surv_query = surv_query.where(SurveillanceObservationModel.observation_date >= start_date)
    if end_date:
        surv_query = surv_query.where(SurveillanceObservationModel.observation_date <= end_date)
    if syndrome:
        surv_query = surv_query.where(SurveillanceObservationModel.syndrome == syndrome)

    surv_rows = session.execute(surv_query).all()

    # Determine actual min/max dates if not provided
    if not start_date or not end_date:
        min_max_date = session.execute(
            select(
                func.min(SurveillanceObservationModel.observation_date),
                func.max(SurveillanceObservationModel.observation_date),
            )
        ).one()
        actual_start = start_date or min_max_date[0] or date(2026, 1, 1)
        actual_end = end_date or min_max_date[1] or date(2026, 6, 29)
    else:
        actual_start = start_date
        actual_end = end_date

    # 2. Query anomaly counts per region
    anom_query = select(
        AnomalyDetectionResultModel.region_id,
        func.count(AnomalyDetectionResultModel.id).label("anomaly_count"),
    ).where(AnomalyDetectionResultModel.is_anomaly == True)  # noqa: E712

    if start_date:
        anom_query = anom_query.where(AnomalyDetectionResultModel.observation_date >= start_date)
    if end_date:
        anom_query = anom_query.where(AnomalyDetectionResultModel.observation_date <= end_date)
    if syndrome:
        anom_query = anom_query.where(AnomalyDetectionResultModel.syndrome == syndrome)

    anom_query = anom_query.group_by(AnomalyDetectionResultModel.region_id)
    anom_rows = session.execute(anom_query).all()
    anomalies_by_region: Dict[str, int] = {r[0]: int(r[1]) for r in anom_rows}

    # 3. Organize surveillance cases and syndromic breakdown per region
    region_cases: Dict[str, int] = {}
    region_active_days: Dict[str, int] = {}
    syndrome_breakdown_by_region: Dict[str, Dict[str, int]] = {}

    for r_id, synd, cases, _, active_days in surv_rows:
        region_cases[r_id] = region_cases.get(r_id, 0) + int(cases)
        region_active_days[r_id] = max(region_active_days.get(r_id, 0), int(active_days))
        if r_id not in syndrome_breakdown_by_region:
            syndrome_breakdown_by_region[r_id] = {}
        syndrome_breakdown_by_region[r_id][synd] = int(cases)

    # 4. Construct regional summaries for known regions
    summaries: List[RegionalSurveillanceSummary] = []
    total_cases_all = 0
    total_anomalies_all = sum(anomalies_by_region.values())

    for r_id, meta in SYNTHETIC_REGIONS.items():
        c = region_cases.get(r_id, 0)
        total_cases_all += c
        anom_c = anomalies_by_region.get(r_id, 0)
        pop = meta.population
        crude_rate = round((c / pop) * 100_000.0, 2) if pop > 0 else None

        summaries.append(
            RegionalSurveillanceSummary(
                region_id=r_id,
                region_name=meta.name,
                population=pop,
                facility_count=meta.facility_count,
                total_cases=c,
                crude_rate_per_100k=crude_rate,
                active_days_count=region_active_days.get(r_id, 0),
                syndromic_breakdown=syndrome_breakdown_by_region.get(r_id, {}),
                anomaly_count=anom_c,
                recent_anomaly_detected=(anom_c > 0),
                centroid_lat=meta.centroid_lat,
                centroid_lon=meta.centroid_lon,
            )
        )

    return GeospatialSurveillanceResponse(
        start_date=actual_start,
        end_date=actual_end,
        syndrome_filter=syndrome,
        total_regions=len(summaries),
        total_surveillance_cases=total_cases_all,
        total_anomalies_flagged=total_anomalies_all,
        regions=summaries,
    )


def get_geospatial_timeseries(
    session: Session,
    region_id: str,
    syndrome: str = "Respiratory",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    detection_method: str = "rolling_mad",
) -> GeospatialTimeSeriesResponse:
    """Fetch aligned daily time-series with anomaly flags for a region and syndrome."""
    norm_id = normalize_region_id(region_id)
    meta = get_region_metadata(norm_id)
    region_name = meta.name if meta else norm_id

    # Query surveillance observations
    surv_query = select(SurveillanceObservationModel).where(
        SurveillanceObservationModel.region_id == norm_id,
        SurveillanceObservationModel.syndrome == syndrome,
    )
    if start_date:
        surv_query = surv_query.where(SurveillanceObservationModel.observation_date >= start_date)
    if end_date:
        surv_query = surv_query.where(SurveillanceObservationModel.observation_date <= end_date)

    surv_query = surv_query.order_by(SurveillanceObservationModel.observation_date.asc())
    surv_records = session.scalars(surv_query).all()

    # Query anomaly detection results for matching dates
    anom_query = select(AnomalyDetectionResultModel).where(
        AnomalyDetectionResultModel.region_id == norm_id,
        AnomalyDetectionResultModel.syndrome == syndrome,
        AnomalyDetectionResultModel.detection_method == detection_method,
    )
    if start_date:
        anom_query = anom_query.where(AnomalyDetectionResultModel.observation_date >= start_date)
    if end_date:
        anom_query = anom_query.where(AnomalyDetectionResultModel.observation_date <= end_date)

    anom_records = session.scalars(anom_query).all()
    anom_map: Dict[date, AnomalyDetectionResultModel] = {
        r.observation_date: r for r in anom_records
    }

    points: List[GeospatialTimeSeriesPoint] = []
    anomaly_count = 0

    for s in surv_records:
        a = anom_map.get(s.observation_date)
        is_anom = bool(a.is_anomaly) if a and a.is_anomaly is not None else False
        if is_anom:
            anomaly_count += 1

        points.append(
            GeospatialTimeSeriesPoint(
                observation_date=s.observation_date,
                region_id=s.region_id,
                syndrome=s.syndrome,
                report_count=s.report_count,
                is_anomaly=is_anom,
                anomaly_score=a.anomaly_score if a else None,
                expected_baseline=a.expected_baseline if a else None,
                detection_threshold=a.detection_threshold if a else None,
                detection_method=detection_method if a else None,
            )
        )

    actual_start = points[0].observation_date if points else (start_date or date(2026, 1, 1))
    actual_end = points[-1].observation_date if points else (end_date or date(2026, 6, 29))

    return GeospatialTimeSeriesResponse(
        region_id=norm_id,
        region_name=region_name,
        syndrome=syndrome,
        start_date=actual_start,
        end_date=actual_end,
        points_count=len(points),
        anomaly_points_count=anomaly_count,
        points=points,
    )


def get_geospatial_mobility_overlay(
    session: Session,
    region_id: str,
    syndrome: str = "Respiratory",
    mobility_metric: str = "transit_station_pct_change",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> GeospatialMobilityOverlayResponse:
    """Retrieve calendar-aligned surveillance counts and mobility percentage deviation."""
    norm_id = normalize_region_id(region_id)
    meta = get_region_metadata(norm_id)
    region_name = meta.name if meta else norm_id

    # 1. Fetch surveillance records
    surv_query = select(SurveillanceObservationModel).where(
        SurveillanceObservationModel.region_id == norm_id,
        SurveillanceObservationModel.syndrome == syndrome,
    )
    if start_date:
        surv_query = surv_query.where(SurveillanceObservationModel.observation_date >= start_date)
    if end_date:
        surv_query = surv_query.where(SurveillanceObservationModel.observation_date <= end_date)
    surv_query = surv_query.order_by(SurveillanceObservationModel.observation_date.asc())
    surv_records = session.scalars(surv_query).all()

    # 2. Fetch mobility records
    mob_query = select(MobilityIndicatorModel).where(
        MobilityIndicatorModel.region_id == norm_id,
        MobilityIndicatorModel.mobility_metric == mobility_metric,
    )
    if start_date:
        mob_query = mob_query.where(MobilityIndicatorModel.observation_date >= start_date)
    if end_date:
        mob_query = mob_query.where(MobilityIndicatorModel.observation_date <= end_date)
    mob_records = session.scalars(mob_query).all()
    mob_map: Dict[date, float] = {m.observation_date: m.mobility_value for m in mob_records}

    # 3. Fetch anomaly flags
    anom_query = select(
        AnomalyDetectionResultModel.observation_date,
        AnomalyDetectionResultModel.is_anomaly,
    ).where(
        AnomalyDetectionResultModel.region_id == norm_id,
        AnomalyDetectionResultModel.syndrome == syndrome,
        AnomalyDetectionResultModel.is_anomaly == True,  # noqa: E712
    )
    if start_date:
        anom_query = anom_query.where(AnomalyDetectionResultModel.observation_date >= start_date)
    if end_date:
        anom_query = anom_query.where(AnomalyDetectionResultModel.observation_date <= end_date)
    anom_dates = {row[0] for row in session.execute(anom_query).all()}

    # 4. Construct aligned overlay points
    points: List[MobilityOverlayPoint] = []
    for s in surv_records:
        points.append(
            MobilityOverlayPoint(
                observation_date=s.observation_date,
                report_count=s.report_count,
                mobility_value=mob_map.get(s.observation_date),
                is_anomaly=(s.observation_date in anom_dates),
            )
        )

    actual_start = points[0].observation_date if points else (start_date or date(2026, 1, 1))
    actual_end = points[-1].observation_date if points else (end_date or date(2026, 6, 29))

    return GeospatialMobilityOverlayResponse(
        region_id=norm_id,
        region_name=region_name,
        syndrome=syndrome,
        mobility_metric=mobility_metric,
        start_date=actual_start,
        end_date=actual_end,
        aligned_days=len(points),
        points=points,
    )


def compute_geospatial_lagged_correlation(
    session: Session,
    region_id: str,
    syndrome: str = "Respiratory",
    mobility_metric: str = "transit_station_pct_change",
    min_lag: int = -7,
    max_lag: int = 14,
) -> GeospatialLaggedCorrelationResponse:
    """Compute cross-correlation across temporal lag offsets (-7 to +14 days)."""
    norm_id = normalize_region_id(region_id)
    meta = get_region_metadata(norm_id)
    region_name = meta.name if meta else norm_id

    # Fetch observations to DataFrames
    surv_records = session.scalars(
        select(SurveillanceObservationModel).where(
            SurveillanceObservationModel.region_id == norm_id,
            SurveillanceObservationModel.syndrome == syndrome,
        )
    ).all()

    mob_records = session.scalars(
        select(MobilityIndicatorModel).where(
            MobilityIndicatorModel.region_id == norm_id,
            MobilityIndicatorModel.mobility_metric == mobility_metric,
        )
    ).all()

    if not surv_records or not mob_records:
        return GeospatialLaggedCorrelationResponse(
            region_id=norm_id,
            region_name=region_name,
            syndrome=syndrome,
            mobility_metric=mobility_metric,
            sample_size=0,
            best_positive_lag_days=None,
            best_positive_lag_pearson_r=None,
            lag_points=[],
        )

    surv_df = pd.DataFrame([r.to_dict() for r in surv_records])
    surv_df["observation_date"] = pd.to_datetime(surv_df["observation_date"]).dt.date

    mob_df = pd.DataFrame([r.to_dict() for r in mob_records])
    mob_df["observation_date"] = pd.to_datetime(mob_df["observation_date"]).dt.date

    # Align via existing verified alignment utility
    aligned_df, _ = align_surveillance_and_mobility(surv_df, mob_df)

    # Filter to specific region and syndrome
    aligned_series = aligned_df[
        (aligned_df["region_id"] == norm_id) & (aligned_df["syndrome"] == syndrome)
    ]

    analyses = compute_lagged_correlations(
        aligned_df=aligned_series,
        mobility_metric=mobility_metric,
        min_lag=min_lag,
        max_lag=max_lag,
    )

    if not analyses:
        return GeospatialLaggedCorrelationResponse(
            region_id=norm_id,
            region_name=region_name,
            syndrome=syndrome,
            mobility_metric=mobility_metric,
            sample_size=0,
            best_positive_lag_days=None,
            best_positive_lag_pearson_r=None,
            lag_points=[],
        )

    analysis = analyses[0]
    lag_points_schema = [
        LaggedCorrelationPointSchema(
            lag_days=p.lag_days,
            sample_size_n=p.sample_size_n,
            pearson_r=round(p.pearson_r, 4) if p.pearson_r is not None else None,
            pearson_p_value=round(p.pearson_p_value, 6) if p.pearson_p_value is not None else None,
            spearman_rho=round(p.spearman_rho, 4) if p.spearman_rho is not None else None,
            spearman_p_value=round(p.spearman_p_value, 6) if p.spearman_p_value is not None else None,
            convention_description=p.convention_description,
        )
        for p in analysis.lag_points
    ]

    return GeospatialLaggedCorrelationResponse(
        region_id=norm_id,
        region_name=region_name,
        syndrome=syndrome,
        mobility_metric=mobility_metric,
        sample_size=len(aligned_series),
        best_positive_lag_days=analysis.best_positive_lag_days,
        best_positive_lag_pearson_r=round(analysis.best_positive_lag_pearson_r, 4)
        if analysis.best_positive_lag_pearson_r is not None
        else None,
        lag_points=lag_points_schema,
    )
