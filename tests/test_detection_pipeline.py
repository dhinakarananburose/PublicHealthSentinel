"""Integration tests for the anomaly detection pipeline and CLI commands."""

from pathlib import Path
import json
import pytest
import pandas as pd

from public_health_sentinel.cli import main as main_cli
from public_health_sentinel.detection.cli import main as detection_cli
from public_health_sentinel.detection.pipeline import run_detection_pipeline
from public_health_sentinel.pipeline import run_pipeline


@pytest.fixture
def prepared_processed_data(tmp_path: Path):
    """Fixture that generates standard processed surveillance data in tmp_path."""
    proc_dir = tmp_path / "processed"
    synth_dir = tmp_path / "synthetic"

    run_pipeline(
        output_dir=proc_dir,
        synthetic_dir=synth_dir,
        duration_days=60,
        seed=42,
        inject_spikes=True,
    )
    return {
        "proc_dir": proc_dir,
        "synth_dir": synth_dir,
        "surv_csv": proc_dir / "surveillance_observations.csv",
        "spikes_csv": synth_dir / "synthetic_injected_spikes.csv",
    }


def test_run_detection_pipeline_all_methods(prepared_processed_data):
    """Verify running detection across all methods produces expected artifacts and reports."""
    paths = prepared_processed_data
    out_dir = paths["proc_dir"]

    result = run_detection_pipeline(
        surveillance_file=paths["surv_csv"],
        spikes_file=paths["spikes_csv"],
        output_dir=out_dir,
        method="all",
        window_size=14,
        threshold=3.0,
        min_history=7,
    )

    assert result.status == "SUCCESS"
    assert set(result.methods_run) == {"rolling_mad", "ewma", "zscore"}
    assert result.total_evaluated_observations > 0

    # Verify output files
    assert (out_dir / "detection_results.csv").exists()
    assert (out_dir / "detection_results_rolling_mad.csv").exists()
    assert (out_dir / "detection_results_ewma.csv").exists()
    assert (out_dir / "detection_results_zscore.csv").exists()
    assert (out_dir / "anomalies_summary.csv").exists()
    assert (out_dir / "method_comparison_report.json").exists()
    assert (out_dir / "spike_evaluation_report.json").exists()

    # Verify comparison report JSON
    with open(out_dir / "method_comparison_report.json", "r", encoding="utf-8") as f:
        comp_data = json.load(f)
    assert "metrics_by_method" in comp_data
    assert "rolling_mad" in comp_data["metrics_by_method"]
    assert "ewma" in comp_data["metrics_by_method"]
    assert "zscore" in comp_data["metrics_by_method"]


def test_run_detection_pipeline_single_method(prepared_processed_data):
    """Verify running a single detector (e.g. rolling_mad) cleanly."""
    paths = prepared_processed_data
    out_dir = paths["proc_dir"]

    result = run_detection_pipeline(
        surveillance_file=paths["surv_csv"],
        spikes_file=paths["spikes_csv"],
        output_dir=out_dir,
        method="rolling_mad",
        window_size=21,
        threshold=3.0,
    )

    assert result.status == "SUCCESS"
    assert result.methods_run == ["rolling_mad"]
    assert (out_dir / "detection_results_rolling_mad.csv").exists()


def test_detection_cli_entry_point(prepared_processed_data):
    """Verify execution of the detection CLI entry point."""
    paths = prepared_processed_data

    exit_code = detection_cli([
        "--method", "zscore",
        "--surveillance-file", str(paths["surv_csv"]),
        "--spikes-file", str(paths["spikes_csv"]),
        "--output-dir", str(paths["proc_dir"]),
        "--threshold", "3.0",
    ])

    assert exit_code == 0
    assert (paths["proc_dir"] / "detection_results_zscore.csv").exists()


def test_main_cli_detection_routing(prepared_processed_data):
    """Verify that python -m public_health_sentinel.cli --detect routes to detection."""
    paths = prepared_processed_data

    exit_code = main_cli([
        "--detect",
        "--method", "ewma",
        "--surveillance-file", str(paths["surv_csv"]),
        "--spikes-file", str(paths["spikes_csv"]),
        "--output-dir", str(paths["proc_dir"]),
    ])

    assert exit_code == 0
    assert (paths["proc_dir"] / "detection_results_ewma.csv").exists()


def test_main_cli_preserves_phase2_behavior(tmp_path: Path):
    """Verify that python -m public_health_sentinel.cli without --detect preserves Phase 2."""
    out_dir = str(tmp_path / "proc_p2")
    synth_dir = str(tmp_path / "synth_p2")

    exit_code = main_cli([
        "--seed", "88",
        "--duration-days", "10",
        "--output-dir", out_dir,
        "--synthetic-dir", synth_dir,
    ])

    assert exit_code == 0
    assert (Path(out_dir) / "surveillance_observations.csv").exists()
    assert (Path(out_dir) / "mobility_indicators.csv").exists()
