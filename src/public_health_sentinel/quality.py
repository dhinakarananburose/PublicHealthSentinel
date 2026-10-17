"""Data quality evaluation for surveillance observations and mobility indicators.

Calculates comprehensive data-quality metrics:
- Record counts (input, valid, invalid)
- Natural candidate key duplicate detection (without auto-summing)
- Missing observation dates (distinguishable from zero counts)
- Missing-value frequencies for optional fields
- Region, syndrome, and metric coverage
- Date span and completeness
- Provenance status distribution
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any, Sequence

from public_health_sentinel.schemas import (
    AggregatedObservation,
    MobilityIndicator,
)
from public_health_sentinel.validator import RejectedRecord


@dataclass
class SurveillanceQualityReport:
    """Structured data quality evaluation for syndromic surveillance records."""

    total_input_records: int
    valid_records: int
    invalid_records: int
    duplicate_key_count: int
    duplicate_keys: list[dict[str, Any]]
    missing_observation_dates_count: int
    missing_observation_dates: list[str]
    missing_values_by_field: dict[str, int]
    region_coverage: dict[str, Any]
    syndrome_coverage: dict[str, Any]
    date_coverage: dict[str, Any]
    source_summary: dict[str, int]
    data_status_summary: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


@dataclass
class MobilityQualityReport:
    """Structured data quality evaluation for population mobility records."""

    total_input_records: int
    valid_records: int
    invalid_records: int
    duplicate_key_count: int
    duplicate_keys: list[dict[str, Any]]
    missing_observation_dates_count: int
    missing_observation_dates: list[str]
    missing_values_by_field: dict[str, int]
    region_coverage: dict[str, Any]
    metric_coverage: dict[str, Any]
    date_coverage: dict[str, Any]
    source_summary: dict[str, int]
    data_status_summary: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


def assess_surveillance_quality(
    valid_records: Sequence[AggregatedObservation],
    invalid_records: Sequence[RejectedRecord] = (),
    expected_regions: Sequence[str] | None = None,
    expected_syndromes: Sequence[str] | None = None,
    expected_start_date: date | None = None,
    expected_end_date: date | None = None,
) -> SurveillanceQualityReport:
    """Assess surveillance dataset quality and produce a structured audit report.

    Candidate Natural Key: (observation_date, region_id, syndrome).
    Duplicates are flagged and counted explicitly, NEVER automatically summed.

    Args:
        valid_records: Sequence of validated AggregatedObservation models.
        invalid_records: Sequence of RejectedRecord instances quarantined by validator.
        expected_regions: Optional list of expected regions to measure coverage against.
        expected_syndromes: Optional list of expected syndromes.
        expected_start_date: Optional expected window start date.
        expected_end_date: Optional expected window end date.

    Returns:
        SurveillanceQualityReport containing full audit statistics.
    """
    total_input = len(valid_records) + len(invalid_records)

    # 1. Natural key duplicates
    key_counter: Counter[tuple[date, str, str]] = Counter(
        (obs.observation_date, obs.region_id, obs.syndrome) for obs in valid_records
    )
    duplicate_entries = [
        {
            "observation_date": k[0].isoformat(),
            "region_id": k[1],
            "syndrome": k[2],
            "occurrences": count,
        }
        for k, count in key_counter.items()
        if count > 1
    ]
    duplicate_key_count = sum(count - 1 for count in key_counter.values() if count > 1)

    # 2. Date and completeness analysis
    observed_dates = sorted(set(obs.observation_date for obs in valid_records))
    observed_regions = sorted(set(obs.region_id for obs in valid_records))
    observed_syndromes = sorted(set(obs.syndrome for obs in valid_records))

    start_dt = expected_start_date or (observed_dates[0] if observed_dates else None)
    end_dt = expected_end_date or (observed_dates[-1] if observed_dates else None)

    missing_dates: list[str] = []
    span_days = 0

    if start_dt and end_dt and start_dt <= end_dt:
        span_days = (end_dt - start_dt).days + 1
        observed_dates_set = set(observed_dates)
        cur = start_dt
        while cur <= end_dt:
            if cur not in observed_dates_set:
                missing_dates.append(cur.isoformat())
            cur += timedelta(days=1)

    # 3. Missing values in optional fields
    missing_facility_count = sum(1 for obs in valid_records if obs.reporting_facility_count is None)
    missing_denominator_count = sum(1 for obs in valid_records if obs.population_denominator is None)

    # 4. Coverage details
    missing_from_expected_regions = []
    if expected_regions:
        missing_from_expected_regions = sorted(set(expected_regions) - set(observed_regions))

    missing_from_expected_syndromes = []
    if expected_syndromes:
        missing_from_expected_syndromes = sorted(set(expected_syndromes) - set(observed_syndromes))

    # 5. Summaries
    source_counts = dict(Counter(obs.data_source for obs in valid_records))
    status_counts = dict(Counter(obs.data_status.value for obs in valid_records))

    return SurveillanceQualityReport(
        total_input_records=total_input,
        valid_records=len(valid_records),
        invalid_records=len(invalid_records),
        duplicate_key_count=duplicate_key_count,
        duplicate_keys=duplicate_entries,
        missing_observation_dates_count=len(missing_dates),
        missing_observation_dates=missing_dates,
        missing_values_by_field={
            "reporting_facility_count": missing_facility_count,
            "population_denominator": missing_denominator_count,
        },
        region_coverage={
            "distinct_count": len(observed_regions),
            "regions": observed_regions,
            "missing_from_expected": missing_from_expected_regions,
        },
        syndrome_coverage={
            "distinct_count": len(observed_syndromes),
            "syndromes": observed_syndromes,
            "missing_from_expected": missing_from_expected_syndromes,
        },
        date_coverage={
            "start_date": start_dt.isoformat() if start_dt else None,
            "end_date": end_dt.isoformat() if end_dt else None,
            "span_days": span_days,
            "distinct_observed_dates_count": len(observed_dates),
        },
        source_summary=source_counts,
        data_status_summary=status_counts,
    )


def assess_mobility_quality(
    valid_records: Sequence[MobilityIndicator],
    invalid_records: Sequence[RejectedRecord] = (),
    expected_regions: Sequence[str] | None = None,
    expected_metrics: Sequence[str] | None = None,
    expected_start_date: date | None = None,
    expected_end_date: date | None = None,
) -> MobilityQualityReport:
    """Assess mobility dataset quality and produce a structured audit report.

    Candidate Natural Key: (observation_date, region_id, mobility_metric).
    Duplicates are counted explicitly, NEVER automatically summed.
    """
    total_input = len(valid_records) + len(invalid_records)

    # 1. Natural key duplicates
    key_counter: Counter[tuple[date, str, str]] = Counter(
        (ind.observation_date, ind.region_id, ind.mobility_metric) for ind in valid_records
    )
    duplicate_entries = [
        {
            "observation_date": k[0].isoformat(),
            "region_id": k[1],
            "mobility_metric": k[2],
            "occurrences": count,
        }
        for k, count in key_counter.items()
        if count > 1
    ]
    duplicate_key_count = sum(count - 1 for count in key_counter.values() if count > 1)

    # 2. Date and completeness analysis
    observed_dates = sorted(set(ind.observation_date for ind in valid_records))
    observed_regions = sorted(set(ind.region_id for ind in valid_records))
    observed_metrics = sorted(set(ind.mobility_metric for ind in valid_records))

    start_dt = expected_start_date or (observed_dates[0] if observed_dates else None)
    end_dt = expected_end_date or (observed_dates[-1] if observed_dates else None)

    missing_dates: list[str] = []
    span_days = 0

    if start_dt and end_dt and start_dt <= end_dt:
        span_days = (end_dt - start_dt).days + 1
        observed_dates_set = set(observed_dates)
        cur = start_dt
        while cur <= end_dt:
            if cur not in observed_dates_set:
                missing_dates.append(cur.isoformat())
            cur += timedelta(days=1)

    missing_from_expected_regions = []
    if expected_regions:
        missing_from_expected_regions = sorted(set(expected_regions) - set(observed_regions))

    missing_from_expected_metrics = []
    if expected_metrics:
        missing_from_expected_metrics = sorted(set(expected_metrics) - set(observed_metrics))

    source_counts = dict(Counter(ind.data_source for ind in valid_records))
    status_counts = dict(Counter(ind.data_status.value for ind in valid_records))

    return MobilityQualityReport(
        total_input_records=total_input,
        valid_records=len(valid_records),
        invalid_records=len(invalid_records),
        duplicate_key_count=duplicate_key_count,
        duplicate_keys=duplicate_entries,
        missing_observation_dates_count=len(missing_dates),
        missing_observation_dates=missing_dates,
        missing_values_by_field={},
        region_coverage={
            "distinct_count": len(observed_regions),
            "regions": observed_regions,
            "missing_from_expected": missing_from_expected_regions,
        },
        metric_coverage={
            "distinct_count": len(observed_metrics),
            "metrics": observed_metrics,
            "missing_from_expected": missing_from_expected_metrics,
        },
        date_coverage={
            "start_date": start_dt.isoformat() if start_dt else None,
            "end_date": end_dt.isoformat() if end_dt else None,
            "span_days": span_days,
            "distinct_observed_dates_count": len(observed_dates),
        },
        source_summary=source_counts,
        data_status_summary=status_counts,
    )
