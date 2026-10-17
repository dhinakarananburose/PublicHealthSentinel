"""Predictive evaluation comparing Surveillance-Only baseline against Mobility-Augmented models.

Experimental Design:
1. Target Definition:
   Next-day syndromic surge: Binary target Y(t+1) indicating whether symptom count
   at day (t+1) exceeds the causal rolling historical threshold computed strictly from
   past data up to day t (window=14, k=2.5 robust scale).
2. Leakage Prevention:
   - Features at prediction time t utilize ONLY observations from days <= t.
   - No observation from day (t+1) is ever used as a feature.
   - Preprocessing scaling parameters (mean, scale) are fit ONLY on the training split.
   - Synthetic injected-spike metadata is NEVER used as an input feature.
3. Chronological Train/Test Partition:
   - Train and test sets are partitioned chronologically by date (e.g., 70% train / 30% test).
   - Strict time-ordering is preserved; no random shuffling across time.
4. Scientific Integrity:
   - Explicitly labeled as a synthetic-data experiment.
   - Models are regularized (L2 Logistic Regression with balanced class weighting).
   - Honest reporting of whether mobility improves, degrades, or matches baseline performance.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.preprocessing import StandardScaler


@dataclass
class ModelEvaluationResult:
    """Evaluation metrics for a single predictive model on held-out test data."""

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
    confusion_matrix: dict[str, int]
    coefficients: dict[str, float]
    intercept: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ComparativeEvaluation:
    """Rigorous comparison between surveillance-only baseline and mobility-augmented model."""

    target_definition: str
    train_date_range: list[str]
    test_date_range: list[str]
    train_ratio: float
    baseline_model: ModelEvaluationResult
    augmented_model: ModelEvaluationResult
    delta_precision: float
    delta_recall: float
    delta_f1: float
    delta_specificity: float
    performance_verdict: str
    synthetic_experiment_notice: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_definition": self.target_definition,
            "train_date_range": self.train_date_range,
            "test_date_range": self.test_date_range,
            "train_ratio": self.train_ratio,
            "baseline_model": self.baseline_model.to_dict(),
            "augmented_model": self.augmented_model.to_dict(),
            "delta_precision": self.delta_precision,
            "delta_recall": self.delta_recall,
            "delta_f1": self.delta_f1,
            "delta_specificity": self.delta_specificity,
            "performance_verdict": self.performance_verdict,
            "synthetic_experiment_notice": self.synthetic_experiment_notice,
        }


def _compute_rolling_mad_threshold(
    history: list[float],
    threshold_factor: float = 2.5,
    min_scale: float = 1.0,
) -> float:
    """Calculate causal rolling median + k * robust MAD upper threshold."""
    arr = np.array(history, dtype=float)
    median_val = float(np.median(arr))
    mad_val = float(np.median(np.abs(arr - median_val)))
    robust_scale = max(1.4826 * mad_val, min_scale)
    return median_val + threshold_factor * robust_scale


def build_evaluation_dataset(
    aligned_df: pd.DataFrame,
    mobility_metrics: Sequence[str],
    lookback_window: int = 14,
    anomaly_threshold_k: float = 2.5,
) -> pd.DataFrame:
    """Construct chronological feature vectors and next-day target labels.

    For each region-syndrome series at prediction date t:
    Target:
      Y(t+1) = 1 if report_count(t+1) > historical_threshold(t) else 0.
      historical_threshold(t) is computed from [t - lookback_window + 1, ..., t].

    Surveillance Features (known at time t):
      - count_lag_0, count_lag_1, count_lag_2, count_lag_3, count_lag_7
      - count_rolling_mean_7, count_rolling_std_7
      - count_velocity (C_t - C_{t-1})
      - day_of_week (0 to 6)

    Mobility Features (known at time t):
      For each mobility metric:
      - mob_{metric}_lag_0, mob_{metric}_lag_1, mob_{metric}_lag_3, mob_{metric}_lag_7
      - mob_{metric}_rolling_mean_7
      - mob_{metric}_velocity (M_t - M_{t-1})
    """
    df = aligned_df.copy()
    if not isinstance(df["observation_date"].iloc[0], date):
        df["observation_date"] = pd.to_datetime(df["observation_date"]).dt.date

    rows: list[dict[str, Any]] = []

    # Group by region and syndrome
    for (region_id, syndrome), grp in df.groupby(["region_id", "syndrome"]):
        grp_sorted = grp.sort_values("observation_date").reset_index(drop=True)
        dates_list = list(grp_sorted["observation_date"])
        counts_list = list(grp_sorted["report_count"])

        # Map dates to row index
        date_to_idx = {d: i for i, d in enumerate(dates_list)}

        # Build metric lookups
        metric_series: dict[str, list[float]] = {}
        for m in mobility_metrics:
            if m in grp_sorted.columns:
                metric_series[m] = list(grp_sorted[m])

        # Generate sample for each day t where lookback history and next-day target exist
        # Need at least lookback_window (e.g. 14) days before t, and t+1 must exist
        for idx in range(lookback_window - 1, len(dates_list) - 1):
            curr_date = dates_list[idx]
            next_date = dates_list[idx + 1]

            # Verify consecutive calendar days for next-day target
            if next_date != curr_date + timedelta(days=1):
                continue

            curr_count = counts_list[idx]
            next_count = counts_list[idx + 1]

            # Missing count check
            if pd.isna(curr_count) or pd.isna(next_count):
                continue

            # Historical baseline lookback window [idx - lookback_window + 1 ... idx]
            past_counts = counts_list[idx - lookback_window + 1 : idx + 1]
            if any(pd.isna(c) for c in past_counts):
                continue

            threshold_t = _compute_rolling_mad_threshold(
                past_counts, threshold_factor=anomaly_threshold_k, min_scale=1.0
            )

            # Target label at t+1
            target_y = 1 if float(next_count) > threshold_t else 0

            # Surveillance features at time t
            row_dict: dict[str, Any] = {
                "observation_date": curr_date,
                "target_date": next_date,
                "region_id": str(region_id),
                "syndrome": str(syndrome),
                "target_next_day_surge": target_y,
                # Surveillance lags
                "surv_count_lag_0": float(curr_count),
                "surv_count_lag_1": float(counts_list[idx - 1]),
                "surv_count_lag_2": float(counts_list[idx - 2]),
                "surv_count_lag_3": float(counts_list[idx - 3]),
                "surv_count_lag_7": float(counts_list[idx - 7]),
                "surv_count_rolling_mean_7": float(np.mean(counts_list[idx - 6 : idx + 1])),
                "surv_count_rolling_std_7": float(np.std(counts_list[idx - 6 : idx + 1])),
                "surv_count_velocity": float(curr_count - counts_list[idx - 1]),
                "day_of_week": curr_date.weekday(),
            }

            # Mobility features at time t
            has_all_mob = True
            for m in mobility_metrics:
                m_vals = metric_series.get(m)
                if m_vals is None:
                    has_all_mob = False
                    break

                m_curr = m_vals[idx]
                m_lag1 = m_vals[idx - 1]
                m_lag3 = m_vals[idx - 3]
                m_lag7 = m_vals[idx - 7]
                m_window = m_vals[idx - 6 : idx + 1]

                if any(pd.isna(v) for v in [m_curr, m_lag1, m_lag3, m_lag7] + m_window):
                    has_all_mob = False
                    break

                prefix = f"mob_{m}"
                row_dict[f"{prefix}_lag_0"] = float(m_curr)
                row_dict[f"{prefix}_lag_1"] = float(m_lag1)
                row_dict[f"{prefix}_lag_3"] = float(m_lag3)
                row_dict[f"{prefix}_lag_7"] = float(m_lag7)
                row_dict[f"{prefix}_rolling_mean_7"] = float(np.mean(m_window))
                row_dict[f"{prefix}_velocity"] = float(m_curr - m_lag1)

            if has_all_mob:
                rows.append(row_dict)

    dataset_df = pd.DataFrame(rows)
    if dataset_df.empty:
        raise ValueError("Evaluation dataset is empty. Ensure sufficient history and valid records.")

    return dataset_df.sort_values(["observation_date", "region_id", "syndrome"]).reset_index(drop=True)


def evaluate_models(
    dataset_df: pd.DataFrame,
    mobility_metrics: Sequence[str],
    train_ratio: float = 0.70,
    random_seed: int = 42,
) -> ComparativeEvaluation:
    """Fit and compare Surveillance-Only baseline and Mobility-Augmented models.

    Args:
        dataset_df: Feature dataset from build_evaluation_dataset.
        mobility_metrics: Names of mobility indicators included in dataset.
        train_ratio: Fraction of chronological date span allocated to training (default 0.70).
        random_seed: Solver random seed for deterministic reproducibility.

    Returns:
        ComparativeEvaluation with complete test metrics and difference analysis.
    """
    df = dataset_df.copy()
    unique_dates = sorted(df["observation_date"].unique())
    num_dates = len(unique_dates)

    if num_dates < 10:
        raise ValueError(f"Insufficient unique dates for chronological train/test split: {num_dates}")

    split_idx = int(num_dates * train_ratio)
    split_date = unique_dates[split_idx]

    train_df = df[df["observation_date"] <= split_date].copy()
    test_df = df[df["observation_date"] > split_date].copy()

    if train_df.empty or test_df.empty:
        raise ValueError("Train or test split is empty after chronological partition.")

    # Target arrays
    y_train = train_df["target_next_day_surge"].to_numpy(dtype=int)
    y_test = test_df["target_next_day_surge"].to_numpy(dtype=int)

    # Feature column lists
    base_features = [
        "surv_count_lag_0",
        "surv_count_lag_1",
        "surv_count_lag_2",
        "surv_count_lag_3",
        "surv_count_lag_7",
        "surv_count_rolling_mean_7",
        "surv_count_rolling_std_7",
        "surv_count_velocity",
        "day_of_week",
    ]

    mob_features: list[str] = []
    for m in mobility_metrics:
        prefix = f"mob_{m}"
        mob_features.extend(
            [
                f"{prefix}_lag_0",
                f"{prefix}_lag_1",
                f"{prefix}_lag_3",
                f"{prefix}_lag_7",
                f"{prefix}_rolling_mean_7",
                f"{prefix}_velocity",
            ]
        )

    augmented_features = base_features + [f for f in mob_features if f in df.columns]

    def _train_and_eval(feature_names: list[str], model_name: str) -> ModelEvaluationResult:
        X_train_raw = train_df[feature_names].to_numpy(dtype=float)
        X_test_raw = test_df[feature_names].to_numpy(dtype=float)

        # Preprocessing: Fit scaler ONLY on training data to prevent leakage
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_raw)
        X_test_scaled = scaler.transform(X_test_raw)

        # Handle edge case where training set contains only a single class
        if len(np.unique(y_train)) < 2:
            single_class = int(y_train[0])
            y_pred = np.full(len(y_test), fill_value=single_class, dtype=int)
            coef_dict = {feat: 0.0 for feat in feature_names}
            intercept = 0.0
        else:
            # Regularized logistic regression with balanced class weights (default is L2 regularization)
            clf = LogisticRegression(
                C=1.0,
                class_weight="balanced",
                solver="lbfgs",
                max_iter=1000,
                random_state=random_seed,
            )
            clf.fit(X_train_scaled, y_train)
            y_pred = clf.predict(X_test_scaled)
            coef_dict = {
                feat: round(float(clf.coef_[0][i]), 4) for i, feat in enumerate(feature_names)
            }
            intercept = round(float(clf.intercept_[0]), 4)

        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()
        tn, fp, fn, tp = int(tn), int(fp), int(fn), int(tp)

        # Metrics with safe zero division
        pos_test = int(np.sum(y_test == 1))
        neg_test = int(np.sum(y_test == 0))

        precision = round(float(tp / (tp + fp)), 4) if (tp + fp) > 0 else 0.0
        recall = round(float(tp / (tp + fn)), 4) if (tp + fn) > 0 else 0.0
        specificity = round(float(tn / (tn + fp)), 4) if (tn + fp) > 0 else 0.0
        f1 = (
            round(float(2 * precision * recall / (precision + recall)), 4)
            if (precision + recall) > 0
            else 0.0
        )
        accuracy = round(float((tp + tn) / len(y_test)), 4)

        # Feature coefficients
        coef_dict = {
            feat: round(float(clf.coef_[0][i]), 4) for i, feat in enumerate(feature_names)
        }

        return ModelEvaluationResult(
            model_name=model_name,
            feature_names=feature_names,
            train_sample_size=len(train_df),
            test_sample_size=len(test_df),
            test_positive_count=pos_test,
            test_negative_count=neg_test,
            precision=precision,
            recall=recall,
            f1_score=f1,
            specificity=specificity,
            accuracy=accuracy,
            confusion_matrix={"tn": tn, "fp": fp, "fn": fn, "tp": tp},
            coefficients=coef_dict,
            intercept=round(float(clf.intercept_[0]), 4),
        )

    baseline_res = _train_and_eval(base_features, "Surveillance-Only Baseline")
    augmented_res = _train_and_eval(augmented_features, "Surveillance + Mobility Augmented")

    # Metric differences
    d_prec = round(augmented_res.precision - baseline_res.precision, 4)
    d_rec = round(augmented_res.recall - baseline_res.recall, 4)
    d_f1 = round(augmented_res.f1_score - baseline_res.f1_score, 4)
    d_spec = round(augmented_res.specificity - baseline_res.specificity, 4)

    # Scientific verdict formulation
    if d_f1 > 0.03:
        verdict = (
            f"Mobility-augmented model showed positive improvement in F1-score (+{d_f1:.4f}) "
            "over the surveillance-only baseline on held-out test data in this synthetic experiment."
        )
    elif d_f1 < -0.03:
        verdict = (
            f"Mobility-augmented model exhibited lower F1-score ({d_f1:.4f}) compared to baseline. "
            "Additional mobility features introduced variance/noise on held-out synthetic test data."
        )
    else:
        verdict = (
            f"Mobility-augmented model showed comparable performance to surveillance baseline "
            f"(Delta F1 = {d_f1:+.4f}, Delta Precision = {d_prec:+.4f}, Delta Recall = {d_rec:+.4f}). "
            "Mobility indicators did not provide substantial incremental predictive signal on held-out synthetic data."
        )

    notice = (
        "SYNTHETIC-DATA EXPERIMENT: Evaluated on synthetic surveillance and mobility datasets. "
        "Results reflect synthetic generating dynamics only and do NOT demonstrate real-world epidemiological relationships."
    )

    train_dates = [train_df["observation_date"].min().isoformat(), train_df["observation_date"].max().isoformat()]
    test_dates = [test_df["observation_date"].min().isoformat(), test_df["observation_date"].max().isoformat()]

    return ComparativeEvaluation(
        target_definition="Next-day syndromic surge: count(t+1) > rolling_median(t) + 2.5 * rolling_MAD(t) (14-day causal window)",
        train_date_range=train_dates,
        test_date_range=test_dates,
        train_ratio=train_ratio,
        baseline_model=baseline_res,
        augmented_model=augmented_res,
        delta_precision=d_prec,
        delta_recall=d_rec,
        delta_f1=d_f1,
        delta_specificity=d_spec,
        performance_verdict=verdict,
        synthetic_experiment_notice=notice,
    )
