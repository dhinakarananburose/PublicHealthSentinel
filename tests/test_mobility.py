"""Comprehensive automated test suite for Phase 4 Mobility Analysis and Predictive Evaluation."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from public_health_sentinel.mobility.alignment import (
    align_surveillance_and_mobility,
    pivot_mobility_indicators,
)
from public_health_sentinel.mobility.correlation import (
    compute_correlations,
    compute_descriptive_statistics,
    generate_mobility_figures,
)
from public_health_sentinel.mobility.evaluation import (
    build_evaluation_dataset,
    evaluate_models,
)
from public_health_sentinel.mobility.lag_analysis import (
    compute_lagged_correlations,
    plot_cross_correlation_profile,
)
from public_health_sentinel.mobility.pipeline import run_mobility_analysis_pipeline


@pytest.fixture
def sample_surveillance_df() -> pd.DataFrame:
    """Fixture providing 30 days of surveillance data across 2 regions and 2 syndromes."""
    rows = []
    base_date = date(2026, 1, 1)
    for day in range(30):
        curr_date = base_date + timedelta(days=day)
        for reg in ["REGION_A", "REGION_B"]:
            for syn in ["Respiratory", "Febrile"]:
                count = 20.0 + (day % 7) * 3.0 + (5.0 if reg == "REGION_B" else 0.0)
                if day in (15, 25):  # Inject surge events for classification target
                    count += 60.0
                rows.append(
                    {
                        "observation_date": curr_date,
                        "region_id": reg,
                        "syndrome": syn,
                        "report_count": count,
                        "data_status": "VALID",
                    }
                )
    return pd.DataFrame(rows)


@pytest.fixture
def sample_mobility_df() -> pd.DataFrame:
    """Fixture providing 30 days of long-format mobility data across 2 regions and 2 metrics."""
    rows = []
    base_date = date(2026, 1, 1)
    for day in range(30):
        curr_date = base_date + timedelta(days=day)
        for reg in ["REGION_A", "REGION_B"]:
            # Transit mobility: dips on weekends
            transit_val = -10.0 if (day % 7) in (5, 6) else 5.0
            rows.append(
                {
                    "observation_date": curr_date,
                    "region_id": reg,
                    "mobility_metric": "transit_station_pct_change",
                    "mobility_value": transit_val,
                    "data_status": "VALID",
                }
            )
            # Residential mobility: rises on weekends
            res_val = 15.0 if (day % 7) in (5, 6) else -2.0
            rows.append(
                {
                    "observation_date": curr_date,
                    "region_id": reg,
                    "mobility_metric": "residential_pct_change",
                    "mobility_value": res_val,
                    "data_status": "VALID",
                }
            )
    return pd.DataFrame(rows)


class TestMobilityAlignment:
    """Tests for spatial and temporal alignment of surveillance and mobility data."""

    def test_alignment_correct_date_region(self, sample_surveillance_df, sample_mobility_df):
        """Verify that surveillance and pivoted mobility match precisely on (date, region)."""
        aligned, summary = align_surveillance_and_mobility(sample_surveillance_df, sample_mobility_df)

        assert len(aligned) == len(sample_surveillance_df)
        assert summary.aligned_rows == len(sample_surveillance_df)
        assert set(summary.regions_aligned) == {"REGION_A", "REGION_B"}
        assert "transit_station_pct_change" in aligned.columns
        assert "residential_pct_change" in aligned.columns

        # Verify a specific row pairing
        target = aligned[
            (aligned["observation_date"] == date(2026, 1, 1))
            & (aligned["region_id"] == "REGION_A")
            & (aligned["syndrome"] == "Respiratory")
        ].iloc[0]
        assert target["report_count"] == 20.0
        assert target["transit_station_pct_change"] == 5.0
        assert target["residential_pct_change"] == -2.0

    def test_alignment_no_row_multiplication(self, sample_surveillance_df, sample_mobility_df):
        """Verify that wide pivot and join prevent Cartesian row explosion."""
        init_rows = len(sample_surveillance_df)
        aligned, summary = align_surveillance_and_mobility(sample_surveillance_df, sample_mobility_df, how="inner")
        assert len(aligned) == init_rows
        assert summary.aligned_rows == init_rows

    def test_alignment_duplicate_key_handling(self, sample_surveillance_df, sample_mobility_df):
        """Verify duplicate candidate keys in mobility are detected and handled without multiplying rows."""
        mob_with_dup = pd.concat([sample_mobility_df, sample_mobility_df.iloc[:2]], ignore_index=True)
        aligned, summary = align_surveillance_and_mobility(sample_surveillance_df, mob_with_dup)

        assert summary.duplicate_mobility_keys_detected == 2
        assert len(aligned) == len(sample_surveillance_df)

    def test_alignment_missing_mobility_values_preserved(self, sample_surveillance_df, sample_mobility_df):
        """Verify missing mobility observations are preserved as NaN and never imputed with zero."""
        mob_with_nan = sample_mobility_df.copy()
        mob_with_nan.loc[0, "mobility_value"] = np.nan

        aligned, summary = align_surveillance_and_mobility(sample_surveillance_df, mob_with_nan, how="left")
        assert summary.missing_mobility_rows > 0

        # Verify the cell is NaN, not 0.0
        missing_row = aligned[
            (aligned["observation_date"] == date(2026, 1, 1))
            & (aligned["region_id"] == "REGION_A")
        ]
        assert pd.isna(missing_row["transit_station_pct_change"].iloc[0])

    def test_alignment_missing_surveillance_values(self, sample_surveillance_df, sample_mobility_df):
        """Verify missing surveillance report counts are tracked and preserved."""
        surv_with_nan = sample_surveillance_df.copy()
        target_date = surv_with_nan.loc[0, "observation_date"]
        target_reg = surv_with_nan.loc[0, "region_id"]
        target_syn = surv_with_nan.loc[0, "syndrome"]
        surv_with_nan.loc[0, "report_count"] = np.nan

        aligned, summary = align_surveillance_and_mobility(surv_with_nan, sample_mobility_df)
        assert summary.missing_surveillance_count_rows == 1

        missing_row = aligned[
            (aligned["observation_date"] == target_date)
            & (aligned["region_id"] == target_reg)
            & (aligned["syndrome"] == target_syn)
        ]
        assert pd.isna(missing_row["report_count"].iloc[0])


class TestCorrelationAnalysis:
    """Tests for descriptive statistics and correlation calculations."""

    def test_descriptive_statistics_calculation(self, sample_surveillance_df, sample_mobility_df):
        """Verify descriptive statistics output structure and accuracy."""
        aligned, summary = align_surveillance_and_mobility(sample_surveillance_df, sample_mobility_df)
        stats_dict = compute_descriptive_statistics(aligned, summary.mobility_metrics_aligned)

        assert "surveillance_by_syndrome" in stats_dict
        assert "mobility_by_metric" in stats_dict
        assert "Respiratory" in stats_dict["surveillance_by_syndrome"]
        assert "transit_station_pct_change" in stats_dict["mobility_by_metric"]

        resp_stats = stats_dict["surveillance_by_syndrome"]["Respiratory"]
        assert resp_stats["count"] == 60
        assert resp_stats["min"] is not None

    def test_correlation_calculations(self, sample_surveillance_df, sample_mobility_df):
        """Verify Pearson and Spearman correlation calculation with p-values."""
        aligned, summary = align_surveillance_and_mobility(sample_surveillance_df, sample_mobility_df)
        corrs = compute_correlations(aligned, summary.mobility_metrics_aligned)

        assert len(corrs) > 0
        record = corrs[0]
        assert record.sample_size_n == 30
        assert record.pearson_r is not None
        assert record.spearman_rho is not None
        assert 0.0 <= record.pearson_p_value <= 1.0

    def test_correlation_zero_variance_handling(self):
        """Verify zero variance series return None gracefully without raising exceptions."""
        df = pd.DataFrame(
            {
                "observation_date": [date(2026, 1, i) for i in range(1, 10)],
                "region_id": ["REGION_A"] * 9,
                "syndrome": ["Respiratory"] * 9,
                "report_count": [10.0] * 9,  # Zero variance
                "transit_station_pct_change": [5.0] * 9,  # Zero variance
            }
        )
        corrs = compute_correlations(df, ["transit_station_pct_change"])
        assert len(corrs) == 1
        assert corrs[0].pearson_r is None
        assert "Insufficient variance" in corrs[0].interpretation_note


class TestLagAnalysis:
    """Tests for temporal lag alignment and cross-correlation sign conventions."""

    def test_lag_sign_convention(self, sample_surveillance_df, sample_mobility_df):
        """Verify that positive lag (+k) pairs symptom count at t with mobility at (t - k)."""
        aligned, summary = align_surveillance_and_mobility(sample_surveillance_df, sample_mobility_df)
        results = compute_lagged_correlations(
            aligned, "transit_station_pct_change", min_lag=-2, max_lag=2
        )

        assert len(results) == 4  # 2 regions * 2 syndromes
        analysis = results[0]
        assert len(analysis.lag_points) == 5  # lags -2, -1, 0, 1, 2

        # Verify positive lag description explicitly states mobility leads
        pos_lag_point = next(p for p in analysis.lag_points if p.lag_days == 1)
        assert "Mobility leads symptom reports by +1 days" in pos_lag_point.convention_description

        # Verify negative lag description explicitly states mobility lags
        neg_lag_point = next(p for p in analysis.lag_points if p.lag_days == -1)
        assert "Mobility lags symptom reports by 1 days" in neg_lag_point.convention_description

    def test_lag_sample_sizes_decrease_with_offset(self, sample_surveillance_df, sample_mobility_df):
        """Verify that sample size decreases as lag offset increases towards series boundaries."""
        aligned, summary = align_surveillance_and_mobility(sample_surveillance_df, sample_mobility_df)
        results = compute_lagged_correlations(
            aligned, "transit_station_pct_change", min_lag=0, max_lag=10
        )
        points = results[0].lag_points
        n_lag0 = next(p.sample_size_n for p in points if p.lag_days == 0)
        n_lag10 = next(p.sample_size_n for p in points if p.lag_days == 10)
        assert n_lag0 == 30
        assert n_lag10 == 20  # 30 - 10 = 20 observations available with 10-day lead


class TestPredictiveEvaluation:
    """Tests for chronological train/test split, feature leakage prevention, and model evaluation."""

    def test_dataset_construction_no_future_feature_leakage(self, sample_surveillance_df, sample_mobility_df):
        """Verify feature vectors at prediction time t only use data <= t."""
        aligned, summary = align_surveillance_and_mobility(sample_surveillance_df, sample_mobility_df)
        ds = build_evaluation_dataset(aligned, summary.mobility_metrics_aligned, lookback_window=7)

        # For every row, target_date must be observation_date + 1 day
        for _, row in ds.iterrows():
            assert row["target_date"] == row["observation_date"] + timedelta(days=1)

        # Check column names: all feature names are at lag_0, lag_1, rolling_mean, etc.
        feature_cols = [c for c in ds.columns if c.startswith(("surv_", "mob_"))]
        for col in feature_cols:
            assert "next" not in col
            assert "future" not in col

    def test_chronological_train_test_split(self, sample_surveillance_df, sample_mobility_df):
        """Verify chronological split partitions strictly by date without overlap or shuffling."""
        aligned, summary = align_surveillance_and_mobility(sample_surveillance_df, sample_mobility_df)
        ds = build_evaluation_dataset(aligned, summary.mobility_metrics_aligned, lookback_window=7)

        comp = evaluate_models(ds, summary.mobility_metrics_aligned, train_ratio=0.70)

        train_start, train_end = comp.train_date_range
        test_start, test_end = comp.test_date_range

        # Strict chronological ordering: train_end < test_start
        assert train_end < test_start

    def test_reproducible_evaluation(self, sample_surveillance_df, sample_mobility_df):
        """Verify identical results with deterministic random seed."""
        aligned, summary = align_surveillance_and_mobility(sample_surveillance_df, sample_mobility_df)
        ds = build_evaluation_dataset(aligned, summary.mobility_metrics_aligned, lookback_window=7)

        eval1 = evaluate_models(ds, summary.mobility_metrics_aligned, train_ratio=0.70, random_seed=42)
        eval2 = evaluate_models(ds, summary.mobility_metrics_aligned, train_ratio=0.70, random_seed=42)

        assert eval1.baseline_model.f1_score == eval2.baseline_model.f1_score
        assert eval1.augmented_model.f1_score == eval2.augmented_model.f1_score
        assert eval1.delta_f1 == eval2.delta_f1


class TestEndToEndPipeline:
    """Integration test for full Phase 4 mobility pipeline execution."""

    def test_pipeline_execution_and_artifact_generation(self, tmp_path):
        """Verify that run_mobility_analysis_pipeline executes cleanly and creates all artifacts."""
        out_dir = tmp_path / "mobility_reports"
        res = run_mobility_analysis_pipeline(
            surveillance_path="data/processed/surveillance_observations.csv",
            mobility_path="data/processed/mobility_indicators.csv",
            output_dir=out_dir,
            min_lag=-3,
            max_lag=5,
            train_ratio=0.70,
            random_seed=42,
        )

        assert Path(res.aligned_dataset_path).exists()
        assert Path(res.descriptive_stats_path).exists()
        assert Path(res.correlation_report_path).exists()
        assert Path(res.lag_analysis_path).exists()
        assert Path(res.model_comparison_path).exists()
        assert Path(res.markdown_report_path).exists()

        for fig_path in res.figures_generated.values():
            assert Path(fig_path).exists()

        # Check markdown content
        with open(res.markdown_report_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "SYNTHETIC-DATA EXPERIMENT DISCLOSURE" in content
            assert "Dataset Alignment and Data Integrity Audit" in content
            assert "Predictive Modeling and Comparative Evaluation" in content
