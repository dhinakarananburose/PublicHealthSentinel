"""Method C: Rolling Historical Z-Score Anomaly Detector.

A classic parametric baseline detector for syndromic surveillance:
- Past-only rolling historical window (zero future leakage)
- Independent region-syndrome time series processing
- Configurable window size and threshold multiplier
- Safe handling of zero standard deviation via configurable scale floor

SCIENTIFIC LIMITATIONS:
Z-score standardization assumes a symmetric, normal Gaussian distribution.
Public health counts are discrete, non-negative integers that frequently exhibit:
1. Right-skewness and overdispersion (Poisson/Negative Binomial characteristics)
2. Susceptibility to the 'masking effect': a single massive surge inside the
   rolling lookback window inflates both the mean and standard deviation,
   desensitizing detection for subsequent days.
"""

from __future__ import annotations

from datetime import date
import numpy as np
import pandas as pd

from public_health_sentinel.detection.baseline import (
    BaseAnomalyDetector,
    DetectionResult,
    EvaluationStatus,
)
from public_health_sentinel.schemas import DataStatus


class ZScoreDetector(BaseAnomalyDetector):
    """Parametric rolling Z-score anomaly detector."""

    def __init__(
        self,
        window_size: int = 21,
        threshold: float = 3.0,
        min_history: int = 7,
        min_scale: float = 1.0,
    ) -> None:
        """Initialize the Z-Score detector.

        Args:
            window_size: Number of past observations in rolling baseline window.
            threshold: Number of standard deviations above baseline to flag as anomaly.
            min_history: Minimum number of historical observations required before evaluating.
            min_scale: Minimum standard deviation floor to prevent division by zero.
        """
        super().__init__(name="zscore")
        if window_size < 2:
            raise ValueError(f"window_size must be >= 2, got {window_size}")
        if min_history < 2 or min_history > window_size:
            raise ValueError(f"min_history must be in [2, {window_size}], got {min_history}")
        if threshold <= 0:
            raise ValueError(f"threshold must be > 0, got {threshold}")

        self.window_size = window_size
        self.threshold = threshold
        self.min_history = min_history
        self.min_scale = min_scale

    def detect_series(
        self,
        series_df: pd.DataFrame,
        region_id: str,
        syndrome: str,
    ) -> list[DetectionResult]:
        """Process an individual region-syndrome time series chronologically."""
        results: list[DetectionResult] = []

        sorted_df = series_df.sort_values("observation_date").reset_index(drop=True)
        past_counts: list[float] = []

        for idx, row in sorted_df.iterrows():
            obs_date_val = row["observation_date"]
            if isinstance(obs_date_val, str):
                obs_date = date.fromisoformat(obs_date_val)
            elif hasattr(obs_date_val, "date"):
                obs_date = obs_date_val.date()
            else:
                obs_date = obs_date_val

            raw_count = row.get("report_count")
            data_source = str(row.get("data_source", "UNKNOWN"))
            raw_status = row.get("data_status", "simulated")
            try:
                data_status = DataStatus(raw_status)
            except ValueError:
                data_status = DataStatus.SIMULATED

            # Check 1: Missing count
            if pd.isna(raw_count) or raw_count is None:
                results.append(
                    DetectionResult(
                        observation_date=obs_date,
                        region_id=region_id,
                        syndrome=syndrome,
                        observed_count=None,
                        expected_baseline=None,
                        anomaly_score=None,
                        detection_threshold=self.threshold,
                        is_anomaly=None,
                        detection_method=self.name,
                        history_count=len(past_counts[-self.window_size :]),
                        evaluation_status=EvaluationStatus.MISSING_COUNT,
                        data_source=data_source,
                        data_status=data_status,
                    )
                )
                continue

            # Check 2: Invalid input
            try:
                count_val = int(raw_count)
                if count_val < 0:
                    raise ValueError("Negative count")
            except (ValueError, TypeError):
                results.append(
                    DetectionResult(
                        observation_date=obs_date,
                        region_id=region_id,
                        syndrome=syndrome,
                        observed_count=None,
                        expected_baseline=None,
                        anomaly_score=None,
                        detection_threshold=self.threshold,
                        is_anomaly=None,
                        detection_method=self.name,
                        history_count=len(past_counts[-self.window_size :]),
                        evaluation_status=EvaluationStatus.INVALID_INPUT,
                        data_source=data_source,
                        data_status=data_status,
                    )
                )
                continue

            # Extract window of strictly prior observations
            window_slice = past_counts[-self.window_size :]
            history_count = len(window_slice)

            # Check 3: Insufficient history (warm-up phase)
            if history_count < self.min_history:
                results.append(
                    DetectionResult(
                        observation_date=obs_date,
                        region_id=region_id,
                        syndrome=syndrome,
                        observed_count=count_val,
                        expected_baseline=None,
                        anomaly_score=None,
                        detection_threshold=self.threshold,
                        is_anomaly=None,
                        detection_method=self.name,
                        history_count=history_count,
                        evaluation_status=EvaluationStatus.INSUFFICIENT_HISTORY,
                        data_source=data_source,
                        data_status=data_status,
                    )
                )
                past_counts.append(float(count_val))
                continue

            # Parametric rolling mean & sample standard deviation
            history_arr = np.array(window_slice, dtype=np.float64)
            mean_val = float(np.mean(history_arr))
            sample_std = float(np.std(history_arr, ddof=1))

            # Zero-std fallback: floor at min_scale
            std_val = max(sample_std, self.min_scale)

            score = (count_val - mean_val) / std_val
            is_anomaly = bool(score >= self.threshold)

            results.append(
                DetectionResult(
                    observation_date=obs_date,
                    region_id=region_id,
                    syndrome=syndrome,
                    observed_count=count_val,
                    expected_baseline=round(mean_val, 2),
                    anomaly_score=round(float(score), 4),
                    detection_threshold=self.threshold,
                    is_anomaly=is_anomaly,
                    detection_method=self.name,
                    history_count=history_count,
                    evaluation_status=EvaluationStatus.EVALUATED,
                    data_source=data_source,
                    data_status=data_status,
                )
            )

            # Update past history buffer with current observation AFTER evaluation
            past_counts.append(float(count_val))

        return results
