"""Pydantic request and response models for PublicHealthSentinel FastAPI service.

Enforces:
- Strict parameter bounds and date validation
- Consistent pagination envelopes (page, page_size, total, total_pages)
- Mandatory synthetic data disclaimers on all clinical/surveillance responses
- Non-clinical anomaly interpretation disclaimer
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class HealthResponse(BaseModel):
    """Health check endpoint response model."""

    status: str = Field(..., description="Service health state: 'healthy' or 'degraded'.")
    app_name: str = Field(..., description="Application identifier.")
    environment: str = Field(..., description="Deployment environment.")
    api_version: str = Field(..., description="API semantic version.")
    database_connected: bool = Field(..., description="Database connectivity status.")
    timestamp: datetime = Field(..., description="Server timestamp.")
    demo_mode: bool = Field(default=False, description="Whether the instance is operating in public demonstration mode.")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard pagination wrapper for collection endpoints."""

    items: list[T] = Field(..., description="List of items for the requested page.")
    total: int = Field(..., ge=0, description="Total matching items across all pages.")
    page: int = Field(..., ge=1, description="Current page number (1-indexed).")
    page_size: int = Field(..., ge=1, description="Number of items requested per page.")
    total_pages: int = Field(..., ge=0, description="Total available pages.")
    synthetic_experiment_notice: str = Field(
        default=(
            "SYNTHETIC-DATA NOTICE: All observations and indicators are simulated. "
            "Data reflects synthetic mathematical models and does not represent real-world patient records."
        ),
        description="Mandatory scientific provenance disclosure.",
    )


class SurveillanceObservationResponse(BaseModel):
    """API representation of a syndromic surveillance observation."""

    id: int
    observation_date: date
    region_id: str
    syndrome: str
    report_count: int
    reporting_facility_count: Optional[int] = None
    population_denominator: Optional[int] = None
    crude_incidence_per_100k: Optional[float] = None
    data_source: str
    data_status: str
    ingestion_timestamp: datetime


class MobilityIndicatorResponse(BaseModel):
    """API representation of an aggregated mobility indicator."""

    id: int
    observation_date: date
    region_id: str
    mobility_metric: str
    mobility_value: float
    data_source: str
    data_status: str
    ingestion_timestamp: datetime


class AnomalyResultResponse(BaseModel):
    """API representation of an anomaly detection result."""

    id: int
    observation_date: date
    region_id: str
    syndrome: str
    detection_method: str
    observed_count: Optional[int] = None
    expected_baseline: Optional[float] = None
    anomaly_score: Optional[float] = None
    detection_threshold: Optional[float] = None
    is_anomaly: Optional[bool] = None
    history_count: int
    evaluation_status: str
    data_source: str
    data_status: str
    created_at: datetime
    interpretation_disclaimer: str = Field(
        default=(
            "STATISTICAL SURGE ONLY: Anomaly flags reflect statistical deviations from historical baselines. "
            "They do NOT constitute confirmed epidemiological outbreaks, clinical diagnoses, or etiology."
        ),
        description="Public health interpretation guardrail.",
    )


class RunDetectionRequest(BaseModel):
    """Request payload for triggering anomaly detection via API."""

    model_config = ConfigDict(extra="forbid")

    method: Literal["all", "rolling_mad", "ewma", "zscore"] = Field(
        default="all",
        description="Detection method to execute ('all', 'rolling_mad', 'ewma', 'zscore').",
    )
    window_size: int = Field(
        default=21,
        ge=2,
        le=90,
        description="Lookback window size in days for historical baseline (2 to 90).",
    )
    threshold: float = Field(
        default=3.0,
        gt=0.0,
        le=10.0,
        description="Detection threshold in standard deviations or robust scale (0.1 to 10.0).",
    )
    min_history: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Minimum past observations required before evaluating (1 to 30).",
    )
    ewma_lambda: float = Field(
        default=0.2,
        gt=0.0,
        le=1.0,
        description="EWMA smoothing factor lambda in (0.0, 1.0].",
    )
    persist_results: bool = Field(
        default=True,
        description="Whether to commit detection results to the database.",
    )


class RunDetectionResponse(BaseModel):
    """Response payload returned upon completing an anomaly detection execution."""

    execution_id: str = Field(..., description="Unique audit identifier for this execution.")
    status: str = Field(..., description="Execution status: 'SUCCESS' or 'FAILED'.")
    methods_run: list[str] = Field(..., description="List of detection algorithms executed.")
    total_evaluated_observations: int = Field(..., description="Count of observations evaluated.")
    anomalies_detected_by_method: dict[str, int] = Field(..., description="Anomalies flagged per method.")
    database_records_persisted: int = Field(..., description="Count of result records written to database.")
    metrics_by_method: dict[str, Any] = Field(default_factory=dict, description="Benchmark metrics if evaluated.")
    synthetic_experiment_notice: str = Field(
        default="SYNTHETIC EXPERIMENT: Evaluated on synthetic benchmark surveillance data.",
    )


class ConfusionMatrixModel(BaseModel):
    """Confusion matrix counts for binary classification."""

    tn: int = Field(..., description="True negatives")
    fp: int = Field(..., description="False positives")
    fn: int = Field(..., description="False negatives")
    tp: int = Field(..., description="True positives")


class ModelPerformanceDetails(BaseModel):
    """Performance metrics and parameters for a fitted predictive model."""

    model_name: str
    feature_names: list[str]
    train_sample_size: int
    test_sample_size: int
    test_positive_count: int
    test_negative_count: int
    precision: float
    recall: float
    f1_score: float
    specificity: float
    accuracy: float
    confusion_matrix: ConfusionMatrixModel
    coefficients: dict[str, float]
    intercept: float


class MobilityEvaluationResponse(BaseModel):
    """Empirical benchmark evaluation comparing surveillance-only baseline vs mobility-augmented models."""

    target_definition: str
    train_date_range: list[str]
    test_date_range: list[str]
    train_ratio: float
    baseline_model: ModelPerformanceDetails
    augmented_model: ModelPerformanceDetails
    delta_precision: float
    delta_recall: float
    delta_f1: float
    delta_specificity: float
    performance_verdict: str
    synthetic_experiment_notice: str
