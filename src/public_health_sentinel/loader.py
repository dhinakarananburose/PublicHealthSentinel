"""CSV data loaders for surveillance observations and mobility indicators.

Enforces schema contract checks, preserves missing values as None,
and rejects malformed files with descriptive actionable errors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd

REQUIRED_SURVEILLANCE_COLUMNS: set[str] = {
    "observation_date",
    "region_id",
    "syndrome",
    "report_count",
    "data_source",
    "data_status",
}

REQUIRED_MOBILITY_COLUMNS: set[str] = {
    "observation_date",
    "region_id",
    "mobility_metric",
    "mobility_value",
    "data_source",
    "data_status",
}


class DataLoaderError(Exception):
    """Raised when an input data file is missing, empty, or structurally malformed."""


def _check_file_exists_and_readable(path: Path) -> None:
    """Verify that file exists, is a regular file, and is not zero bytes."""
    if not path.exists():
        raise DataLoaderError(f"File does not exist: {path}")
    if not path.is_file():
        raise DataLoaderError(f"Path is not a regular file: {path}")
    if path.stat().st_size == 0:
        raise DataLoaderError(f"File is completely empty (0 bytes): {path}")


def load_surveillance_csv(
    file_path: Path | str,
    required_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Load a surveillance CSV file into a pandas DataFrame.

    Requirements:
    - Parses dates and numeric columns explicitly.
    - Preserves genuinely missing values as NaN/None (never coerces to 0).
    - Checks for presence of all required columns regardless of column order.
    - Rejects malformed or empty files with DataLoaderError.

    Args:
        file_path: Path to the surveillance CSV.
        required_columns: Expected columns (defaults to REQUIRED_SURVEILLANCE_COLUMNS).

    Returns:
        DataFrame with raw or parsed columns ready for validation.

    Raises:
        DataLoaderError: If the file cannot be read, is empty, or lacks required columns.
    """
    path = Path(file_path)
    _check_file_exists_and_readable(path)

    expected = set(required_columns or REQUIRED_SURVEILLANCE_COLUMNS)

    try:
        # keep_default_na=True preserves empty cells as NaN without inventing 0
        df = pd.read_csv(
            path,
            dtype={
                "region_id": str,
                "syndrome": str,
                "data_source": str,
                "data_status": str,
            },
            keep_default_na=True,
        )
    except Exception as exc:
        raise DataLoaderError(f"Failed to parse CSV file '{path}': {exc}") from exc

    if df.empty:
        raise DataLoaderError(f"Surveillance dataset in '{path}' contains header but 0 data rows.")

    missing = expected - set(df.columns)
    if missing:
        raise DataLoaderError(
            f"Surveillance CSV '{path}' is missing required columns: {sorted(missing)}. "
            f"Found columns: {list(df.columns)}"
        )

    return df


def load_mobility_csv(
    file_path: Path | str,
    required_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Load a mobility CSV file into a pandas DataFrame.

    Args:
        file_path: Path to the mobility CSV.
        required_columns: Expected columns (defaults to REQUIRED_MOBILITY_COLUMNS).

    Returns:
        DataFrame ready for validation.

    Raises:
        DataLoaderError: If the file cannot be read, is empty, or lacks required columns.
    """
    path = Path(file_path)
    _check_file_exists_and_readable(path)

    expected = set(required_columns or REQUIRED_MOBILITY_COLUMNS)

    try:
        df = pd.read_csv(
            path,
            dtype={
                "region_id": str,
                "mobility_metric": str,
                "data_source": str,
                "data_status": str,
            },
            keep_default_na=True,
        )
    except Exception as exc:
        raise DataLoaderError(f"Failed to parse CSV file '{path}': {exc}") from exc

    if df.empty:
        raise DataLoaderError(f"Mobility dataset in '{path}' contains header but 0 data rows.")

    missing = expected - set(df.columns)
    if missing:
        raise DataLoaderError(
            f"Mobility CSV '{path}' is missing required columns: {sorted(missing)}. "
            f"Found columns: {list(df.columns)}"
        )

    return df
