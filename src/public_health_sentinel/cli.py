"""Command-line interface (CLI) for PublicHealthSentinel pipelines.

Usage:
    # Phase 2: Ingestion & Data Pipeline
    python -m public_health_sentinel.cli [--seed 42] [--duration-days 180]

    # Phase 3: Statistical Anomaly Detection
    python -m public_health_sentinel.cli --detect [--method all] [--threshold 3.0]

    # Phase 4: Mobility Analysis and Predictive Evaluation
    python -m public_health_sentinel.cli --analyze-mobility [--output-dir reports/mobility]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from public_health_sentinel.detection.pipeline import run_detection_pipeline
from public_health_sentinel.mobility.pipeline import run_mobility_analysis_pipeline
from public_health_sentinel.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for data generation, ingestion, and anomaly detection."""
    parser = argparse.ArgumentParser(
        prog="public-health-sentinel",
        description="PublicHealthSentinel surveillance data and anomaly detection pipeline.",
    )

    # Mode selection
    parser.add_argument(
        "--detect",
        action="store_true",
        help="Run Phase 3 statistical anomaly detection.",
    )
    parser.add_argument(
        "--analyze-mobility",
        action="store_true",
        help="Run Phase 4 mobility analysis and predictive evaluation.",
    )

    # Phase 2 Data Generation Arguments
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic synthetic data generation (default: 42).",
    )
    parser.add_argument(
        "--duration-days",
        type=int,
        default=180,
        help="Number of days of surveillance to simulate (default: 180).",
    )
    parser.add_argument(
        "--no-spikes",
        action="store_true",
        help="Disable injection of known synthetic anomaly spikes.",
    )
    parser.add_argument(
        "--missing-fraction",
        type=float,
        default=0.0,
        help="Fraction of synthetic observations to deliberately omit (default: 0.0).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Target directory for processed outputs (default: data/processed).",
    )
    parser.add_argument(
        "--synthetic-dir",
        type=str,
        default=None,
        help="Target directory for synthetic benchmarks (default: data/synthetic).",
    )

    # Phase 3 Detection Arguments
    parser.add_argument(
        "--method",
        choices=["all", "rolling_mad", "ewma", "zscore"],
        default=None,
        help="Detection algorithm to execute (rolling_mad, ewma, zscore, all).",
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
        help="Path to surveillance CSV file for detection.",
    )
    parser.add_argument(
        "--spikes-file",
        type=str,
        default=None,
        help="Path to injected spikes metadata CSV for evaluation.",
    )

    # Phase 4 Mobility Arguments
    parser.add_argument(
        "--mobility-file",
        type=str,
        default=None,
        help="Path to mobility indicators CSV (default: data/processed/mobility_indicators.csv).",
    )
    parser.add_argument(
        "--min-lag",
        type=int,
        default=-7,
        help="Minimum lag offset in days for cross-correlation analysis (default: -7).",
    )
    parser.add_argument(
        "--max-lag",
        type=int,
        default=14,
        help="Maximum lag offset in days for cross-correlation analysis (default: 14).",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.70,
        help="Chronological train/test split boundary ratio (default: 0.70).",
    )

    args = parser.parse_args(argv)

    # Route to Phase 4 Mobility Analysis if requested
    if args.analyze_mobility:
        surv_in = args.surveillance_file or "data/processed/surveillance_observations.csv"
        mob_in = args.mobility_file or "data/processed/mobility_indicators.csv"
        out_target = args.output_dir or "reports/mobility"

        print("=" * 75)
        print("  PublicHealthSentinel - Phase 4 Mobility Analysis & Predictive Evaluation")
        print("=" * 75)
        print(f"Surveillance File: {surv_in}")
        print(f"Mobility File:     {mob_in}")
        print(f"Output Directory:  {out_target}")
        print(f"Lag Offset Range:  [{args.min_lag}, {args.max_lag}] days")
        print(f"Train/Test Ratio:  {args.train_ratio:.2f} (chronological)")
        print(f"Random Seed:       {args.seed}")
        print("-" * 75)

        try:
            mob_res = run_mobility_analysis_pipeline(
                surveillance_path=surv_in,
                mobility_path=mob_in,
                output_dir=out_target,
                min_lag=args.min_lag,
                max_lag=args.max_lag,
                train_ratio=args.train_ratio,
                random_seed=args.seed,
            )
        except Exception as exc:
            print(f"\n[FATAL ERROR] Mobility analysis terminated with exception: {exc}")
            return 1

        summary = mob_res.alignment_summary
        comp = mob_res.model_comparison
        base = comp.baseline_model
        aug = comp.augmented_model

        print(f"\n[ALIGNMENT] {summary.aligned_rows} rows aligned across {len(summary.regions_aligned)} regions.")
        print(f"  Complete Cases:       {summary.complete_cases_rows}")
        print(f"  Missing Mobility:     {summary.missing_mobility_rows}")
        print(f"  Duplicate Keys:       {summary.duplicate_mobility_keys_detected}")

        print("\n[MODEL COMPARISON] Next-Day Anomaly Surge Prediction:")
        print(f"  Baseline (Surv Only): F1={base.f1_score:.4f} | Prec={base.precision:.4f} | Rec={base.recall:.4f} | Spec={base.specificity:.4f}")
        print(f"  Augmented (+Mobility): F1={aug.f1_score:.4f} | Prec={aug.precision:.4f} | Rec={aug.recall:.4f} | Spec={aug.specificity:.4f}")
        print(f"  Delta (Aug - Base):   Delta F1={comp.delta_f1:+.4f} | Delta Prec={comp.delta_precision:+.4f} | Delta Rec={comp.delta_recall:+.4f}")
        print(f"  Verdict:              {comp.performance_verdict}")

        print("\n[GENERATED ARTIFACTS]")
        print(f"  - Aligned Dataset:    {mob_res.aligned_dataset_path}")
        print(f"  - Descriptive Stats:  {mob_res.descriptive_stats_path}")
        print(f"  - Correlation Report: {mob_res.correlation_report_path}")
        print(f"  - Lag Analysis:       {mob_res.lag_analysis_path}")
        print(f"  - Model Comparison:   {mob_res.model_comparison_path}")
        print(f"  - Markdown Summary:   {mob_res.markdown_report_path}")
        for fig_name, fig_path in mob_res.figures_generated.items():
            print(f"  - Figure ({fig_name}): {fig_path}")

        print("\n[SUCCESS] Phase 4 mobility analysis completed cleanly.")
        return 0

    # Route to Phase 3 Detection if explicitly requested via --detect or --method
    if args.detect or args.method is not None:
        detection_method = args.method or "all"
        print("=" * 70)
        print("  PublicHealthSentinel - Phase 3 Statistical Anomaly Detection")
        print("=" * 70)
        print(f"Method:            {detection_method}")
        print(f"Window Size:       {args.window_size} days")
        print(f"Threshold:         {args.threshold}")
        print(f"Min History:       {args.min_history} days")
        print(f"EWMA Lambda:       {args.ewma_lambda}")
        print("-" * 70)

        try:
            det_result = run_detection_pipeline(
                surveillance_file=Path(args.surveillance_file) if args.surveillance_file else None,
                spikes_file=Path(args.spikes_file) if args.spikes_file else None,
                output_dir=Path(args.output_dir) if args.output_dir else None,
                method=detection_method,
                window_size=args.window_size,
                threshold=args.threshold,
                min_history=args.min_history,
                ewma_lambda=args.ewma_lambda,
            )
        except Exception as exc:
            print(f"\n[FATAL ERROR] Detection terminated with unhandled exception: {exc}")
            return 1

        if det_result.status == "FAILED":
            print(f"\n[FAILURE] Detection failed with errors: {det_result.errors}")
            return 1

        print(f"Status:            {det_result.status}")
        print(f"Evaluated Records: {det_result.total_evaluated_observations}")
        print("\nAnomalies Detected by Method:")
        for m, count in det_result.anomalies_detected_by_method.items():
            print(f"  - {m}: {count} anomalies flagged")

        if det_result.metrics_by_method:
            print("\nBenchmark Evaluation vs Injected Spikes:")
            for m, met in det_result.metrics_by_method.items():
                print(f"  [{m.upper()}] TP={met['true_positives']}, FP={met['false_positives']}, FN={met['false_negatives']}, Precision={met['precision']}, Recall={met['recall']}, F1={met['f1_score']}")

        print("\nGenerated Artifacts:")
        for name, path in det_result.output_files.items():
            print(f"  - {name}: {path}")

        print("\n[SUCCESS] Statistical anomaly detection completed cleanly.")
        return 0

    # Default: Phase 2 Data Pipeline Execution
    print("=" * 70)
    print("  PublicHealthSentinel - Phase 2 Data Engineering Pipeline")
    print("=" * 70)
    print(f"Random Seed:             {args.seed}")
    print(f"Duration (days):         {args.duration_days}")
    print(f"Inject Known Spikes:     {not args.no_spikes}")
    print(f"Missing Dates Fraction:  {args.missing_fraction}")
    print("-" * 70)

    try:
        result = run_pipeline(
            seed=args.seed,
            duration_days=args.duration_days,
            inject_spikes=not args.no_spikes,
            missing_dates_fraction=args.missing_fraction,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            synthetic_dir=Path(args.synthetic_dir) if args.synthetic_dir else None,
        )
    except Exception as exc:
        print(f"\n[FATAL ERROR] Pipeline terminated with unhandled exception: {exc}")
        return 1

    print(f"Pipeline Status:         {result.status}")
    print(f"Surveillance Records:    {result.surveillance_valid_count} valid, {result.surveillance_invalid_count} rejected")
    print(f"Mobility Records:        {result.mobility_valid_count} valid, {result.mobility_invalid_count} rejected")
    print(f"Surveillance Duplicates: {result.surveillance_quality.duplicate_key_count}")
    print(f"Mobility Duplicates:     {result.mobility_quality.duplicate_key_count}")
    print("\nGenerated Artifacts:")
    for name, path in result.processed_files.items():
        print(f"  - {name}: {path}")

    if result.status == "SUCCESS":
        print("\n[SUCCESS] Phase 2 Data Pipeline completed cleanly.")
        return 0
    else:
        print(f"\n[FAILURE] Pipeline failed with errors: {result.errors}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
