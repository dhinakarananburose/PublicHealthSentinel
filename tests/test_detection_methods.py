"""Tests for statistical anomaly detection algorithms: Rolling MAD, EWMA, and Z-Score.

Verifies:
- Detection of clear isolated spikes
- Clean execution without false alarms on stable series
- Independent series processing per (region_id, syndrome)
- Chronological sorting guarantees
- Strict prevention of future-data leakage
- Zero-MAD and zero-std division-by-zero safeguards
- Handling of missing counts, invalid inputs, and warm-up periods
"""

from datetime import date, timedelta
import numpy as np
import pandas as pd
import pytest

from public_health_sentinel.detection import (
    EWMADetector,
    EvaluationStatus,
    RollingMADDetector,
    ZScoreDetector,
)


def _create_synthetic_series(
    counts: list[int | None],
    start_date: date = date(2026, 1, 1),
    region_id: str = "REGION_A",
    syndrome: str = "Respiratory",
) -> pd.DataFrame:
    """Helper to create a structured DataFrame for detection tests."""
    rows = []
    for idx, count in enumerate(counts):
        rows.append(
            {
                "observation_date": start_date + timedelta(days=idx),
                "region_id": region_id,
                "syndrome": syndrome,
                "report_count": count,
                "data_source": "TEST_STREAM",
                "data_status": "simulated",
            }
        )
    return pd.DataFrame(rows)


@pytest.mark.parametrize("detector_cls", [RollingMADDetector, EWMADetector, ZScoreDetector])
def test_detection_of_clear_isolated_spike(detector_cls):
    """Verify all detectors identify a prominent isolated surge following stable baseline."""
    # 20 baseline days around 50, followed by a massive surge to 250 on day 21
    counts = [50 + (i % 3) for i in range(20)] + [250] + [50 for _ in range(5)]
    df = _create_synthetic_series(counts)

    detector = detector_cls(threshold=3.0, min_history=7)
    results = detector.detect(df)

    # Day 20 (index 20) is the spike day
    spike_result = results[20]
    assert spike_result.observation_date == date(2026, 1, 21)
    assert spike_result.observed_count == 250
    assert spike_result.evaluation_status == EvaluationStatus.EVALUATED
    assert spike_result.is_anomaly is True
    assert spike_result.anomaly_score is not None and spike_result.anomaly_score > 3.0


@pytest.mark.parametrize("detector_cls", [RollingMADDetector, EWMADetector, ZScoreDetector])
def test_no_false_detection_for_stable_series(detector_cls):
    """Verify that a completely stable, non-surging series produces zero anomalies."""
    counts = [50 + (i % 2) for i in range(40)]
    df = _create_synthetic_series(counts)

    detector = detector_cls(threshold=3.0, min_history=7)
    results = detector.detect(df)

    # Filter only evaluated results (excluding warm-up period)
    evaluated = [r for r in results if r.evaluation_status == EvaluationStatus.EVALUATED]
    assert len(evaluated) > 0
    anomalies = [r for r in evaluated if r.is_anomaly is True]
    assert len(anomalies) == 0


def test_independent_region_syndrome_processing():
    """Verify that surges in one series do not contaminate baselines in another series."""
    # REGION_A has massive surge on day 15; REGION_B remains quiet
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(25)]

    rows_a = [
        {"observation_date": d, "region_id": "REGION_A", "syndrome": "Respiratory", "report_count": 300 if idx == 15 else 40}
        for idx, d in enumerate(dates)
    ]
    rows_b = [
        {"observation_date": d, "region_id": "REGION_B", "syndrome": "Respiratory", "report_count": 40}
        for idx, d in enumerate(dates)
    ]
    df = pd.DataFrame(rows_a + rows_b)

    detector = RollingMADDetector(window_size=14, threshold=3.0, min_history=7)
    results = detector.detect(df)

    # Check REGION_B day 15
    res_b_day15 = [
        r for r in results
        if r.region_id == "REGION_B" and r.observation_date == date(2026, 1, 16)
    ][0]
    assert res_b_day15.observed_count == 40
    assert res_b_day15.is_anomaly is False

    # Check REGION_A day 15
    res_a_day15 = [
        r for r in results
        if r.region_id == "REGION_A" and r.observation_date == date(2026, 1, 16)
    ][0]
    assert res_a_day15.observed_count == 300
    assert res_a_day15.is_anomaly is True


def test_chronological_sorting_guarantee():
    """Verify that passing shuffled dates is sorted chronologically before evaluation."""
    counts = [40, 42, 41, 40, 43, 40, 41, 40, 150]
    df = _create_synthetic_series(counts)

    # Shuffle the DataFrame rows randomly
    shuffled_df = df.sample(frac=1.0, random_state=42).copy()

    detector = ZScoreDetector(window_size=7, threshold=2.5, min_history=5)
    results = detector.detect(shuffled_df)

    # Results must be strictly in chronological order
    result_dates = [r.observation_date for r in results]
    assert result_dates == sorted(result_dates)
    assert results[-1].observed_count == 150
    assert results[-1].is_anomaly is True


@pytest.mark.parametrize("detector_cls", [RollingMADDetector, EWMADetector, ZScoreDetector])
def test_no_future_data_leakage(detector_cls):
    """MANDATORY: Changing future observations must NOT alter past baselines or scores."""
    base_counts = [50 + (i % 3) for i in range(20)]

    # Version 1: followed by normal future counts
    counts_v1 = base_counts + [52, 51, 50, 53, 50]
    # Version 2: followed by a catastrophic massive surge in the future
    counts_v2 = base_counts + [9999, 9999, 9999, 9999, 9999]

    df1 = _create_synthetic_series(counts_v1)
    df2 = _create_synthetic_series(counts_v2)

    detector1 = detector_cls(threshold=3.0, min_history=7)
    detector2 = detector_cls(threshold=3.0, min_history=7)

    res1 = detector1.detect(df1)
    res2 = detector2.detect(df2)

    # Check all evaluations up to day 20 (the period before the change)
    for idx in range(20):
        r1 = res1[idx]
        r2 = res2[idx]
        assert r1.observation_date == r2.observation_date
        assert r1.expected_baseline == r2.expected_baseline
        assert r1.anomaly_score == r2.anomaly_score
        assert r1.is_anomaly == r2.is_anomaly
        assert r1.evaluation_status == r2.evaluation_status


def test_zero_mad_safeguard():
    """Verify that a series with constant historical counts (MAD=0) does not divide by zero."""
    # 15 days of identical count 30 -> MAD is 0
    counts = [30] * 15 + [100]
    df = _create_synthetic_series(counts)

    detector = RollingMADDetector(window_size=10, threshold=3.0, min_history=5)
    results = detector.detect(df)

    # Prior days with count 30 should have score 0
    assert results[10].anomaly_score == 0.0
    assert results[10].is_anomaly is False

    # Day 16 with count 100 should be evaluated cleanly without ZeroDivisionError
    spike_res = results[15]
    assert spike_res.observed_count == 100
    assert spike_res.is_anomaly is True
    assert spike_res.anomaly_score is not None and spike_res.anomaly_score > 3.0


def test_zero_standard_deviation_safeguard():
    """Verify that a series with constant counts (std=0) does not divide by zero in ZScore."""
    counts = [25] * 15 + [90]
    df = _create_synthetic_series(counts)

    detector = ZScoreDetector(window_size=10, threshold=3.0, min_history=5)
    results = detector.detect(df)

    assert results[10].anomaly_score == 0.0
    assert results[10].is_anomaly is False

    spike_res = results[15]
    assert spike_res.observed_count == 90
    assert spike_res.is_anomaly is True
    assert spike_res.anomaly_score is not None and spike_res.anomaly_score > 3.0


def test_insufficient_history_handling():
    """Verify observations during warm-up are marked INSUFFICIENT_HISTORY and not normal."""
    counts = [40, 42, 45, 41, 43]  # Only 5 observations, but min_history is 7
    df = _create_synthetic_series(counts)

    detector = RollingMADDetector(min_history=7)
    results = detector.detect(df)

    for r in results:
        assert r.evaluation_status == EvaluationStatus.INSUFFICIENT_HISTORY
        assert r.is_anomaly is None
        assert r.expected_baseline is None
        assert r.anomaly_score is None


def test_missing_count_and_invalid_input_handling():
    """Verify handling of missing counts (NaN) and invalid negative counts."""
    counts: list[int | None] = [50] * 10 + [None, -15, 52]
    df = _create_synthetic_series(counts)

    detector = RollingMADDetector(window_size=7, min_history=5)
    results = detector.detect(df)

    # Index 10 is None
    res_none = results[10]
    assert res_none.evaluation_status == EvaluationStatus.MISSING_COUNT
    assert res_none.is_anomaly is None

    # Index 11 is -15
    res_invalid = results[11]
    assert res_invalid.evaluation_status == EvaluationStatus.INVALID_INPUT
    assert res_invalid.is_anomaly is None

    # Index 12 is valid 52, should be evaluated normally
    res_valid = results[12]
    assert res_valid.evaluation_status == EvaluationStatus.EVALUATED
    assert res_valid.observed_count == 52
    assert res_valid.is_anomaly is False
