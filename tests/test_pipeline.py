"""Tests for the end-to-end data engineering pipeline and CLI execution."""

from pathlib import Path
import json
import pytest
import pandas as pd

from public_health_sentinel.cli import main
from public_health_sentinel.pipeline import run_pipeline


def test_end_to_end_pipeline_with_synthetic_generation(tmp_path: Path):
    """Verify complete pipeline execution using synthetic data generation."""
    out_dir = tmp_path / "processed"
    synth_dir = tmp_path / "synthetic"

    result = run_pipeline(
        output_dir=out_dir,
        synthetic_dir=synth_dir,
        seed=42,
        duration_days=10,
        inject_spikes=True,
    )

    assert result.status == "SUCCESS"
    assert result.surveillance_valid_count > 0
    assert result.surveillance_invalid_count == 0
    assert result.mobility_valid_count > 0

    # Verify generated files exist
    assert (out_dir / "surveillance_observations.csv").exists()
    assert (out_dir / "mobility_indicators.csv").exists()
    assert (out_dir / "quality_report.json").exists()
    assert (synth_dir / "synthetic_surveillance.csv").exists()
    assert (synth_dir / "synthetic_mobility.csv").exists()

    # Verify quality report is valid JSON
    with open(out_dir / "quality_report.json", "r", encoding="utf-8") as f:
        report_data = json.load(f)
    assert "surveillance" in report_data
    assert "mobility" in report_data
    assert report_data["surveillance"]["valid_records"] == result.surveillance_valid_count


def test_end_to_end_pipeline_with_csv_inputs(tmp_path: Path):
    """Verify running the pipeline against externally loaded CSV input files."""
    surv_csv = tmp_path / "raw_surveillance.csv"
    mob_csv = tmp_path / "raw_mobility.csv"
    out_dir = tmp_path / "processed"

    surv_csv.write_text(
        "observation_date,region_id,syndrome,report_count,reporting_facility_count,population_denominator,data_source,data_status\n"
        "2026-01-01,REGION_A,Respiratory,35,8,250000,STATE_DOH,real\n"
        "2026-01-02,REGION_A,Respiratory,42,8,250000,STATE_DOH,real\n"
    )

    mob_csv.write_text(
        "observation_date,region_id,mobility_metric,mobility_value,data_source,data_status\n"
        "2026-01-01,REGION_A,transit_station_pct_change,-10.0,GOOGLE_MOBILITY,real\n"
        "2026-01-02,REGION_A,transit_station_pct_change,-12.0,GOOGLE_MOBILITY,real\n"
    )

    result = run_pipeline(
        surveillance_source=surv_csv,
        mobility_source=mob_csv,
        output_dir=out_dir,
    )

    assert result.status == "SUCCESS"
    assert result.surveillance_valid_count == 2
    assert result.mobility_valid_count == 2

    # Confirm raw input was NOT overwritten or modified
    assert surv_csv.exists()
    assert "2026-01-01,REGION_A,Respiratory,35" in surv_csv.read_text()


def test_pipeline_quarantine_writing_when_invalid_records_present(tmp_path: Path):
    """Verify invalid records are routed to quarantine CSVs and not discarded silently."""
    surv_csv = tmp_path / "mixed_surveillance.csv"
    mob_csv = tmp_path / "valid_mobility.csv"
    out_dir = tmp_path / "processed"

    # Row 2 is valid, Row 3 has negative count (invalid)
    surv_csv.write_text(
        "observation_date,region_id,syndrome,report_count,data_source,data_status\n"
        "2026-01-01,REGION_A,Respiratory,35,STATE_DOH,real\n"
        "2026-01-02,REGION_A,Respiratory,-10,STATE_DOH,real\n"
    )

    mob_csv.write_text(
        "observation_date,region_id,mobility_metric,mobility_value,data_source,data_status\n"
        "2026-01-01,REGION_A,transit_station_pct_change,-10.0,GOOGLE_MOBILITY,real\n"
    )

    result = run_pipeline(
        surveillance_source=surv_csv,
        mobility_source=mob_csv,
        output_dir=out_dir,
    )

    assert result.surveillance_valid_count == 1
    assert result.surveillance_invalid_count == 1

    quarantine_file = out_dir / "surveillance_quarantine.csv"
    assert quarantine_file.exists()

    quarantine_df = pd.read_csv(quarantine_file)
    assert len(quarantine_df) == 1
    assert quarantine_df.iloc[0]["row_number"] == 3
    assert "report_count" in quarantine_df.iloc[0]["errors"]


def test_no_leftover_temporary_files(tmp_path: Path):
    """Verify that atomic write temp files (.tmp_*) are cleaned up."""
    out_dir = tmp_path / "processed"
    synth_dir = tmp_path / "synthetic"

    run_pipeline(
        output_dir=out_dir,
        synthetic_dir=synth_dir,
        duration_days=5,
    )

    tmp_files = list(out_dir.glob(".tmp_*")) + list(synth_dir.glob(".tmp_*"))
    assert len(tmp_files) == 0


def test_cli_execution_success(tmp_path: Path):
    """Verify the CLI entry point runs with exit code 0."""
    out_dir = str(tmp_path / "proc")
    synth_dir = str(tmp_path / "synth")

    exit_code = main([
        "--seed", "99",
        "--duration-days", "5",
        "--output-dir", out_dir,
        "--synthetic-dir", synth_dir,
    ])

    assert exit_code == 0
    assert (Path(out_dir) / "surveillance_observations.csv").exists()
