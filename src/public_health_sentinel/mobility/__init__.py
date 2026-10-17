"""Mobility analysis and predictive evaluation package for PublicHealthSentinel (Phase 4).

Provides:
- alignment: Spatial and temporal alignment of surveillance counts and mobility indicators.
- correlation: Bivariate Pearson and Spearman correlation analysis with p-values and visuals.
- lag_analysis: Calendar-based cross-correlation profiling with documented lead/lag sign conventions.
- evaluation: Chronological predictive modeling comparing surveillance-only baseline to mobility-augmented models.
- pipeline: End-to-end mobility analysis orchestrator producing datasets, figures, and reports.
"""

from public_health_sentinel.mobility.alignment import (
    AlignmentSummary,
    align_surveillance_and_mobility,
    pivot_mobility_indicators,
)
from public_health_sentinel.mobility.correlation import (
    CorrelationRecord,
    compute_correlations,
    compute_descriptive_statistics,
    generate_mobility_figures,
)
from public_health_sentinel.mobility.evaluation import (
    ComparativeEvaluation,
    ModelEvaluationResult,
    build_evaluation_dataset,
    evaluate_models,
)
from public_health_sentinel.mobility.lag_analysis import (
    LagCorrelationPoint,
    SeriesLagAnalysis,
    compute_lagged_correlations,
    plot_cross_correlation_profile,
)
from public_health_sentinel.mobility.pipeline import (
    MobilityPipelineResult,
    run_mobility_analysis_pipeline,
)

__all__ = [
    "AlignmentSummary",
    "ComparativeEvaluation",
    "CorrelationRecord",
    "LagCorrelationPoint",
    "MobilityPipelineResult",
    "ModelEvaluationResult",
    "SeriesLagAnalysis",
    "align_surveillance_and_mobility",
    "build_evaluation_dataset",
    "compute_correlations",
    "compute_descriptive_statistics",
    "compute_lagged_correlations",
    "evaluate_models",
    "generate_mobility_figures",
    "pivot_mobility_indicators",
    "plot_cross_correlation_profile",
    "run_mobility_analysis_pipeline",
]
