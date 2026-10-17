"""Data schemas and provenance definitions for PublicHealthSentinel.

This module defines Pydantic schemas for:
1. Aggregated daily syndromic surveillance observations
2. Aggregated population mobility indicators

Core Principles:
- AGGREGATION ONLY: No individual patient records or Protected Health Information (PHI).
- STRICT PROVENANCE: Every record tracks its data_status (real, simulated, derived).
- NO INVENTED ZEROS: Missing denominators or reporting facility counts remain None.
- NON-CAUSALITY: Observed associations between mobility trends and syndromic counts
  are strictly ecological and observational; they do NOT establish clinical or
  epidemiological causation.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DataStatus(str, Enum):
    """Provenance state of the observation or indicator.
    
    Attributes:
        REAL: Genuine observational data from health authorities or mobility providers.
        SIMULATED: Synthetic benchmark data generated for testing and model evaluation.
        DERIVED: Post-processed or aggregated observations (e.g., rolling averages, normalized rates).
    """
    REAL = "real"
    SIMULATED = "simulated"
    DERIVED = "derived"


class AggregatedObservation(BaseModel):
    """Aggregated daily syndromic surveillance count for a geographic jurisdiction.

    IMPORTANT SCIENTIFIC CONSTRAINTS:
    - This schema represents high-level aggregated counts only.
    - Zero individual-level patient records or personal identifiers are permitted.
    - Missing reporting facility counts or population denominators must remain None.
      Treating unknown counts as 0 introduces severe epidemiological distortion.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        validate_default=True,
    )

    observation_date: date = Field(
        ...,
        description="Calendar date of surveillance observation in YYYY-MM-DD format.",
    )
    region_id: str = Field(
        ...,
        min_length=1,
        description="Geographic jurisdiction identifier (e.g., FIPS code, ISO-3166-2, or district ID).",
    )
    syndrome: str = Field(
        ...,
        min_length=1,
        description="Standardized syndrome cluster under surveillance (e.g., 'ILI', 'respiratory', 'gastrointestinal').",
    )
    report_count: int = Field(
        ...,
        ge=0,
        description="Non-negative integer count of aggregated clinical encounters or symptom reports.",
    )
    reporting_facility_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of healthcare facilities that submitted reports for this date. None if unrecorded.",
    )
    population_denominator: Optional[int] = Field(
        default=None,
        gt=0,
        description="Estimated reference population for the jurisdiction. Must be >0 if provided; None if unavailable.",
    )
    data_source: str = Field(
        ...,
        min_length=1,
        description="Originating stream or publishing agency (e.g., 'CDC_NHSN', 'STATE_DOH', 'SYNTHETIC_GENERATOR').",
    )
    data_status: DataStatus = Field(
        ...,
        description="Provenance classification: 'real', 'simulated', or 'derived'.",
    )
    ingestion_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp marking when this record was ingested into the sentinel system.",
    )

    @field_validator("region_id", "syndrome", "data_source")
    @classmethod
    def validate_non_empty_strings(cls, v: str, info) -> str:
        """Ensure string fields contain non-whitespace characters."""
        if not v or not v.strip():
            raise ValueError(f"Field '{info.field_name}' cannot be empty or blank whitespace.")
        return v.strip()

    @property
    def crude_incidence_per_100k(self) -> Optional[float]:
        """Calculate crude incidence rate per 100,000 population when denominator exists.

        Returns None if population_denominator is missing. Does NOT fabricate zero.
        """
        if self.population_denominator is None:
            return None
        return (self.report_count / self.population_denominator) * 100_000.0


class MobilityIndicator(BaseModel):
    """Aggregated population mobility indicator for a geographic region.

    EPIDEMIOLOGICAL DISCLAIMER:
    Observed correlations between mobility metrics (e.g., transit activity, workplace presence)
    and syndromic surge counts are ecological correlations. They do NOT establish causation,
    disease transmission dynamics, or individual behavioral compliance.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        validate_default=True,
    )

    observation_date: date = Field(
        ...,
        description="Calendar date of mobility measurement in YYYY-MM-DD format.",
    )
    region_id: str = Field(
        ...,
        min_length=1,
        description="Geographic jurisdiction identifier corresponding to surveillance regions.",
    )
    mobility_metric: str = Field(
        ...,
        min_length=1,
        description="Name of standardized mobility metric (e.g., 'transit_station_pct_change', 'retail_recreation_pct_change').",
    )
    mobility_value: float = Field(
        ...,
        description="Numeric metric value (e.g., percentage deviation from baseline, index score).",
    )
    data_source: str = Field(
        ...,
        min_length=1,
        description="Originating provider (e.g., 'GOOGLE_COMMUNITY_MOBILITY', 'SYNTHETIC_MOBILITY_GENERATOR').",
    )
    data_status: DataStatus = Field(
        ...,
        description="Provenance classification: 'real', 'simulated', or 'derived'.",
    )
    ingestion_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the indicator was ingested.",
    )

    @field_validator("region_id", "mobility_metric", "data_source")
    @classmethod
    def validate_non_empty_strings(cls, v: str, info) -> str:
        """Ensure string fields contain non-whitespace characters."""
        if not v or not v.strip():
            raise ValueError(f"Field '{info.field_name}' cannot be empty or blank whitespace.")
        return v.strip()
