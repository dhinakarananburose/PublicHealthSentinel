"""Tests for record-level validation, row number tracking, and quarantine logic."""

from datetime import date
import pytest
import pandas as pd

from public_health_sentinel.validator import (
    validate_mobility_records,
    validate_surveillance_records,
)


def test_validator_accepts_valid_surveillance_records():
    """Verify validation passes cleanly on compliant records."""
    records = [
        {
            "observation_date": date(2026, 1, 1),
            "region_id": "REGION_A",
            "syndrome": "Respiratory",
            "report_count": 50,
            "reporting_facility_count": 8,
            "population_denominator": 250000,
            "data_source": "STATE_DOH",
            "data_status": "real",
        },
        {
            "observation_date": date(2026, 1, 2),
            "region_id": "REGION_B",
            "syndrome": "Febrile",
            "report_count": 0,
            "reporting_facility_count": None,
            "population_denominator": None,
            "data_source": "STATE_DOH",
            "data_status": "real",
        },
    ]

    result = validate_surveillance_records(records)
    assert result.valid_count == 2
    assert result.invalid_count == 0
    assert len(result.valid_records) == 2


def test_validator_quarantines_negative_counts_and_tracks_row_number():
    """Verify negative report counts are quarantined with correct source row numbers."""
    records = [
        # Row 2 (CSV line 2)
        {
            "observation_date": "2026-01-01",
            "region_id": "REGION_A",
            "syndrome": "Respiratory",
            "report_count": 25,
            "data_source": "STATE_DOH",
            "data_status": "real",
        },
        # Row 3 (CSV line 3) - INVALID negative count
        {
            "observation_date": "2026-01-02",
            "region_id": "REGION_A",
            "syndrome": "Respiratory",
            "report_count": -5,
            "data_source": "STATE_DOH",
            "data_status": "real",
        },
        # Row 4 (CSV line 4) - INVALID empty region
        {
            "observation_date": "2026-01-03",
            "region_id": "   ",
            "syndrome": "Respiratory",
            "report_count": 10,
            "data_source": "STATE_DOH",
            "data_status": "real",
        },
        # Row 5 (CSV line 5) - INVALID unknown data status
        {
            "observation_date": "2026-01-04",
            "region_id": "REGION_A",
            "syndrome": "Respiratory",
            "report_count": 10,
            "data_source": "STATE_DOH",
            "data_status": "unverified",
        },
    ]

    result = validate_surveillance_records(records, start_row_index=2)
    assert result.valid_count == 1
    assert result.invalid_count == 3

    rejected_rows = [r.row_number for r in result.invalid_records]
    assert rejected_rows == [3, 4, 5]

    # Verify error attribution
    assert any("report_count" in err for err in result.invalid_records[0].errors)
    assert any("region_id" in err for err in result.invalid_records[1].errors)
    assert any("data_status" in err for err in result.invalid_records[2].errors)


def test_validator_quarantines_extra_fields():
    """Verify that unexpected extra fields (e.g. accidental patient_id) are rejected."""
    records = [
        {
            "observation_date": "2026-01-01",
            "region_id": "REGION_A",
            "syndrome": "Respiratory",
            "report_count": 25,
            "data_source": "STATE_DOH",
            "data_status": "real",
            "patient_mrn": "MRN-9999",
        }
    ]

    result = validate_surveillance_records(records)
    assert result.valid_count == 0
    assert result.invalid_count == 1
    assert any("patient_mrn" in err or "extra" in err.lower() for err in result.invalid_records[0].errors)


def test_validator_mobility_records():
    """Verify validation for mobility indicator records."""
    records = [
        {
            "observation_date": "2026-01-01",
            "region_id": "REGION_A",
            "mobility_metric": "transit_station_pct_change",
            "mobility_value": -14.2,
            "data_source": "GOOGLE_MOBILITY",
            "data_status": "real",
        },
        # Invalid: missing metric
        {
            "observation_date": "2026-01-01",
            "region_id": "REGION_A",
            "mobility_metric": "   ",
            "mobility_value": 0.0,
            "data_source": "GOOGLE_MOBILITY",
            "data_status": "real",
        },
    ]

    result = validate_mobility_records(records)
    assert result.valid_count == 1
    assert result.invalid_count == 1
    assert result.invalid_records[0].row_number == 3
