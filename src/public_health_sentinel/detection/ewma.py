"""Method B: Exponentially Weighted Moving Average (EWMA) Anomaly Detector.

A statistical process control detector for early public-health surge detection:
- Processes series independently per (region_id, syndrome)
- Uses past observations only (zero future leakage)
- Smooths historical counts with parameter lambda in (0, 1]
- Calculates time-varying asymptotic control limits
- Handles short warm-up histories and zero variance safely
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


class EWMADetector(BaseAnomalyDetector):
    """Exponentially Weighted Moving Average (EWMA) anomaly detector."""

    def __init__(
        self,
        lambda_: float = 0.2,
        threshold: float = 3.0,
        min_history: int = 7,
        min_scale: float = 1.0,
    ) -> None:
        """Initialize EWMA detector.

        Args:
            lambda_: Smoothing parameter in (0, 1]. Smaller values give more weight to older history.
            threshold: Number of control-limit standard deviations above baseline to flag an anomaly (L).
            min_history: Minimum number of historical observations required to establish initial level.
            min_scale: Minimum standard deviation floor to prevent division by zero.
        """
        super().__init__(name="ewma")
        if not (0.0 < lambda_ <= 1.0):
            raise ValueError(f"lambda_ must be in (0, 1], got {lambda_}")
        if threshold <= 0:
            raise ValueError(f"threshold must be > 0, got {threshold}")
        if min_history < 2:
            raise ValueError(f"min_history must be >= 2, got {min_history}")

        self.lambda_ = lambda_
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
        ewma_level: float | None = None
        eval_step = 0

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
                        expected_baseline=round(ewma_level, 2) if ewma_level is not None else None,
                        anomaly_score=None,
                        detection_threshold=self.threshold,
                        is_anomaly=None,
                        detection_method=self.name,
                        history_count=len(past_counts),
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
                        expected_baseline=round(ewma_level, 2) if ewma_level is not None else None,
                        anomaly_score=None,
                        detection_threshold=self.threshold,
                        is_anomaly=None,
                        detection_method=self.name,
                        history_count=len(past_counts),
                        evaluation_status=EvaluationStatus.INVALID_INPUT,
                        data_source=data_source,
                        data_status=data_status,
                    )
                )
                continue

            history_count = len(past_counts)

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
                if len(past_counts) == self.min_history:
                    # Initialize initial EWMA level from warm-up sample mean
                    ewma_level = float(np.mean(past_counts))
                continue

            # Active evaluation using PRIOR state Z_{t-1} and past sample variance
            assert ewma_level is not None
            eval_step += 1

            # Past sample variance
            sample_std = float(np.std(past_counts, ddof=1))
            sigma = max(sample_std, self.min_scale)

            # EWMA standard deviation factor with finite-horizon correction:
            # Var(Z_t) = sigma^2 * (lambda / (2 - lambda)) * [1 - (1 - lambda)^(2*t)]
            time_factor = 1.0 - (1.0 - self.lambda_) ** (2 * eval_step)
            ewma_sigma = sigma * np.sqrt((self.lambda_ / (2.0 - self.lambda_)) * max(time_factor, 1e-4))
            ewma_sigma = max(float(ewma_sigma), self.min_scale)

            # Standardized score
            score = (count_val - ewma_level) / ewma_sigma
            is_anomaly = bool(score >= self.threshold)

            results.append(
                DetectionResult(
                    observation_date=obs_date,
                    region_id=region_id,
                    syndrome=syndrome,
                    observed_count=count_val,
                    expected_baseline=round(ewma_level, 2),
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

            # Update EWMA state AFTER evaluation to strictly prevent future data leakage
            ewma_level = float(self.lambda_ * count_val + (1.0 - self.lambda_) * ewma_level)
            past_counts.append(float(count_val))

        return results
