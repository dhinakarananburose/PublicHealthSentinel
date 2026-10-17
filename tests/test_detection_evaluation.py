"""Tests for anomaly detection evaluation metrics and spike benchmark comparisons."""

from datetime import date, timedelta
from pathlib import Path
import pytest

from public_health_sentinel.detection import (
    DetectionResult,
    EvaluationStatus,
    compare_detectors,
    evaluate_detector,
    load_injected_spikes,
)
from public_health_sentinel.synthetic_generator import InjectedSpike


def test_evaluate_detector_exact_date_metrics():
    """Verify exact calculation of TP, FP, TN, FN, precision, recall, and specificity."""
    # 10 days of surveillance: Jan 1 to Jan 10
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(10)]

    # Ground truth: Jan 3 and Jan 4 are spike days
    spikes = [
        InjectedSpike(
            observation_date=date(2026, 1, 3),
            region_id="REGION_A",
            syndrome="Respiratory",
            spike_count=100,
            duration_days=2,  # Jan 3 and Jan 4
        )
    ]

    # Detector predictions:
    # Flagged: Jan 3 (TP), Jan 5 (FP)
    # Unflagged: Jan 4 (FN), Jan 1,2,6,7,8,9,10 (7 TN)
    results = []
    for d in dates:
        is_anom = d in [date(2026, 1, 3), date(2026, 1, 5)]
        results.append(
            DetectionResult(
                observation_date=d,
                region_id="REGION_A",
                syndrome="Respiratory",
                observed_count=50,
                expected_baseline=50.0,
                anomaly_score=4.0 if is_anom else 0.5,
                detection_threshold=3.0,
                is_anomaly=is_anom,
                detection_method="mock_detector",
                history_count=7,
                evaluation_status=EvaluationStatus.EVALUATED,
            )
        )

    metrics = evaluate_detector(results, spikes)

    assert metrics.true_positives == 1   # Jan 3
    assert metrics.false_positives == 1  # Jan 5
    assert metrics.false_negatives == 1  # Jan 4
    assert metrics.true_negatives == 7   # 7 other days
    assert metrics.precision == pytest.approx(0.5, rel=1e-3)
    assert metrics.recall == pytest.approx(0.5, rel=1e-3)
    assert metrics.f1_score == pytest.approx(0.5, rel=1e-3)
    assert metrics.specificity == pytest.approx(7 / 8, rel=1e-3)
    assert metrics.false_alarm_rate_per_day == pytest.approx(1 / 8, rel=1e-3)


def test_event_level_evaluation_and_detection_delay():
    """Verify event-level detection detection and lag calculation."""
    # Multi-day event starting Jan 5 (duration 3 days: Jan 5, Jan 6, Jan 7)
    spike = InjectedSpike(
        observation_date=date(2026, 1, 5),
        region_id="REGION_A",
        syndrome="Respiratory",
        spike_count=80,
        duration_days=3,
    )

    # Detector flags only Jan 6 (delay = 1 day)
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(10)]
    results = [
        DetectionResult(
            observation_date=d,
            region_id="REGION_A",
            syndrome="Respiratory",
            observed_count=40,
            is_anomaly=(d == date(2026, 1, 6)),
            detection_method="mock_detector",
            history_count=7,
            evaluation_status=EvaluationStatus.EVALUATED,
        )
        for d in dates
    ]

    metrics = evaluate_detector(results, [spike])

    assert metrics.total_injected_events == 1
    assert metrics.detected_events_count == 1
    assert metrics.event_recall == 1.0
    assert metrics.mean_detection_delay_days == 1.0
    assert metrics.event_details[0].is_detected is True
    assert metrics.event_details[0].detection_delay_days == 1


def test_compare_detectors_structure():
    """Verify compare_detectors outputs structured comparison across methods."""
    spike = InjectedSpike(
        observation_date=date(2026, 1, 2),
        region_id="REGION_A",
        syndrome="Respiratory",
        spike_count=50,
        duration_days=1,
    )
    dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]

    res_m1 = [
        DetectionResult(
            observation_date=d,
            region_id="REGION_A",
            syndrome="Respiratory",
            observed_count=50,
            is_anomaly=(d == date(2026, 1, 2)),
            detection_method="method1",
            evaluation_status=EvaluationStatus.EVALUATED,
        )
        for d in dates
    ]
    res_m2 = [
        DetectionResult(
            observation_date=d,
            region_id="REGION_A",
            syndrome="Respiratory",
            observed_count=50,
            is_anomaly=False,
            detection_method="method2",
            evaluation_status=EvaluationStatus.EVALUATED,
        )
        for d in dates
    ]

    comparison = compare_detectors({"method1": res_m1, "method2": res_m2}, [spike])
    assert "methods_evaluated" in comparison
    assert comparison["methods_evaluated"] == ["method1", "method2"]
    assert "metrics_by_method" in comparison
    assert comparison["metrics_by_method"]["method1"]["true_positives"] == 1
    assert comparison["metrics_by_method"]["method2"]["true_positives"] == 0
    assert "limitations" in comparison


def test_load_injected_spikes_from_csv(tmp_path: Path):
    """Verify loading injected spikes from CSV file."""
    csv_file = tmp_path / "spikes.csv"
    csv_file.write_text(
        "observation_date,region_id,syndrome,spike_count,duration_days,description\n"
        "2026-02-15,REGION_A,Respiratory,95,3,Test spike\n"
    )

    spikes = load_injected_spikes(csv_file)
    assert len(spikes) == 1
    assert spikes[0].observation_date == date(2026, 2, 15)
    assert spikes[0].region_id == "REGION_A"
    assert spikes[0].duration_days == 3
    assert spikes[0].spike_count == 95
