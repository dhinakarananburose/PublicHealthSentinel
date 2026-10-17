"""Tests for data quality reporting, duplicate detection, and missing observation dates."""

from datetime import date
from public_health_sentinel.quality import (
    assess_mobility_quality,
    assess_surveillance_quality,
)
from public_health_sentinel.schemas import (
    AggregatedObservation,
    DataStatus,
    MobilityIndicator,
)


def test_surveillance_duplicate_key_detection():
    """Verify natural candidate key (date + region + syndrome) duplicate detection.

    Ensures duplicates are counted and reported, NEVER automatically summed.
    """
    obs1 = AggregatedObservation(
        observation_date=date(2026, 1, 1),
        region_id="REGION_A",
        syndrome="Respiratory",
        report_count=20,
        data_source="STATE_DOH",
        data_status=DataStatus.REAL,
    )
    # Duplicate key with different count (e.g. conflicting ingestion batch)
    obs2 = AggregatedObservation(
        observation_date=date(2026, 1, 1),
        region_id="REGION_A",
        syndrome="Respiratory",
        report_count=25,
        data_source="CDC_NHSN",
        data_status=DataStatus.REAL,
    )
    obs3 = AggregatedObservation(
        observation_date=date(2026, 1, 2),
        region_id="REGION_A",
        syndrome="Respiratory",
        report_count=18,
        data_source="STATE_DOH",
        data_status=DataStatus.REAL,
    )

    report = assess_surveillance_quality([obs1, obs2, obs3])
    assert report.total_input_records == 3
    assert report.valid_records == 3
    assert report.duplicate_key_count == 1
    assert len(report.duplicate_keys) == 1
    assert report.duplicate_keys[0]["region_id"] == "REGION_A"
    assert report.duplicate_keys[0]["occurrences"] == 2


def test_surveillance_missing_observation_dates():
    """Verify identification of missing dates across the date span."""
    # Jan 1 and Jan 3 are present, Jan 2 is missing
    obs1 = AggregatedObservation(
        observation_date=date(2026, 1, 1),
        region_id="REGION_A",
        syndrome="Respiratory",
        report_count=20,
        data_source="STATE_DOH",
        data_status=DataStatus.REAL,
    )
    obs2 = AggregatedObservation(
        observation_date=date(2026, 1, 3),
        region_id="REGION_A",
        syndrome="Respiratory",
        report_count=22,
        data_source="STATE_DOH",
        data_status=DataStatus.REAL,
    )

    report = assess_surveillance_quality([obs1, obs2])
    assert report.date_coverage["span_days"] == 3
    assert report.date_coverage["distinct_observed_dates_count"] == 2
    assert report.missing_observation_dates_count == 1
    assert "2026-01-02" in report.missing_observation_dates


def test_missing_values_by_field_reported():
    """Verify missing denominators and facility counts are counted accurately."""
    obs1 = AggregatedObservation(
        observation_date=date(2026, 1, 1),
        region_id="REGION_A",
        syndrome="Respiratory",
        report_count=20,
        reporting_facility_count=None,
        population_denominator=None,
        data_source="STATE_DOH",
        data_status=DataStatus.REAL,
    )
    obs2 = AggregatedObservation(
        observation_date=date(2026, 1, 2),
        region_id="REGION_A",
        syndrome="Respiratory",
        report_count=22,
        reporting_facility_count=5,
        population_denominator=None,
        data_source="STATE_DOH",
        data_status=DataStatus.REAL,
    )

    report = assess_surveillance_quality([obs1, obs2])
    assert report.missing_values_by_field["reporting_facility_count"] == 1
    assert report.missing_values_by_field["population_denominator"] == 2


def test_mobility_duplicate_key_detection():
    """Verify mobility duplicate candidate key (date + region + metric) detection."""
    ind1 = MobilityIndicator(
        observation_date=date(2026, 1, 1),
        region_id="REGION_A",
        mobility_metric="workplace_pct_change",
        mobility_value=-10.5,
        data_source="PROVIDER_A",
        data_status=DataStatus.REAL,
    )
    ind2 = MobilityIndicator(
        observation_date=date(2026, 1, 1),
        region_id="REGION_A",
        mobility_metric="workplace_pct_change",
        mobility_value=-11.0,
        data_source="PROVIDER_B",
        data_status=DataStatus.REAL,
    )

    report = assess_mobility_quality([ind1, ind2])
    assert report.duplicate_key_count == 1
    assert report.duplicate_keys[0]["mobility_metric"] == "workplace_pct_change"
