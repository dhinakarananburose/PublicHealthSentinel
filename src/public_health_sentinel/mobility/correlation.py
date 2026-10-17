"""Exploratory data analysis, descriptive statistics, and correlation analysis.

Calculates:
- Metric-level descriptive statistics (mean, std, median, quartiles, missingness)
- Bivariate Pearson (linear) and Spearman (monotonic rank) correlations
- Two-tailed p-values and effective sample sizes per (region_id, syndrome)
- Automated Matplotlib time-series and correlation visualizations

SCIENTIFIC LIMITATIONS:
1. Shared time trends, weekday reporting cycles, and seasonal sinusoidal drift can produce
   spurious statistical correlations even when no epidemiological relationship exists.
2. Observed correlation NEVER establishes clinical, behavioral, or transmission causation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class CorrelationRecord:
    """Statistical correlation results for a specific pair of variables."""

    region_id: str
    syndrome: str
    mobility_metric: str
    sample_size_n: int
    pearson_r: float | None
    pearson_p_value: float | None
    spearman_rho: float | None
    spearman_p_value: float | None
    is_statistically_significant_05: bool
    interpretation_note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_descriptive_statistics(
    aligned_df: pd.DataFrame,
    mobility_metrics: Sequence[str],
) -> dict[str, Any]:
    """Calculate summary statistics for mobility metrics and syndromic counts."""
    stats_dict: dict[str, Any] = {
        "surveillance_by_syndrome": {},
        "mobility_by_metric": {},
        "missing_counts": {},
    }

    # Surveillance counts by syndrome
    for syndrome, grp in aligned_df.groupby("syndrome"):
        counts = grp["report_count"].dropna()
        stats_dict["surveillance_by_syndrome"][str(syndrome)] = {
            "count": int(len(counts)),
            "mean": round(float(counts.mean()), 2),
            "std": round(float(counts.std()), 2) if len(counts) > 1 else 0.0,
            "min": int(counts.min()) if not counts.empty else None,
            "q25": round(float(counts.quantile(0.25)), 2) if not counts.empty else None,
            "median": round(float(counts.median()), 2) if not counts.empty else None,
            "q75": round(float(counts.quantile(0.75)), 2) if not counts.empty else None,
            "max": int(counts.max()) if not counts.empty else None,
            "missing_count": int(grp["report_count"].isna().sum()),
        }

    # Mobility metrics
    for m in mobility_metrics:
        if m in aligned_df.columns:
            vals = aligned_df[m].dropna()
            stats_dict["mobility_by_metric"][m] = {
                "count": int(len(vals)),
                "mean": round(float(vals.mean()), 2),
                "std": round(float(vals.std()), 2) if len(vals) > 1 else 0.0,
                "min": round(float(vals.min()), 2) if not vals.empty else None,
                "q25": round(float(vals.quantile(0.25)), 2) if not vals.empty else None,
                "median": round(float(vals.median()), 2) if not vals.empty else None,
                "q75": round(float(vals.quantile(0.75)), 2) if not vals.empty else None,
                "max": round(float(vals.max()), 2) if not vals.empty else None,
                "missing_count": int(aligned_df[m].isna().sum()),
            }

    return stats_dict


def compute_correlations(
    aligned_df: pd.DataFrame,
    mobility_metrics: Sequence[str],
) -> list[CorrelationRecord]:
    """Calculate Pearson and Spearman correlation between symptom counts and mobility metrics.

    Evaluates series separately by (region_id, syndrome).
    """
    records: list[CorrelationRecord] = []

    groups = aligned_df.groupby(["region_id", "syndrome"])
    for (region_id, syndrome), grp in groups:
        for metric in mobility_metrics:
            if metric not in grp.columns:
                continue

            # Pairwise complete observations
            subset = grp[["report_count", metric]].dropna()
            n = len(subset)

            if n < 5 or subset["report_count"].std() == 0 or subset[metric].std() == 0:
                # Insufficient variance or sample size
                records.append(
                    CorrelationRecord(
                        region_id=str(region_id),
                        syndrome=str(syndrome),
                        mobility_metric=metric,
                        sample_size_n=n,
                        pearson_r=None,
                        pearson_p_value=None,
                        spearman_rho=None,
                        spearman_p_value=None,
                        is_statistically_significant_05=False,
                        interpretation_note="Insufficient variance or sample size (N < 5) to compute correlation.",
                    )
                )
                continue

            # Pearson r
            r_val, p_pearson = stats.pearsonr(subset["report_count"], subset[metric])
            # Spearman rho
            rho_val, p_spearman = stats.spearmanr(subset["report_count"], subset[metric])

            sig = bool(p_pearson < 0.05 or p_spearman < 0.05)
            note = (
                "Statistically significant association observed (p < 0.05). "
                "Warning: Shared day-of-week and seasonal time trends may account for association; "
                "correlation does NOT prove causal transmission."
                if sig
                else "No statistically significant linear or rank association detected (p >= 0.05)."
            )

            records.append(
                CorrelationRecord(
                    region_id=str(region_id),
                    syndrome=str(syndrome),
                    mobility_metric=metric,
                    sample_size_n=n,
                    pearson_r=round(float(r_val), 4),
                    pearson_p_value=round(float(p_pearson), 4),
                    spearman_rho=round(float(rho_val), 4),
                    spearman_p_value=round(float(p_spearman), 4),
                    is_statistically_significant_05=sig,
                    interpretation_note=note,
                )
            )

    return records


def generate_mobility_figures(
    aligned_df: pd.DataFrame,
    mobility_metrics: Sequence[str],
    output_dir: Path | str,
) -> dict[str, str]:
    """Generate and save publication-quality visualizations for mobility and surveillance trends.

    Returns:
        Mapping of figure name to output file path.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated_figures: dict[str, str] = {}

    df = aligned_df.copy()
    df["observation_date"] = pd.to_datetime(df["observation_date"])

    # Figure 1: Mobility Trends by Region
    fig, axes = plt.subplots(len(mobility_metrics), 1, figsize=(12, 4 * len(mobility_metrics)), sharex=True)
    if len(mobility_metrics) == 1:
        axes = [axes]

    regions = sorted(df["region_id"].unique())
    colors = plt.cm.tab10(np.linspace(0, 1, len(regions)))

    for ax, metric in zip(axes, mobility_metrics):
        for reg, color in zip(regions, colors):
            sub = df[df["region_id"] == reg].drop_duplicates(subset=["observation_date"])
            ax.plot(sub["observation_date"], sub[metric], label=reg, color=color, alpha=0.8, linewidth=1.2)
        ax.set_title(f"Mobility Metric: {metric} (% deviation from baseline)", fontsize=11, fontweight="bold")
        ax.set_ylabel("% Change", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.axhline(0, color="black", linestyle=":", alpha=0.7)

    axes[0].legend(loc="upper right", framealpha=0.9, title="Region")
    axes[-1].set_xlabel("Observation Date", fontsize=10)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.autofmt_xdate()
    fig.suptitle("Synthetic Population Mobility Indicators Across Regions (Phase 4)", fontsize=13, fontweight="bold")
    plt.tight_layout()

    fig1_path = out_dir / "mobility_trends.png"
    fig.savefig(fig1_path, dpi=150)
    plt.close(fig)
    generated_figures["mobility_trends"] = str(fig1_path)

    # Figure 2: Symptom Counts vs Transit Station Mobility (REGION_A Respiratory example)
    sample_df = df[(df["region_id"] == "REGION_A") & (df["syndrome"] == "Respiratory")].sort_values("observation_date")
    if not sample_df.empty:
        fig, ax1 = plt.subplots(figsize=(12, 5))
        ax2 = ax1.twinx()

        ax1.plot(sample_df["observation_date"], sample_df["report_count"], color="#d62728", linewidth=1.5, label="Respiratory Reports (count)")
        ax1.set_ylabel("Daily Report Count", color="#d62728", fontsize=10)
        ax1.tick_params(axis="y", labelcolor="#d62728")

        if "transit_station_pct_change" in sample_df.columns:
            ax2.plot(sample_df["observation_date"], sample_df["transit_station_pct_change"], color="#1f77b4", linewidth=1.2, linestyle="--", label="Transit Station Mobility (%)")
            ax2.set_ylabel("Transit Mobility (% change)", color="#1f77b4", fontsize=10)
            ax2.tick_params(axis="y", labelcolor="#1f77b4")

        ax1.set_title("Dual-Axis Time Series: Respiratory Reports vs Transit Mobility (REGION_A)", fontsize=12, fontweight="bold")
        ax1.set_xlabel("Date", fontsize=10)
        ax1.grid(True, linestyle=":", alpha=0.4)
        fig.autofmt_xdate()
        plt.tight_layout()

        fig2_path = out_dir / "surveillance_mobility_timeseries.png"
        fig.savefig(fig2_path, dpi=150)
        plt.close(fig)
        generated_figures["surveillance_mobility_timeseries"] = str(fig2_path)

    # Figure 3: Correlation Matrix Heatmap
    corr_cols = ["report_count"] + [m for m in mobility_metrics if m in df.columns]
    corr_matrix = df[corr_cols].dropna().corr()

    fig, ax = plt.subplots(figsize=(8, 6))
    cax = ax.matshow(corr_matrix, cmap="coolwarm", vmin=-1, vmax=1)
    fig.colorbar(cax)

    ticks = list(range(len(corr_cols)))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels(corr_cols, rotation=45, ha="left", fontsize=9)
    ax.set_yticklabels(corr_cols, fontsize=9)

    for i in range(len(corr_cols)):
        for j in range(len(corr_cols)):
            val = corr_matrix.iloc[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", color="black" if abs(val) < 0.6 else "white", fontsize=10)

    ax.set_title("Overall Correlation Matrix (Synthetic Dataset)", fontsize=12, fontweight="bold", pad=20)
    plt.tight_layout()

    fig3_path = out_dir / "correlation_matrix.png"
    fig.savefig(fig3_path, dpi=150)
    plt.close(fig)
    generated_figures["correlation_matrix"] = str(fig3_path)

    return generated_figures
