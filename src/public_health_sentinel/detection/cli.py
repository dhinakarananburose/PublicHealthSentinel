"""Command-line interface (CLI) for anomaly detection and benchmark evaluation.

Usage:
    python -m public_health_sentinel.detection.cli [--method all] [--threshold 3.0]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from public_health_sentinel.detection.pipeline import run_detection_pipeline


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for running anomaly detection algorithms."""
    parser = argparse.ArgumentParser(
        prog="public-health-sentinel-detect",
        description="Run statistical anomaly detectors on surveillance observations.",
    )
    parser.add_argument(
        "--method",
        choices=["all", "rolling_mad", "ewma", "zscore"],
        default="all",
        help="Detection algorithm to execute (default: all).",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=21,
        help="Lookback window size in days for rolling baselines (default: 21).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=3.0,
        help="Anomaly detection threshold in standard deviations / robust scale (default: 3.0).",
    )
    parser.add_argument(
        "--min-history",
        type=int,
        default=7,
        help="Minimum number of past observations required before evaluating (default: 7).",
    )
    parser.add_argument(
        "--ewma-lambda",
        type=float,
        default=0.2,
        help="EWMA smoothing parameter lambda in (0, 1] (default: 0.2).",
    )
    parser.add_argument(
        "--surveillance-file",
        type=str,
        default=None,
        help="Path to surveillance CSV file (default: data/processed/surveillance_observations.csv).",
    )
    parser.add_argument(
        "--spikes-file",
        type=str,
        default=None,
        help="Path to injected spikes metadata CSV (default: data/synthetic/synthetic_injected_spikes.csv).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save detection outputs (default: data/processed).",
    )

    args = parser.parse_args(argv)

    print("=" * 70)
    print("  PublicHealthSentinel - Phase 3 Statistical Anomaly Detection")
    print("=" * 70)
    print(f"Method:            {args.method}")
    print(f"Window Size:       {args.window_size} days")
    print(f"Threshold:         {args.threshold}")
    print(f"Min History:       {args.min_history} days")
    print(f"EWMA Lambda:       {args.ewma_lambda}")
    print("-" * 70)

    try:
        result = run_detection_pipeline(
            surveillance_file=Path(args.surveillance_file) if args.surveillance_file else None,
            spikes_file=Path(args.spikes_file) if args.spikes_file else None,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            method=args.method,
            window_size=args.window_size,
            threshold=args.threshold,
            min_history=args.min_history,
            ewma_lambda=args.ewma_lambda,
        )
    except Exception as exc:
        print(f"\n[FATAL ERROR] Anomaly detection terminated with unhandled exception: {exc}")
        return 1

    if result.status == "FAILED":
        print(f"\n[FAILURE] Detection failed with errors: {result.errors}")
        return 1

    print(f"Pipeline Status:   {result.status}")
    print(f"Evaluated Records: {result.total_evaluated_observations}")
    print("\nAnomalies Detected by Method:")
    for m, count in result.anomalies_detected_by_method.items():
        print(f"  - {m}: {count} anomalies flagged")

    if result.metrics_by_method:
        print("\nEvaluation vs Injected Benchmark Spikes:")
        for m, met in result.metrics_by_method.items():
            print(f"  [{m.upper()}]")
            print(f"    Exact-Date: TP={met['true_positives']}, FP={met['false_positives']}, FN={met['false_negatives']}")
            print(f"    Precision={met['precision']}, Recall={met['recall']}, F1={met['f1_score']}, Specificity={met['specificity']}")
            print(f"    Event-Level: Detected {met['detected_events_count']}/{met['total_injected_events']} events (Recall={met['event_recall']})")
            if met.get("mean_detection_delay_days") is not None:
                print(f"    Mean Detection Delay: {met['mean_detection_delay_days']} days")

    print("\nGenerated Artifacts:")
    for name, path in result.output_files.items():
        print(f"  - {name}: {path}")

    print("\n[SUCCESS] Statistical anomaly detection completed cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
