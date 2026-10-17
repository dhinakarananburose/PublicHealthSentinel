"""Tests for synthetic data generation, determinism, provenance, and spike injection."""

from datetime import date
from pathlib import Path
import pytest

from public_health_sentinel.schemas import DataStatus
from public_health_sentinel.synthetic_generator import (
    DEFAULT_REGIONS,
    DEFAULT_SYNDROMES,
    InjectedSpike,
    generate_synthetic_data,
)


def test_deterministic_generation_with_same_seed():
    """Verify that identical random seeds produce identical dataset counts and values."""
    ds1 = generate_synthetic_data(seed=123, duration_days=30)
    ds2 = generate_synthetic_data(seed=123, duration_days=30)

    assert len(ds1.surveillance) == len(ds2.surveillance)
    assert len(ds1.mobility) == len(ds2.mobility)

    counts1 = [obs.report_count for obs in ds1.surveillance]
    counts2 = [obs.report_count for obs in ds2.surveillance]
    assert counts1 == counts2

    mob_vals1 = [ind.mobility_value for ind in ds1.mobility]
    mob_vals2 = [ind.mobility_value for ind in ds2.mobility]
    assert mob_vals1 == mob_vals2


def test_different_seeds_produce_different_results():
    """Verify that different random seeds produce varying stochastic series."""
    ds1 = generate_synthetic_data(seed=42, duration_days=30)
    ds2 = generate_synthetic_data(seed=999, duration_days=30)

    counts1 = [obs.report_count for obs in ds1.surveillance]
    counts2 = [obs.report_count for obs in ds2.surveillance]
    assert counts1 != counts2


def test_synthetic_provenance_labels():
    """Verify that all generated records carry data_status='simulated'."""
    dataset = generate_synthetic_data(seed=42, duration_days=10)

    for obs in dataset.surveillance:
        assert obs.data_status == DataStatus.SIMULATED
        assert obs.data_source == "SYNTHETIC_GENERATOR"

    for ind in dataset.mobility:
        assert ind.data_status == DataStatus.SIMULATED
        assert ind.data_source == "SYNTHETIC_MOBILITY_GENERATOR"


def test_expected_default_record_counts():
    """Verify full-coverage record count: duration_days * regions * syndromes."""
    duration = 180
    dataset = generate_synthetic_data(
        duration_days=duration,
        missing_dates_fraction=0.0,
    )

    expected_surv_count = duration * len(DEFAULT_REGIONS) * len(DEFAULT_SYNDROMES)
    # 3 mobility metrics per day per region
    expected_mob_count = duration * len(DEFAULT_REGIONS) * 3

    assert len(dataset.surveillance) == expected_surv_count
    assert len(dataset.mobility) == expected_mob_count
    assert len(dataset.surveillance) == 2700
    assert len(dataset.mobility) == 2700


def test_known_injected_spikes_recorded():
    """Verify that injected synthetic spikes are tracked in metadata and affect counts."""
    custom_spike = InjectedSpike(
        observation_date=date(2026, 1, 15),
        region_id="REGION_A",
        syndrome="Respiratory",
        spike_count=200,
        duration_days=1,
        description="Test massive spike",
    )

    dataset_with_spike = generate_synthetic_data(
        start_date=date(2026, 1, 1),
        duration_days=30,
        inject_spikes=True,
        custom_spikes=[custom_spike],
        seed=42,
    )
    dataset_no_spike = generate_synthetic_data(
        start_date=date(2026, 1, 1),
        duration_days=30,
        inject_spikes=False,
        seed=42,
    )

    assert len(dataset_with_spike.injected_spikes) == 1
    assert dataset_with_spike.injected_spikes[0].spike_count == 200

    target_with = [
        obs for obs in dataset_with_spike.surveillance
        if obs.observation_date == date(2026, 1, 15)
        and obs.region_id == "REGION_A"
        and obs.syndrome == "Respiratory"
    ][0]

    target_without = [
        obs for obs in dataset_no_spike.surveillance
        if obs.observation_date == date(2026, 1, 15)
        and obs.region_id == "REGION_A"
        and obs.syndrome == "Respiratory"
    ][0]

    assert target_with.report_count == target_without.report_count + 200


def test_missing_observations_distinguishable_from_zero():
    """Verify that missing observations result in absent rows, not zero counts."""
    dataset = generate_synthetic_data(
        duration_days=30,
        missing_dates_fraction=0.10,
        seed=42,
    )

    total_expected = 30 * len(DEFAULT_REGIONS) * len(DEFAULT_SYNDROMES)
    assert len(dataset.surveillance) < total_expected

    # Zero counts might happen naturally if Poisson draws 0, but an omitted observation
    # means the row is missing from the table entirely
    distinct_dates = set(obs.observation_date for obs in dataset.surveillance)
    assert len(distinct_dates) <= 30


def test_synthetic_dataset_save_csv(tmp_path: Path):
    """Verify saving synthetic datasets to CSV files."""
    dataset = generate_synthetic_data(duration_days=5, seed=42)

    s_file = tmp_path / "surv.csv"
    m_file = tmp_path / "mob.csv"
    sp_file = tmp_path / "spikes.csv"

    dataset.save_csv(s_file, m_file, sp_file)

    assert s_file.exists()
    assert m_file.exists()
    assert sp_file.exists()
    assert s_file.stat().st_size > 0
    assert m_file.stat().st_size > 0
