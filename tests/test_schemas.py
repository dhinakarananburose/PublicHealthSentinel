"""Tests for data schemas, provenance classification, and validation constraints."""

from datetime import date
import pytest
from pydantic import ValidationError

from public_health_sentinel.schemas import (
    AggregatedObservation,
    DataStatus,
    MobilityIndicator,
)


def test_valid_aggregated_observation_full():
    """Verify an observation with all optional fields provided."""
    obs = AggregatedObservation(
        observation_date=date(2026, 10, 1),
        region_id="REGION_US_NY",
        syndrome="respiratory",
        report_count=142,
        reporting_facility_count=12,
        population_denominator=500_000,
        data_source="STATE_DOH",
        data_status=DataStatus.REAL,
    )

    assert obs.observation_date == date(2026, 10, 1)
    assert obs.region_id == "REGION_US_NY"
    assert obs.syndrome == "respiratory"
    assert obs.report_count == 142
    assert obs.reporting_facility_count == 12
    assert obs.population_denominator == 500_000
    assert obs.data_source == "STATE_DOH"
    assert obs.data_status == DataStatus.REAL
    assert obs.ingestion_timestamp is not None
    assert obs.crude_incidence_per_100k == pytest.approx(28.4, rel=1e-2)


def test_missing_denominators_remain_none():
    """Verify that optional counts remain None and are NOT coerced to zero.

    Treating unknown denominators or facility counts as 0 corrupts rates.
    """
    obs = AggregatedObservation(
        observation_date=date(2026, 10, 2),
        region_id="REGION_US_CA",
        syndrome="influenza_like_illness",
        report_count=45,
        reporting_facility_count=None,
        population_denominator=None,
        data_source="SYNTHETIC_GENERATOR",
        data_status=DataStatus.SIMULATED,
    )

    assert obs.reporting_facility_count is None
    assert obs.population_denominator is None
    assert obs.crude_incidence_per_100k is None


def test_negative_report_count_rejected():
    """Verify that negative report counts trigger validation errors."""
    with pytest.raises(ValidationError) as exc_info:
        AggregatedObservation(
            observation_date=date(2026, 10, 3),
            region_id="REGION_US_TX",
            syndrome="gastrointestinal",
            report_count=-1,
            data_source="CDC_NHSN",
            data_status=DataStatus.REAL,
        )
    assert "report_count" in str(exc_info.value)


def test_blank_string_identifiers_rejected():
    """Verify that empty or whitespace-only identifiers are rejected."""
    with pytest.raises(ValidationError):
        AggregatedObservation(
            observation_date=date(2026, 10, 3),
            region_id="   ",
            syndrome="fever",
            report_count=10,
            data_source="CDC_NHSN",
            data_status=DataStatus.REAL,
        )

    with pytest.raises(ValidationError):
        AggregatedObservation(
            observation_date=date(2026, 10, 3),
            region_id="REGION_US_FL",
            syndrome="   ",
            report_count=10,
            data_source="CDC_NHSN",
            data_status=DataStatus.REAL,
        )


def test_invalid_data_status_rejected():
    """Verify that unknown provenance categories are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        AggregatedObservation(
            observation_date=date(2026, 10, 3),
            region_id="REGION_US_WA",
            syndrome="respiratory",
            report_count=10,
            data_source="CDC_NHSN",
            data_status="unverified_status",  # type: ignore[arg-type]
        )
    assert "data_status" in str(exc_info.value)


def test_extra_fields_forbidden():
    """Verify that unknown fields (e.g. accidental patient IDs) are strictly forbidden."""
    with pytest.raises(ValidationError) as exc_info:
        AggregatedObservation(
            observation_date=date(2026, 10, 3),
            region_id="REGION_US_MA",
            syndrome="respiratory",
            report_count=10,
            data_source="CDC_NHSN",
            data_status=DataStatus.REAL,
            patient_id="12345",  # type: ignore[call-arg]
        )
    assert "extra_forbidden" in str(exc_info.value) or "Extra inputs are not permitted" in str(exc_info.value)


def test_valid_mobility_indicator():
    """Verify mobility indicator instantiation and validation."""
    mobility = MobilityIndicator(
        observation_date=date(2026, 10, 1),
        region_id="REGION_US_NY",
        mobility_metric="transit_station_pct_change",
        mobility_value=-15.4,
        data_source="GOOGLE_COMMUNITY_MOBILITY",
        data_status=DataStatus.REAL,
    )

    assert mobility.observation_date == date(2026, 10, 1)
    assert mobility.region_id == "REGION_US_NY"
    assert mobility.mobility_metric == "transit_station_pct_change"
    assert mobility.mobility_value == -15.4
    assert mobility.data_status == DataStatus.REAL


def test_empty_mobility_metric_rejected():
    """Verify that blank mobility metric strings fail validation."""
    with pytest.raises(ValidationError):
        MobilityIndicator(
            observation_date=date(2026, 10, 1),
            region_id="REGION_US_NY",
            mobility_metric="   ",
            mobility_value=0.0,
            data_source="GOOGLE_COMMUNITY_MOBILITY",
            data_status=DataStatus.REAL,
        )
