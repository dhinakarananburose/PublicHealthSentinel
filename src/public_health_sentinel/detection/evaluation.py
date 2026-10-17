"""Evaluation metrics for statistical anomaly detectors against benchmark injected spikes.

Calculates:
- Exact-date per-observation metrics: TP, FP, TN, FN, Precision, Recall, F1, Specificity, False Alarm Rate
- Event-level metrics: Event detection status, event recall, and detection delay (lag to first alert)
- Method comparison reports across identical eligible observation subsets

SCIENTIFIC INTEGRITY NOTICE:
- Benchmark spike labels are used solely for retrospective evaluation, never as model features.
- Statistical power notice: With 3 benchmark injected spike events (9 positive days), confidence intervals
  are wide; results measure synthetic benchmark alignment, not validated clinical efficacy.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from public_health_sentinel.detection.baseline import DetectionResult, EvaluationStatus
from public_health_sentinel.synthetic_generator import InjectedSpike

SAMPLE_SIZE_LIMITATION_NOTE: str = (
    "STATISTICAL POWER LIMITATION: The benchmark evaluation dataset contains a small number "
    "of injected surge events (typically 3 events across 9 positive days). Metrics such as "
    "Precision, Recall, and F1 have wide binomial uncertainty. These scores demonstrate relative "
    "algorithmic behavior under synthetic benchmark conditions; they DO NOT establish real-world "
    "clinical sensitivity, diagnostic efficacy, or regulatory readiness."
)


@dataclass
class EventEvaluationResult:
    """Detection performance details for a specific multi-day injected spike event."""

    event_id: str
    start_date: str
    region_id: str
    syndrome: str
    duration_days: int
    spike_count: int
    is_detected: bool
    detection_delay_days: int | None
    alert_dates: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationMetrics:
    """Comprehensive performance evaluation metrics for an anomaly detector."""

    method: str
    total_observations: int
    eligible_evaluated_observations: int
    warmup_un_evaluated_observations: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    specificity: float
    false_alarm_rate_per_day: float
    total_injected_events: int
    detected_events_count: int
    event_recall: float
    mean_detection_delay_days: float | None
    event_details: list[EventEvaluationResult]
    limitations: str = SAMPLE_SIZE_LIMITATION_NOTE

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        d = asdict(self)
        d["event_details"] = [e.to_dict() for e in self.event_details]
        return d

    def to_json(self, indent: int = 2) -> str:
        """Convert metrics to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


def load_injected_spikes(source: Path | str | pd.DataFrame) -> list[InjectedSpike]:
    """Load ground-truth injected spike metadata from CSV or DataFrame."""
    if isinstance(source, pd.DataFrame):
        df = source
    else:
        path = Path(source)
        if not path.exists():
            return []
        df = pd.read_csv(path)

    if df.empty:
        return []

    spikes: list[InjectedSpike] = []
    for _, row in df.iterrows():
        raw_dt = row["observation_date"]
        if isinstance(raw_dt, str):
            dt = date.fromisoformat(raw_dt)
        elif hasattr(raw_dt, "date"):
            dt = raw_dt.date()
        else:
            dt = raw_dt

        spikes.append(
            InjectedSpike(
                observation_date=dt,
                region_id=str(row["region_id"]),
                syndrome=str(row["syndrome"]),
                spike_count=int(row["spike_count"]),
                duration_days=int(row.get("duration_days", 1)),
                description=str(row.get("description", "Injected spike")),
            )
        )
    return spikes


def evaluate_detector(
    results: Sequence[DetectionResult],
    injected_spikes: Sequence[InjectedSpike],
) -> EvaluationMetrics:
    """Evaluate an anomaly detector's predictions against ground-truth injected spikes.

    Args:
        results: List of DetectionResult objects from one detector.
        injected_spikes: Ground-truth list of InjectedSpike events.

    Returns:
        EvaluationMetrics with exact-date and event-level calculations.
    """
    if not results:
        raise ValueError("Cannot evaluate empty detection results.")

    method_name = results[0].detection_method

    # Build set of exact (date, region_id, syndrome) that were positive surge days
    ground_truth_positive_days: set[tuple[date, str, str]] = set()
    for s in injected_spikes:
        for offset in range(s.duration_days):
            target_dt = s.observation_date + timedelta(days=offset)
            ground_truth_positive_days.add((target_dt, s.region_id, s.syndrome))

    # Partition results into eligible (evaluated) vs warm-up / missing
    evaluated_results: list[DetectionResult] = [
        r for r in results if r.evaluation_status == EvaluationStatus.EVALUATED
    ]
    warmup_count = len(results) - len(evaluated_results)

    tp = 0
    fp = 0
    tn = 0
    fn = 0

    # Build lookup of prediction flags: (date, region, syndrome) -> is_anomaly
    pred_map: dict[tuple[date, str, str], bool] = {}

    for r in evaluated_results:
        key = (r.observation_date, r.region_id, r.syndrome)
        is_pred_positive = bool(r.is_anomaly)
        pred_map[key] = is_pred_positive

        is_actual_positive = key in ground_truth_positive_days

        if is_pred_positive and is_actual_positive:
            tp += 1
        elif is_pred_positive and not is_actual_positive:
            fp += 1
        elif not is_pred_positive and not is_actual_positive:
            tn += 1
        else:
            fn += 1

    # Exact-date metrics
    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0
    specificity = round(tn / (tn + fp), 4) if (tn + fp) > 0 else 0.0
    false_alarm_rate = round(fp / (tn + fp), 4) if (tn + fp) > 0 else 0.0

    # Event-level evaluation
    event_details: list[EventEvaluationResult] = []
    delays: list[int] = []

    for idx, s in enumerate(injected_spikes, start=1):
        event_id = f"EVENT_{idx:02d}_{s.region_id}_{s.syndrome}"
        event_alert_dates: list[str] = []
        delay: int | None = None

        for offset in range(s.duration_days):
            target_dt = s.observation_date + timedelta(days=offset)
            key = (target_dt, s.region_id, s.syndrome)
            if pred_map.get(key, False):
                event_alert_dates.append(target_dt.isoformat())
                if delay is None:
                    delay = offset

        is_detected = len(event_alert_dates) > 0
        if delay is not None:
            delays.append(delay)

        event_details.append(
            EventEvaluationResult(
                event_id=event_id,
                start_date=s.observation_date.isoformat(),
                region_id=s.region_id,
                syndrome=s.syndrome,
                duration_days=s.duration_days,
                spike_count=s.spike_count,
                is_detected=is_detected,
                detection_delay_days=delay,
                alert_dates=event_alert_dates,
            )
        )

    detected_events_count = sum(1 for e in event_details if e.is_detected)
    event_recall = round(detected_events_count / max(len(injected_spikes), 1), 4)
    mean_delay = round(float(np.mean(delays)), 2) if delays else None

    return EvaluationMetrics(
        method=method_name,
        total_observations=len(results),
        eligible_evaluated_observations=len(evaluated_results),
        warmup_un_evaluated_observations=warmup_count,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1_score=f1,
        specificity=specificity,
        false_alarm_rate_per_day=false_alarm_rate,
        total_injected_events=len(injected_spikes),
        detected_events_count=detected_events_count,
        event_recall=event_recall,
        mean_detection_delay_days=mean_delay,
        event_details=event_details,
    )


def compare_detectors(
    results_by_method: dict[str, Sequence[DetectionResult]],
    injected_spikes: Sequence[InjectedSpike],
) -> dict[str, Any]:
    """Compare multiple anomaly detection algorithms across the identical observations.

    Args:
        results_by_method: Mapping from detector name to its list of DetectionResult objects.
        injected_spikes: Ground-truth list of benchmark spikes.

    Returns:
        Structured dictionary comparing metrics across all evaluated methods.
    """
    comparison_summary: dict[str, Any] = {
        "methods_evaluated": list(results_by_method.keys()),
        "injected_events_count": len(injected_spikes),
        "metrics_by_method": {},
        "limitations": SAMPLE_SIZE_LIMITATION_NOTE,
    }

    for method_name, res in results_by_method.items():
        metrics = evaluate_detector(res, injected_spikes)
        comparison_summary["metrics_by_method"][method_name] = metrics.to_dict()

    return comparison_summary
