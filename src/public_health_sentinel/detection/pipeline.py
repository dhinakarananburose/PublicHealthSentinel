"""Orchestration pipeline for statistical anomaly detection and benchmark evaluation.

Coordinates:
1. Loading processed surveillance observations
2. Running selected detector(s) with past-only baselines
3. Evaluating detection against ground-truth injected spike events
4. Emitting per-observation results, anomaly summaries, and comparison reports
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from public_health_sentinel.config import get_config
from public_health_sentinel.detection.baseline import DetectionResult
from public_health_sentinel.detection.evaluation import (
    EvaluationMetrics,
    compare_detectors,
    evaluate_detector,
    load_injected_spikes,
)
from public_health_sentinel.detection.ewma import EWMADetector
from public_health_sentinel.detection.rolling_mad import RollingMADDetector
from public_health_sentinel.detection.zscore import ZScoreDetector
from public_health_sentinel.loader import load_surveillance_csv
from public_health_sentinel.synthetic_generator import InjectedSpike


@dataclass
class DetectionPipelineResult:
    """Outcome and artifacts produced by the anomaly detection pipeline."""

    status: Literal["SUCCESS", "FAILED"]
    methods_run: list[str]
    total_evaluated_observations: int
    anomalies_detected_by_method: dict[str, int]
    metrics_by_method: dict[str, Any] = field(default_factory=dict)
    output_files: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "methods_run": self.methods_run,
            "total_evaluated_observations": self.total_evaluated_observations,
            "anomalies_detected_by_method": self.anomalies_detected_by_method,
            "output_files": self.output_files,
            "errors": self.errors,
            "metrics_by_method": self.metrics_by_method,
        }


def _atomic_write_dataframe(df: pd.DataFrame, target_path: Path) -> Path:
    """Write DataFrame atomically using temporary file rename."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".tmp_{os.getpid()}_{target_path.name}")
    try:
        df.to_csv(temp_path, index=False)
        os.replace(temp_path, target_path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
    return target_path


def _atomic_write_json(data: dict[str, Any], target_path: Path) -> Path:
    """Write JSON data atomically."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".tmp_{os.getpid()}_{target_path.name}")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(temp_path, target_path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
    return target_path


def run_detection_pipeline(
    surveillance_file: Path | str | None = None,
    spikes_file: Path | str | None = None,
    output_dir: Path | str | None = None,
    method: Literal["all", "rolling_mad", "ewma", "zscore"] = "all",
    window_size: int = 21,
    threshold: float = 3.0,
    min_history: int = 7,
    ewma_lambda: float = 0.2,
) -> DetectionPipelineResult:
    """Run the statistical anomaly detection pipeline.

    Args:
        surveillance_file: Path to processed surveillance observations CSV.
        spikes_file: Optional path to benchmark injected spikes metadata CSV.
        output_dir: Target output directory for detection artifacts.
        method: Which detector to run ('all', 'rolling_mad', 'ewma', 'zscore').
        window_size: Lookback window in days for rolling detectors.
        threshold: Decision threshold multiplier (standard deviations / robust scale).
        min_history: Minimum number of historical observations required before evaluation.
        ewma_lambda: Smoothing parameter for EWMA detector.

    Returns:
        DetectionPipelineResult with file paths, detection counts, and metrics.
    """
    config = get_config()
    proc_dir = Path(output_dir) if output_dir else config.data_processed_dir
    proc_dir.mkdir(parents=True, exist_ok=True)

    surv_path = Path(surveillance_file) if surveillance_file else proc_dir / "surveillance_observations.csv"
    if not surv_path.exists():
        return DetectionPipelineResult(
            status="FAILED",
            methods_run=[],
            total_evaluated_observations=0,
            anomalies_detected_by_method={},
            errors=[f"Surveillance dataset not found at '{surv_path}'. Run Phase 2 pipeline first."],
        )

    df_surv = load_surveillance_csv(surv_path)

    # Load injected spikes metadata if available
    injected_spikes: list[InjectedSpike] = []
    if spikes_file:
        injected_spikes = load_injected_spikes(Path(spikes_file))
    else:
        default_spikes_path = config.data_synthetic_dir / "synthetic_injected_spikes.csv"
        if default_spikes_path.exists():
            injected_spikes = load_injected_spikes(default_spikes_path)

    # Initialize detectors
    detector_instances = {}
    if method in ("all", "rolling_mad"):
        detector_instances["rolling_mad"] = RollingMADDetector(
            window_size=window_size,
            threshold=threshold,
            min_history=min_history,
        )
    if method in ("all", "ewma"):
        detector_instances["ewma"] = EWMADetector(
            lambda_=ewma_lambda,
            threshold=threshold,
            min_history=min_history,
        )
    if method in ("all", "zscore"):
        detector_instances["zscore"] = ZScoreDetector(
            window_size=window_size,
            threshold=threshold,
            min_history=min_history,
        )

    results_by_method: dict[str, list[DetectionResult]] = {}
    anomalies_counts: dict[str, int] = {}
    output_files: dict[str, str] = {}
    all_anomaly_rows: list[dict[str, Any]] = []

    for name, detector in detector_instances.items():
        res = detector.detect(df_surv)
        results_by_method[name] = res

        # Count anomalies
        anom_res = [r for r in res if r.is_anomaly is True]
        anomalies_counts[name] = len(anom_res)

        # Collect anomaly rows for summary
        for r in anom_res:
            all_anomaly_rows.append(r.to_flat_dict())

        # Write per-method observation CSV
        method_csv = proc_dir / f"detection_results_{name}.csv"
        method_df = pd.DataFrame([r.to_flat_dict() for r in res])
        _atomic_write_dataframe(method_df, method_csv)
        output_files[f"detection_results_{name}"] = str(method_csv)

    # Primary detection results CSV (either single method or rolling_mad if all)
    primary_name = "rolling_mad" if "rolling_mad" in results_by_method else list(results_by_method.keys())[0]
    primary_csv = proc_dir / "detection_results.csv"
    primary_df = pd.DataFrame([r.to_flat_dict() for r in results_by_method[primary_name]])
    _atomic_write_dataframe(primary_df, primary_csv)
    output_files["detection_results"] = str(primary_csv)

    # Write anomalies summary CSV
    anomalies_summary_file = proc_dir / "anomalies_summary.csv"
    if all_anomaly_rows:
        anomalies_df = pd.DataFrame(all_anomaly_rows)
    else:
        anomalies_df = pd.DataFrame(
            columns=[
                "observation_date",
                "region_id",
                "syndrome",
                "observed_count",
                "expected_baseline",
                "anomaly_score",
                "detection_threshold",
                "detection_method",
            ]
        )
    _atomic_write_dataframe(anomalies_df, anomalies_summary_file)
    output_files["anomalies_summary"] = str(anomalies_summary_file)

    # Evaluation against benchmark spikes
    metrics_by_method: dict[str, Any] = {}
    if injected_spikes:
        comparison_report = compare_detectors(results_by_method, injected_spikes)
        metrics_by_method = comparison_report["metrics_by_method"]

        report_file = proc_dir / "method_comparison_report.json"
        _atomic_write_json(comparison_report, report_file)
        output_files["method_comparison_report"] = str(report_file)

        # Injected spike event breakdown report
        spike_eval_data = {
            "injected_events_count": len(injected_spikes),
            "events": [s.to_dict() for s in injected_spikes],
            "evaluation_by_method": {
                m: metrics_by_method[m]["event_details"] for m in metrics_by_method
            },
        }
        spike_eval_file = proc_dir / "spike_evaluation_report.json"
        _atomic_write_json(spike_eval_data, spike_eval_file)
        output_files["spike_evaluation_report"] = str(spike_eval_file)

    first_method_results = list(results_by_method.values())[0]
    total_eval = len(first_method_results)

    return DetectionPipelineResult(
        status="SUCCESS",
        methods_run=list(results_by_method.keys()),
        total_evaluated_observations=total_eval,
        anomalies_detected_by_method=anomalies_counts,
        metrics_by_method=metrics_by_method,
        output_files=output_files,
    )
