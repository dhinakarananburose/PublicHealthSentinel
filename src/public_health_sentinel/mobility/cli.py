"""Command-line interface (CLI) for Phase 4 Mobility Analysis and Predictive Evaluation.

Usage:
    python -m public_health_sentinel.mobility.cli [OPTIONS]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from public_health_sentinel.mobility.pipeline import run_mobility_analysis_pipeline


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for mobility analysis and predictive model comparison."""
    parser = argparse.ArgumentParser(
        prog="public-health-sentinel-mobility",
        description="PublicHealthSentinel - Phase 4 Mobility Analysis and Predictive Evaluation.",
    )

    parser.add_argument(
        "--surveillance-file",
        type=str,
        default="data/processed/surveillance_observations.csv",
        help="Path to processed surveillance CSV (default: data/processed/surveillance_observations.csv).",
    )
    parser.add_argument(
        "--mobility-file",
        type=str,
        default="data/processed/mobility_indicators.csv",
        help="Path to processed mobility CSV (default: data/processed/mobility_indicators.csv).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports/mobility",
        help="Directory to write analysis artifacts, reports, and figures (default: reports/mobility).",
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
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic model training (default: 42).",
    )

    args = parser.parse_args(argv)

    print("=" * 75)
    print("  PublicHealthSentinel - Phase 4 Mobility Analysis & Predictive Evaluation")
    print("=" * 75)
    print(f"Surveillance File: {args.surveillance_file}")
    print(f"Mobility File:     {args.mobility_file}")
    print(f"Output Directory:  {args.output_dir}")
    print(f"Lag Offset Range:  [{args.min_lag}, {args.max_lag}] days")
    print(f"Train/Test Ratio:  {args.train_ratio:.2f} (chronological)")
    print(f"Random Seed:       {args.seed}")
    print("-" * 75)

    try:
        result = run_mobility_analysis_pipeline(
            surveillance_path=args.surveillance_file,
            mobility_path=args.mobility_file,
            output_dir=args.output_dir,
            min_lag=args.min_lag,
            max_lag=args.max_lag,
            train_ratio=args.train_ratio,
            random_seed=args.seed,
        )
    except Exception as exc:
        print(f"\n[FATAL ERROR] Mobility analysis terminated with exception: {exc}")
        return 1

    summary = result.alignment_summary
    comp = result.model_comparison
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
    print(f"  - Aligned Dataset:    {result.aligned_dataset_path}")
    print(f"  - Descriptive Stats:  {result.descriptive_stats_path}")
    print(f"  - Correlation Report: {result.correlation_report_path}")
    print(f"  - Lag Analysis:       {result.lag_analysis_path}")
    print(f"  - Model Comparison:   {result.model_comparison_path}")
    print(f"  - Markdown Summary:   {result.markdown_report_path}")
    for fig_name, fig_path in result.figures_generated.items():
        print(f"  - Figure ({fig_name}): {fig_path}")

    print("\n[SUCCESS] Phase 4 mobility analysis completed cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
