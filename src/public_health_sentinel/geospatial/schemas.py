"""Schemas for Phase 7 Geospatial Intelligence and Surveillance Mapping.

Strictly preserves data integrity:
- Explicit synthetic geography notices on all regional geographic structures.
- Separate regional summaries and non-coercion of missing observation days into zeros.
- Crude incidence rate calculation requires explicit population denominators.
- Explicit non-diagnostic anomaly definitions.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class SyntheticRegionMetadata(BaseModel):
    """Metadata describing a synthetic surveillance region."""

    model_config = ConfigDict(frozen=True)

    region_id: str = Field(..., description="Unique region identifier (e.g. REGION_A)")
    name: str = Field(..., description="Human-readable synthetic sector name")
    code: str = Field(..., description="Short sector code")
    population: int = Field(..., description="Reference population denominator")
    facility_count: int = Field(..., description="Number of baseline reporting surveillance facilities")
    centroid_lat: float = Field(..., description="Synthetic latitude coordinate")
    centroid_lon: float = Field(..., description="Synthetic longitude coordinate")
    bounding_box: tuple[float, float, float, float] = Field(
        ...,
        description="Bounding box [min_lon, min_lat, max_lon, max_lat]",
    )
    is_synthetic_geography: bool = Field(
        default=True,
        description="Declares that coordinates and boundaries are simulated research fixtures.",
    )
    synthetic_disclaimer: str = Field(
        default=(
            "SYNTHETIC-GEOGRAPHY NOTICE: Regional boundaries and coordinates are simulated "
            "benchmark geometries for evaluating spatial surveillance algorithms. They do "
            "not correspond to real-world administrative jurisdictions or patient locations."
        ),
        description="Integrity disclaimer regarding synthetic coordinates.",
    )


class RegionalSurveillanceSummary(BaseModel):
    """Aggregated surveillance statistics for a single region across a time window."""

    model_config = ConfigDict(frozen=True)

    region_id: str
    region_name: str
    population: int
    facility_count: int
    total_cases: int
    crude_rate_per_100k: Optional[float]
    active_days_count: int
    syndromic_breakdown: Dict[str, int]
    anomaly_count: int
    recent_anomaly_detected: bool
    centroid_lat: float
    centroid_lon: float
    data_status: str = "simulated"


class GeospatialSurveillanceResponse(BaseModel):
    """Response payload for multi-region surveillance summary aggregation."""

    model_config = ConfigDict(frozen=True)

    start_date: date
    end_date: date
    syndrome_filter: Optional[str]
    total_regions: int
    total_surveillance_cases: int
    total_anomalies_flagged: int
    regions: List[RegionalSurveillanceSummary]
    synthetic_notice: str = (
        "SYNTHETIC RESEARCH DATA: Observations represent synthetic benchmark data. "
        "Regional coordinates are abstract simulation fixtures."
    )
    non_clinical_notice: str = (
        "DISCLAIMER: Aggregated case counts and statistical anomaly flags do not "
        "represent confirmed outbreak events, clinical triage, or patient diagnoses."
    )


class GeospatialTimeSeriesPoint(BaseModel):
    """Single date observation for time-series anomaly exploration."""

    model_config = ConfigDict(frozen=True)

    observation_date: date
    region_id: str
    syndrome: str
    report_count: int
    is_anomaly: bool = False
    anomaly_score: Optional[float] = None
    expected_baseline: Optional[float] = None
    detection_threshold: Optional[float] = None
    detection_method: Optional[str] = None


class GeospatialTimeSeriesResponse(BaseModel):
    """Complete time-series points for a region and syndrome."""

    model_config = ConfigDict(frozen=True)

    region_id: str
    region_name: str
    syndrome: str
    start_date: date
    end_date: date
    points_count: int
    anomaly_points_count: int
    points: List[GeospatialTimeSeriesPoint]
    synthetic_notice: str = (
        "SYNTHETIC SURVEILLANCE DATA: Baseline, threshold, and score metrics are generated "
        "by statistical anomaly algorithms on simulated data."
    )


class MobilityOverlayPoint(BaseModel):
    """Dual-axis point aligning surveillance counts and mobility percentage deviation."""

    model_config = ConfigDict(frozen=True)

    observation_date: date
    report_count: int
    mobility_value: Optional[float] = None
    is_anomaly: bool = False


class GeospatialMobilityOverlayResponse(BaseModel):
    """Response containing aligned surveillance and mobility series."""

    model_config = ConfigDict(frozen=True)

    region_id: str
    region_name: str
    syndrome: str
    mobility_metric: str
    start_date: date
    end_date: date
    aligned_days: int
    points: List[MobilityOverlayPoint]
    synthetic_notice: str = (
        "SYNTHETIC MOBILITY BENCHMARK: Mobility deviations and symptom counts are simulated."
    )
    causality_disclaimer: str = (
        "EPIDEMIOLOGICAL PRINCIPLE: Temporal correlation between population mobility shifts "
        "and surveillance counts does not imply causality or disease transmission dynamics."
    )


class LaggedCorrelationPointSchema(BaseModel):
    """Individual lag offset correlation metric."""

    model_config = ConfigDict(frozen=True)

    lag_days: int
    sample_size_n: int
    pearson_r: Optional[float]
    pearson_p_value: Optional[float]
    spearman_rho: Optional[float]
    spearman_p_value: Optional[float]
    convention_description: str


class GeospatialLaggedCorrelationResponse(BaseModel):
    """Response payload for cross-correlation analysis."""

    model_config = ConfigDict(frozen=True)

    region_id: str
    region_name: str
    syndrome: str
    mobility_metric: str
    sample_size: int
    best_positive_lag_days: Optional[int]
    best_positive_lag_pearson_r: Optional[float]
    lag_points: List[LaggedCorrelationPointSchema]
    lag_convention: str = (
        "Positive Lag (+k): Mobility at day (t - k) paired with symptoms at day t. "
        "Mobility precedes symptom reports by k days."
    )
    causality_disclaimer: str = (
        "CAUTION: Cross-correlations reflect time-series co-movement in benchmark data. "
        "They do not establish clinical incubation periods or transmission causality."
    )


class GeoJSONGeometry(BaseModel):
    """RFC 7946 GeoJSON Polygon Geometry."""

    model_config = ConfigDict(frozen=True)

    type: Literal["Polygon"] = "Polygon"
    coordinates: List[List[List[float]]]


class GeoJSONFeature(BaseModel):
    """RFC 7946 GeoJSON Feature."""

    model_config = ConfigDict(frozen=True)

    type: Literal["Feature"] = "Feature"
    id: str
    properties: Dict[str, Any]
    geometry: GeoJSONGeometry


class GeoJSONFeatureCollection(BaseModel):
    """RFC 7946 GeoJSON Feature Collection."""

    model_config = ConfigDict(frozen=True)

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[GeoJSONFeature]
    synthetic_notice: str = (
        "SYNTHETIC BOUNDARIES: Polygon coordinates represent an abstract synthetic regional grid."
    )
