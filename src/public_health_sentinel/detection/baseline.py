"""Base classes, data models, and evaluation statuses for statistical anomaly detection.

Enforces:
- Strict past-only lookback without future-data leakage
- Independent series processing per (region_id, syndrome)
- Explicit evaluation status tracking (insufficient history, missing observations, etc.)
- Retention of data provenance metadata
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from enum import Enum
from typing import Any, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from public_health_sentinel.schemas import DataStatus


class EvaluationStatus(str, Enum):
    """Execution status for an observation's anomaly evaluation."""

    EVALUATED = "evaluated"
    INSUFFICIENT_HISTORY = "insufficient_history"
    MISSING_OBSERVATION = "missing_observation"
    MISSING_COUNT = "missing_count"
    INVALID_INPUT = "invalid_input"


class DetectionResult(BaseModel):
    """Output record of a statistical anomaly detection evaluation on a single observation."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        validate_default=True,
    )

    observation_date: date = Field(..., description="Date of surveillance observation.")
    region_id: str = Field(..., min_length=1, description="Jurisdiction identifier.")
    syndrome: str = Field(..., min_length=1, description="Syndrome under surveillance.")
    observed_count: Optional[int] = Field(
        default=None,
        description="Observed count for this date. None if missing.",
    )
    expected_baseline: Optional[float] = Field(
        default=None,
        description="Historical baseline estimate (mean, median, or EWMA level).",
    )
    anomaly_score: Optional[float] = Field(
        default=None,
        description="Standardized statistical score or deviation metric.",
    )
    detection_threshold: Optional[float] = Field(
        default=None,
        description="Decision threshold above which an anomaly is triggered.",
    )
    is_anomaly: Optional[bool] = Field(
        default=None,
        description="True if an anomaly is confirmed; False if confirmed normal; None if unevaluated.",
    )
    detection_method: str = Field(
        ...,
        min_length=1,
        description="Identifier of the detection algorithm.",
    )
    history_count: int = Field(
        default=0,
        ge=0,
        description="Number of past valid observations in the historical baseline window.",
    )
    evaluation_status: EvaluationStatus = Field(
        default=EvaluationStatus.EVALUATED,
        description="Audit status indicating whether evaluation succeeded or reason for skipping.",
    )
    data_source: str = Field(
        default="UNKNOWN",
        description="Data provenance source stream identifier.",
    )
    data_status: DataStatus = Field(
        default=DataStatus.SIMULATED,
        description="Provenance classification: 'real', 'simulated', or 'derived'.",
    )

    def to_flat_dict(self) -> dict[str, Any]:
        """Convert detection result to a flat dictionary suitable for DataFrame/CSV export."""
        return {
            "observation_date": self.observation_date.isoformat(),
            "region_id": self.region_id,
            "syndrome": self.syndrome,
            "observed_count": self.observed_count,
            "expected_baseline": self.expected_baseline,
            "anomaly_score": self.anomaly_score,
            "detection_threshold": self.detection_threshold,
            "is_anomaly": self.is_anomaly,
            "detection_method": self.detection_method,
            "history_count": self.history_count,
            "evaluation_status": self.evaluation_status.value,
            "data_source": self.data_source,
            "data_status": self.data_status.value,
        }


class BaseAnomalyDetector(ABC):
    """Abstract base class for time-series anomaly detectors in PublicHealthSentinel."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def detect_series(
        self,
        series_df: pd.DataFrame,
        region_id: str,
        syndrome: str,
    ) -> list[DetectionResult]:
        """Run detection on a single chronological time series for one region-syndrome pair.

        Args:
            series_df: DataFrame sorted chronologically containing observations for one pair.
            region_id: Jurisdiction identifier.
            syndrome: Syndrome cluster name.

        Returns:
            List of DetectionResult instances for each observation.
        """

    def detect(self, df: pd.DataFrame) -> list[DetectionResult]:
        """Execute detection across all region-syndrome combinations in the dataset.

        Guarantees:
        - Independent processing per (region_id, syndrome)
        - Strict chronological sorting before evaluation
        - Past observations only (zero future leakage)

        Args:
            df: DataFrame containing surveillance observations.

        Returns:
            Combined list of DetectionResult objects sorted by date, region, syndrome.
        """
        if df.empty:
            return []

        required_cols = {"observation_date", "region_id", "syndrome", "report_count"}
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            raise ValueError(f"Input DataFrame is missing required columns: {sorted(missing_cols)}")

        results: list[DetectionResult] = []

        # Group by region and syndrome
        groups = df.groupby(["region_id", "syndrome"], sort=True)

        for (region_id, syndrome), group in groups:
            # Sort strictly chronologically
            sorted_group = group.sort_values("observation_date").copy()
            series_results = self.detect_series(
                series_df=sorted_group,
                region_id=str(region_id),
                syndrome=str(syndrome),
            )
            results.extend(series_results)

        # Sort final output consistently
        results.sort(key=lambda r: (r.observation_date, r.region_id, r.syndrome))
        return results
