"""Method A: Rolling Median + Median Absolute Deviation (MAD) Anomaly Detector.

A robust non-parametric anomaly detector tailored for syndromic surveillance:
- Past-only historical lookback (zero future leakage)
- Independent region-syndrome time series processing
- Configurable lookback window and detection threshold
- Safe handling of zero MAD via mean absolute deviation and scale floors
- Explicit insufficient-history warm-up handling without normal-class assumption
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from public_health_sentinel.detection.baseline import (
    BaseAnomalyDetector,
    DetectionResult,
    EvaluationStatus,
)
from public_health_sentinel.schemas import DataStatus


class RollingMADDetector(BaseAnomalyDetector):
    """Historical rolling median and median absolute deviation anomaly detector."""

    def __init__(
        self,
        window_size: int = 21,
        threshold: float = 3.0,
        min_history: int = 7,
        min_scale: float = 1.0,
    ) -> None:
        """Initialize the Rolling MAD detector.

        Args:
            window_size: Number of past observations to include in historical window.
            threshold: Number of robust standard deviations above baseline to flag as anomaly.
            min_history: Minimum number of valid past observations required before evaluating.
            min_scale: Minimum scale floor when MAD and MeanAD are zero (prevents zero division).
        """
        super().__init__(name="rolling_mad")
        if window_size < 2:
            raise ValueError(f"window_size must be >= 2, got {window_size}")
        if min_history < 1 or min_history > window_size:
            raise ValueError(f"min_history must be in [1, {window_size}], got {min_history}")
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

        # Ensure sorted chronologically
        sorted_df = series_df.sort_values("observation_date").reset_index(drop=True)

        # Buffer of past valid (date, count) pairs
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

            # Check 2: Invalid input (e.g. negative count)
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
                # Append current valid observation for future baselines
                past_counts.append(float(count_val))
                continue

            # Calculation: Robust Rolling Median & MAD
            history_arr = np.array(window_slice, dtype=np.float64)
            med = float(np.median(history_arr))
            abs_devs = np.abs(history_arr - med)
            raw_mad = float(np.median(abs_devs))

            # Scale estimation:
            # Under normality, scale = 1.4826 * MAD.
            # If MAD == 0 (more than 50% identical values), fallback to MeanAD * 1.2533.
            # If MeanAD == 0 (all values identical), fallback to min_scale.
            if raw_mad > 0:
                scale = 1.4826 * raw_mad
            else:
                mean_ad = float(np.mean(abs_devs))
                if mean_ad > 0:
                    scale = 1.2533 * mean_ad
                else:
                    scale = self.min_scale

            # Safe floor
            scale = max(scale, self.min_scale)

            # Calculate robust standardized score
            score = (count_val - med) / scale
            is_anomaly = bool(score >= self.threshold)

            results.append(
                DetectionResult(
                    observation_date=obs_date,
                    region_id=region_id,
                    syndrome=syndrome,
                    observed_count=count_val,
                    expected_baseline=round(med, 2),
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
