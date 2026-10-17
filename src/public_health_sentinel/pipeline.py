"""End-to-end data engineering pipeline for PublicHealthSentinel.

Orchestrates:
1. Synthetic data generation or external CSV loading
2. Pydantic schema validation with row-level error attribution
3. Data quality audits and natural-key duplicate detection
4. Atomic writing of accepted records to data/processed/
5. Separate quarantine storage of rejected rows with actionable diagnostics
6. Serialization of machine-readable quality reports
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from public_health_sentinel.config import get_config
from public_health_sentinel.loader import load_mobility_csv, load_surveillance_csv
from public_health_sentinel.quality import (
    MobilityQualityReport,
    SurveillanceQualityReport,
    assess_mobility_quality,
    assess_surveillance_quality,
)
from public_health_sentinel.synthetic_generator import (
    DEFAULT_REGIONS,
    DEFAULT_SYNDROMES,
    generate_synthetic_data,
)
from public_health_sentinel.validator import (
    validate_mobility_records,
    validate_surveillance_records,
)


@dataclass
class PipelineResult:
    """Summary of data pipeline execution."""

    status: Literal["SUCCESS", "FAILED"]
    surveillance_valid_count: int
    surveillance_invalid_count: int
    mobility_valid_count: int
    mobility_invalid_count: int
    surveillance_quality: SurveillanceQualityReport
    mobility_quality: MobilityQualityReport
    processed_files: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert pipeline outcome to summary dictionary."""
        return {
            "status": self.status,
            "surveillance_valid_count": self.surveillance_valid_count,
            "surveillance_invalid_count": self.surveillance_invalid_count,
            "mobility_valid_count": self.mobility_valid_count,
            "mobility_invalid_count": self.mobility_invalid_count,
            "processed_files": self.processed_files,
            "errors": self.errors,
            "surveillance_quality": self.surveillance_quality.to_dict(),
            "mobility_quality": self.mobility_quality.to_dict(),
        }


def _atomic_write_dataframe(df: pd.DataFrame, target_path: Path) -> Path:
    """Safely write DataFrame to temporary file and atomically rename to target.

    Prevents partially written files from appearing as completed runs.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".tmp_{os.getpid()}_{target_path.name}")
    try:
        df.to_csv(temp_path, index=False)
        os.replace(temp_path, target_path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
    return target_path


def _atomic_write_json(data: dict[str, Any], target_path: Path) -> Path:
    """Safely write JSON to temporary file and atomically rename."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_name(f".tmp_{os.getpid()}_{target_path.name}")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(temp_path, target_path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
    return target_path


def run_pipeline(
    surveillance_source: Path | pd.DataFrame | str | None = None,
    mobility_source: Path | pd.DataFrame | str | None = None,
    output_dir: Path | str | None = None,
    synthetic_dir: Path | str | None = None,
    seed: int = 42,
    duration_days: int = 180,
    inject_spikes: bool = True,
    missing_dates_fraction: float = 0.0,
) -> PipelineResult:
    """Execute the Phase 2 data engineering pipeline.

    Args:
        surveillance_source: Optional path or DataFrame of input surveillance records.
            If None, synthetic dataset is generated.
        mobility_source: Optional path or DataFrame of input mobility records.
            If None, synthetic dataset is generated.
        output_dir: Destination for processed records and reports.
        synthetic_dir: Destination for raw generated synthetic benchmarks.
        seed: Random seed for deterministic generation.
        duration_days: Duration for synthetic generator (default: 180 days).
        inject_spikes: Whether to inject known benchmark anomaly spikes.
        missing_dates_fraction: Fraction of synthetic dates to deliberately omit.

    Returns:
        PipelineResult with execution status, counts, and file locations.
    """
    config = get_config()
    proc_dir = Path(output_dir) if output_dir else config.data_processed_dir
    synth_dir = Path(synthetic_dir) if synthetic_dir else config.data_synthetic_dir

    proc_dir.mkdir(parents=True, exist_ok=True)
    synth_dir.mkdir(parents=True, exist_ok=True)

    processed_files: dict[str, str] = {}
    pipeline_errors: list[str] = []

    # Step 1: Ingestion or Synthetic Generation
    surv_df: pd.DataFrame
    mob_df: pd.DataFrame

    if surveillance_source is None or mobility_source is None:
        # Generate deterministic synthetic data
        dataset = generate_synthetic_data(
            start_date=date(2026, 1, 1),
            duration_days=duration_days,
            regions=DEFAULT_REGIONS,
            syndromes=DEFAULT_SYNDROMES,
            seed=seed,
            inject_spikes=inject_spikes,
            missing_dates_fraction=missing_dates_fraction,
        )

        # Save raw synthetic benchmarks under data/synthetic/
        synth_surv_file = synth_dir / "synthetic_surveillance.csv"
        synth_mob_file = synth_dir / "synthetic_mobility.csv"
        synth_spikes_file = synth_dir / "synthetic_injected_spikes.csv"

        _atomic_write_dataframe(dataset.to_surveillance_df(), synth_surv_file)
        _atomic_write_dataframe(dataset.to_mobility_df(), synth_mob_file)
        if dataset.injected_spikes:
            spikes_df = pd.DataFrame([s.to_dict() for s in dataset.injected_spikes])
            _atomic_write_dataframe(spikes_df, synth_spikes_file)
            processed_files["synthetic_spikes"] = str(synth_spikes_file)

        processed_files["synthetic_surveillance"] = str(synth_surv_file)
        processed_files["synthetic_mobility"] = str(synth_mob_file)

        surv_df = dataset.to_surveillance_df()
        mob_df = dataset.to_mobility_df()
    else:
        # Load from provided sources
        if isinstance(surveillance_source, pd.DataFrame):
            surv_df = surveillance_source
        else:
            surv_df = load_surveillance_csv(surveillance_source)

        if isinstance(mobility_source, pd.DataFrame):
            mob_df = mobility_source
        else:
            mob_df = load_mobility_csv(mobility_source)

    # Step 2: Validation
    surv_val = validate_surveillance_records(surv_df)
    mob_val = validate_mobility_records(mob_df)

    # Step 3: Data Quality Assessment
    surv_quality = assess_surveillance_quality(
        valid_records=surv_val.valid_records,
        invalid_records=surv_val.invalid_records,
        expected_regions=DEFAULT_REGIONS,
        expected_syndromes=DEFAULT_SYNDROMES,
    )

    mob_quality = assess_mobility_quality(
        valid_records=mob_val.valid_records,
        invalid_records=mob_val.invalid_records,
        expected_regions=DEFAULT_REGIONS,
    )

    # Step 4: Write Processed Valid Outputs
    accepted_surv_file = proc_dir / "surveillance_observations.csv"
    accepted_mob_file = proc_dir / "mobility_indicators.csv"

    accepted_surv_df = pd.DataFrame([obs.model_dump() for obs in surv_val.valid_records])
    accepted_mob_df = pd.DataFrame([ind.model_dump() for ind in mob_val.valid_records])

    _atomic_write_dataframe(accepted_surv_df, accepted_surv_file)
    _atomic_write_dataframe(accepted_mob_df, accepted_mob_file)

    processed_files["surveillance_observations"] = str(accepted_surv_file)
    processed_files["mobility_indicators"] = str(accepted_mob_file)

    # Step 5: Write Quarantine Outputs (if any invalid rows exist)
    if surv_val.invalid_records:
        quarantine_surv_file = proc_dir / "surveillance_quarantine.csv"
        quarantine_surv_df = pd.DataFrame([r.to_dict() for r in surv_val.invalid_records])
        _atomic_write_dataframe(quarantine_surv_df, quarantine_surv_file)
        processed_files["surveillance_quarantine"] = str(quarantine_surv_file)

    if mob_val.invalid_records:
        quarantine_mob_file = proc_dir / "mobility_quarantine.csv"
        quarantine_mob_df = pd.DataFrame([r.to_dict() for r in mob_val.invalid_records])
        _atomic_write_dataframe(quarantine_mob_df, quarantine_mob_file)
        processed_files["mobility_quarantine"] = str(quarantine_mob_file)

    # Step 6: Write Machine-Readable Quality Report
    report_file = proc_dir / "quality_report.json"
    full_report = {
        "pipeline_version": "0.1.0",
        "surveillance": surv_quality.to_dict(),
        "mobility": mob_quality.to_dict(),
        "files": processed_files,
    }
    _atomic_write_json(full_report, report_file)
    processed_files["quality_report"] = str(report_file)

    status: Literal["SUCCESS", "FAILED"] = "SUCCESS"
    if surv_val.valid_count == 0 or mob_val.valid_count == 0:
        status = "FAILED"
        pipeline_errors.append("Pipeline failed: zero valid records accepted.")

    return PipelineResult(
        status=status,
        surveillance_valid_count=surv_val.valid_count,
        surveillance_invalid_count=surv_val.invalid_count,
        mobility_valid_count=mob_val.valid_count,
        mobility_invalid_count=mob_val.invalid_count,
        surveillance_quality=surv_quality,
        mobility_quality=mob_quality,
        processed_files=processed_files,
        errors=pipeline_errors,
    )


if __name__ == "__main__":
    import sys
    from public_health_sentinel.cli import main

    sys.exit(main())

