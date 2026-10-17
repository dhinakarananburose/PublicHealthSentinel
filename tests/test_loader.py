"""Tests for CSV loading, malformed file detection, and missing value preservation."""

from pathlib import Path
import pytest
import pandas as pd

from public_health_sentinel.loader import (
    DataLoaderError,
    load_mobility_csv,
    load_surveillance_csv,
)


def test_load_valid_surveillance_csv(tmp_path: Path):
    """Verify loading a valid surveillance CSV."""
    csv_file = tmp_path / "valid_surv.csv"
    csv_file.write_text(
        "observation_date,region_id,syndrome,report_count,reporting_facility_count,population_denominator,data_source,data_status\n"
        "2026-01-01,REGION_A,Respiratory,45,8,250000,STATE_DOH,real\n"
        "2026-01-02,REGION_B,Febrile,30,,,STATE_DOH,real\n"
    )

    df = load_surveillance_csv(csv_file)
    assert len(df) == 2
    assert "report_count" in df.columns
    assert df.iloc[0]["report_count"] == 45
    # Row 2 has empty optional values, which must be NaN/None, not 0
    assert pd.isna(df.iloc[1]["reporting_facility_count"])
    assert pd.isna(df.iloc[1]["population_denominator"])


def test_load_valid_mobility_csv(tmp_path: Path):
    """Verify loading a valid mobility CSV."""
    csv_file = tmp_path / "valid_mob.csv"
    csv_file.write_text(
        "observation_date,region_id,mobility_metric,mobility_value,data_source,data_status\n"
        "2026-01-01,REGION_A,transit_station_pct_change,-12.5,GOOGLE_MOBILITY,real\n"
    )

    df = load_mobility_csv(csv_file)
    assert len(df) == 1
    assert df.iloc[0]["mobility_value"] == -12.5


def test_loader_rejects_nonexistent_file(tmp_path: Path):
    """Verify DataLoaderError when file does not exist."""
    non_existent = tmp_path / "does_not_exist.csv"
    with pytest.raises(DataLoaderError, match="does not exist"):
        load_surveillance_csv(non_existent)


def test_loader_rejects_empty_file(tmp_path: Path):
    """Verify DataLoaderError when file is 0 bytes."""
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("")
    with pytest.raises(DataLoaderError, match="completely empty"):
        load_surveillance_csv(empty_file)


def test_loader_rejects_header_only_file(tmp_path: Path):
    """Verify DataLoaderError when file contains headers but 0 rows."""
    header_only = tmp_path / "header_only.csv"
    header_only.write_text(
        "observation_date,region_id,syndrome,report_count,data_source,data_status\n"
    )
    with pytest.raises(DataLoaderError, match="contains header but 0 data rows"):
        load_surveillance_csv(header_only)


def test_loader_rejects_missing_required_columns(tmp_path: Path):
    """Verify DataLoaderError when required columns are absent."""
    missing_cols = tmp_path / "missing_cols.csv"
    missing_cols.write_text(
        "observation_date,region_id,report_count\n"
        "2026-01-01,REGION_A,45\n"
    )
    with pytest.raises(DataLoaderError, match="missing required columns"):
        load_surveillance_csv(missing_cols)
