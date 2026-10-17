"""Record-level data validation for surveillance observations and mobility indicators.

Validates input records against Pydantic models, separates valid from invalid rows,
preserves source row numbers and actionable validation failure reasons, and ensures
no invalid rows are discarded silently.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Generic, Sequence, TypeVar

import pandas as pd
from pydantic import ValidationError

from public_health_sentinel.schemas import (
    AggregatedObservation,
    MobilityIndicator,
)

T = TypeVar("T", AggregatedObservation, MobilityIndicator)


@dataclass
class RejectedRecord:
    """Encapsulates a rejected record quarantined during ingestion."""

    row_number: int
    raw_record: dict[str, Any]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert rejected record to serializable dictionary for quarantine logging."""
        cleaned_raw = {
            k: (v.isoformat() if isinstance(v, date) else v)
            for k, v in self.raw_record.items()
        }
        return {
            "row_number": self.row_number,
            "errors": "; ".join(self.errors),
            **cleaned_raw,
        }


@dataclass
class ValidationResult(Generic[T]):
    """Container holding accepted valid records and quarantined rejected records."""

    valid_records: list[T] = field(default_factory=list)
    invalid_records: list[RejectedRecord] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.valid_records) + len(self.invalid_records)

    @property
    def valid_count(self) -> int:
        return len(self.valid_records)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_records)

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "total_input_count": self.total_count,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "valid_ratio": round(self.valid_count / max(self.total_count, 1), 4),
        }


def _clean_row_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Clean pandas row dict by converting NaN/NA values to None."""
    cleaned: dict[str, Any] = {}
    for k, v in raw.items():
        if pd.isna(v):
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def validate_surveillance_records(
    records: Sequence[dict[str, Any]] | pd.DataFrame,
    start_row_index: int = 2,
) -> ValidationResult[AggregatedObservation]:
    """Validate surveillance records against AggregatedObservation schema.

    Args:
        records: List of dictionaries or a pandas DataFrame.
        start_row_index: 1-indexed row offset corresponding to CSV lines
            (defaults to 2 assuming line 1 is the CSV header).

    Returns:
        ValidationResult containing validated models and rejected rows with errors.
    """
    if isinstance(records, pd.DataFrame):
        row_dicts = records.to_dict(orient="records")
    else:
        row_dicts = list(records)

    result: ValidationResult[AggregatedObservation] = ValidationResult()

    for idx, raw_row in enumerate(row_dicts):
        row_num = idx + start_row_index
        cleaned_row = _clean_row_dict(raw_row)

        try:
            obs = AggregatedObservation(**cleaned_row)
            result.valid_records.append(obs)
        except ValidationError as exc:
            error_messages = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            ]
            result.invalid_records.append(
                RejectedRecord(
                    row_number=row_num,
                    raw_record=cleaned_row,
                    errors=error_messages,
                )
            )
        except Exception as exc:
            result.invalid_records.append(
                RejectedRecord(
                    row_number=row_num,
                    raw_record=cleaned_row,
                    errors=[f"Unexpected error: {str(exc)}"],
                )
            )

    return result


def validate_mobility_records(
    records: Sequence[dict[str, Any]] | pd.DataFrame,
    start_row_index: int = 2,
) -> ValidationResult[MobilityIndicator]:
    """Validate mobility indicator records against MobilityIndicator schema.

    Args:
        records: List of dictionaries or a pandas DataFrame.
        start_row_index: 1-indexed row offset corresponding to CSV lines.

    Returns:
        ValidationResult containing validated models and rejected rows.
    """
    if isinstance(records, pd.DataFrame):
        row_dicts = records.to_dict(orient="records")
    else:
        row_dicts = list(records)

    result: ValidationResult[MobilityIndicator] = ValidationResult()

    for idx, raw_row in enumerate(row_dicts):
        row_num = idx + start_row_index
        cleaned_row = _clean_row_dict(raw_row)

        try:
            ind = MobilityIndicator(**cleaned_row)
            result.valid_records.append(ind)
        except ValidationError as exc:
            error_messages = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            ]
            result.invalid_records.append(
                RejectedRecord(
                    row_number=row_num,
                    raw_record=cleaned_row,
                    errors=error_messages,
                )
            )
        except Exception as exc:
            result.invalid_records.append(
                RejectedRecord(
                    row_number=row_num,
                    raw_record=cleaned_row,
                    errors=[f"Unexpected error: {str(exc)}"],
                )
            )

    return result
