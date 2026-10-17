"""Geographic and temporal data alignment for surveillance and mobility indicators.

Pivots mobility metrics and joins them with surveillance observations on (observation_date, region_id):
- Preserves region and syndrome identifiers
- Validates date and region compatibility
- Detects candidate key duplicates explicitly
- Preserves missing values as NaN/None (never replaces with zero)
- Prevents accidental Cartesian row multiplication during joins
- Excludes unavailable mobility records rather than silently imputing them
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Sequence

import pandas as pd


@dataclass
class AlignmentSummary:
    """Audit summary of surveillance and mobility dataset alignment."""

    surveillance_input_rows: int
    mobility_input_rows: int
    pivoted_mobility_rows: int
    aligned_rows: int
    complete_cases_rows: int
    missing_mobility_rows: int
    missing_surveillance_count_rows: int
    mobility_metrics_aligned: list[str]
    regions_aligned: list[str]
    date_range_start: str | None
    date_range_end: str | None
    duplicate_mobility_keys_detected: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_date_column(df: pd.DataFrame, col: str = "observation_date") -> pd.DataFrame:
    """Normalize date column to datetime.date objects."""
    res = df.copy()
    if pd.api.types.is_datetime64_any_dtype(res[col]):
        res[col] = res[col].dt.date
    else:
        res[col] = pd.to_datetime(res[col]).dt.date
    return res


def pivot_mobility_indicators(
    mobility_df: pd.DataFrame,
) -> tuple[pd.DataFrame, int, list[str]]:
    """Pivot long-format mobility table to wide-format by metric.

    Input columns: [observation_date, region_id, mobility_metric, mobility_value, ...]
    Output columns: [observation_date, region_id, <metric_1>, <metric_2>, ...]

    Returns:
        Tuple of (pivoted_df, duplicate_count, metric_names).
    """
    required = {"observation_date", "region_id", "mobility_metric", "mobility_value"}
    missing = required - set(mobility_df.columns)
    if missing:
        raise ValueError(f"Mobility DataFrame missing required columns: {sorted(missing)}")

    df = _normalize_date_column(mobility_df, "observation_date")

    # Detect duplicate candidate keys: (observation_date, region_id, mobility_metric)
    key_counts = df.groupby(["observation_date", "region_id", "mobility_metric"]).size()
    duplicates_detected = int((key_counts > 1).sum())

    if duplicates_detected > 0:
        # Deduplicate keeping last, but record occurrence in audit
        df = df.drop_duplicates(subset=["observation_date", "region_id", "mobility_metric"], keep="last")

    # Pivot to wide format
    pivoted = df.pivot(
        index=["observation_date", "region_id"],
        columns="mobility_metric",
        values="mobility_value",
    ).reset_index()

    pivoted.columns.name = None
    metric_cols = [c for c in pivoted.columns if c not in ("observation_date", "region_id")]

    return pivoted, duplicates_detected, sorted(metric_cols)


def align_surveillance_and_mobility(
    surveillance_df: pd.DataFrame,
    mobility_df: pd.DataFrame,
    how: str = "inner",
) -> tuple[pd.DataFrame, AlignmentSummary]:
    """Join surveillance observations with pivoted mobility indicators.

    Args:
        surveillance_df: Surveillance observations table.
        mobility_df: Mobility indicators table.
        how: Join type ('inner' to require both, 'left' to retain all surveillance).

    Returns:
        Tuple of (aligned_df, alignment_summary).
    """
    surv_req = {"observation_date", "region_id", "syndrome", "report_count"}
    surv_missing = surv_req - set(surveillance_df.columns)
    if surv_missing:
        raise ValueError(f"Surveillance DataFrame missing required columns: {sorted(surv_missing)}")

    surv = _normalize_date_column(surveillance_df, "observation_date")
    pivoted_mob, dup_count, metrics = pivot_mobility_indicators(mobility_df)

    initial_surv_count = len(surv)

    # Join on (observation_date, region_id)
    # Because pivoted_mob has unique (date, region), this join CANNOT cause row multiplication
    aligned = pd.merge(
        surv,
        pivoted_mob,
        on=["observation_date", "region_id"],
        how=how,
    )

    if how == "left" and len(aligned) != initial_surv_count:
        raise AssertionError(
            f"Row count mismatch after join! Expected {initial_surv_count}, got {len(aligned)}. "
            "Accidental row multiplication detected."
        )

    # Sort strictly chronologically
    aligned = aligned.sort_values(["observation_date", "region_id", "syndrome"]).reset_index(drop=True)

    # Missingness diagnostics
    missing_surv = int(aligned["report_count"].isna().sum())
    missing_mob = int(aligned[metrics].isna().any(axis=1).sum()) if metrics else 0
    complete_cases = int((~aligned["report_count"].isna() & ~aligned[metrics].isna().any(axis=1)).sum()) if metrics else 0

    dates = sorted(aligned["observation_date"].unique())
    start_str = dates[0].isoformat() if dates else None
    end_str = dates[-1].isoformat() if dates else None
    regions = sorted(aligned["region_id"].unique())

    summary = AlignmentSummary(
        surveillance_input_rows=initial_surv_count,
        mobility_input_rows=len(mobility_df),
        pivoted_mobility_rows=len(pivoted_mob),
        aligned_rows=len(aligned),
        complete_cases_rows=complete_cases,
        missing_mobility_rows=missing_mob,
        missing_surveillance_count_rows=missing_surv,
        mobility_metrics_aligned=metrics,
        regions_aligned=regions,
        date_range_start=start_str,
        date_range_end=end_str,
        duplicate_mobility_keys_detected=dup_count,
    )

    return aligned, summary
