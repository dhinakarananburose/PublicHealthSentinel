"""Anomaly detection package for PublicHealthSentinel.

Exports:
- Baseline models: EvaluationStatus, DetectionResult, BaseAnomalyDetector
- Detectors: RollingMADDetector, EWMADetector, ZScoreDetector
- Evaluation: evaluate_detector, compare_detectors, load_injected_spikes, EvaluationMetrics
- Pipeline: run_detection_pipeline, DetectionPipelineResult
"""

from public_health_sentinel.detection.baseline import (
    BaseAnomalyDetector,
    DetectionResult,
    EvaluationStatus,
)
from public_health_sentinel.detection.evaluation import (
    EvaluationMetrics,
    EventEvaluationResult,
    compare_detectors,
    evaluate_detector,
    load_injected_spikes,
)
from public_health_sentinel.detection.ewma import EWMADetector
from public_health_sentinel.detection.pipeline import (
    DetectionPipelineResult,
    run_detection_pipeline,
)
from public_health_sentinel.detection.rolling_mad import RollingMADDetector
from public_health_sentinel.detection.zscore import ZScoreDetector

__all__ = [
    "BaseAnomalyDetector",
    "DetectionPipelineResult",
    "DetectionResult",
    "EWMADetector",
    "EvaluationMetrics",
    "EvaluationStatus",
    "EventEvaluationResult",
    "RollingMADDetector",
    "ZScoreDetector",
    "compare_detectors",
    "evaluate_detector",
    "load_injected_spikes",
    "run_detection_pipeline",
]
