"""Lagged cross-correlation analysis between mobility indicators and symptom reports.

Evaluates whether historical mobility shifts precede changes in syndromic reporting:
- Explicit lag sign conventions (+k: mobility leads symptoms by k days)
- True calendar-date alignment (immune to date sequence gaps)
- Sample size and p-value tracking for each lag offset
- Cross-correlation visualization across lag spectrum (-7 to +14 days)

SCIENTIFIC CAUTION:
Elevated cross-correlation at a specific lag offset is purely observational.
It reflects synthetic generating dynamics or macro time-series structure and does
NOT prove clinical incubation periods, behavioral transmission, or predictive causality.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class LagCorrelationPoint:
    """Correlation metric at a specific temporal lag offset."""

    lag_days: int
    sample_size_n: int
    pearson_r: float | None
    pearson_p_value: float | None
    spearman_rho: float | None
    spearman_p_value: float | None
    convention_description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SeriesLagAnalysis:
    """Lagged cross-correlation profile for a (region_id, syndrome, mobility_metric) tuple."""

    region_id: str
    syndrome: str
    mobility_metric: str
    best_positive_lag_days: int | None
    best_positive_lag_pearson_r: float | None
    lag_points: list[LagCorrelationPoint]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["lag_points"] = [p.to_dict() for p in self.lag_points]
        return d


def compute_lagged_correlations(
    aligned_df: pd.DataFrame,
    mobility_metric: str,
    min_lag: int = -7,
    max_lag: int = 14,
) -> list[SeriesLagAnalysis]:
    """Calculate cross-correlations across a range of lag offsets.

    Lag Convention:
    - Positive Lag (+k): Mobility at day (t - k) paired with symptoms at day t.
      Mobility precedes symptom reports by k calendar days.
    - Zero Lag (0): Same-day observation pairing.
    - Negative Lag (-k): Mobility at day (t + k) paired with symptoms at day t.
      Mobility follows symptom reports by k calendar days.

    Args:
        aligned_df: Joined table with observation_date, region_id, syndrome, report_count, and mobility columns.
        mobility_metric: Name of the mobility metric column to analyze.
        min_lag: Minimum lag in days (default: -7).
        max_lag: Maximum lag in days (default: +14).

    Returns:
        List of SeriesLagAnalysis objects for each region-syndrome combination.
    """
    if mobility_metric not in aligned_df.columns:
        raise ValueError(f"Metric '{mobility_metric}' not found in aligned DataFrame columns.")

    results: list[SeriesLagAnalysis] = []

    # Ensure date objects
    df = aligned_df.copy()
    if not isinstance(df["observation_date"].iloc[0], date):
        df["observation_date"] = pd.to_datetime(df["observation_date"]).dt.date

    # Group by region and syndrome
    groups = df.groupby(["region_id", "syndrome"])

    for (region_id, syndrome), grp in groups:
        # Build date -> value lookups for exact calendar matching
        mob_map: dict[date, float] = {}
        for _, row in grp.dropna(subset=[mobility_metric]).iterrows():
            mob_map[row["observation_date"]] = float(row[mobility_metric])

        surv_rows = grp.dropna(subset=["report_count"]).sort_values("observation_date")

        lag_points: list[LagCorrelationPoint] = []
        best_pos_lag: int | None = None
        max_abs_r: float = -1.0
        best_pos_r: float | None = None

        for lag in range(min_lag, max_lag + 1):
            if lag > 0:
                desc = f"Mobility leads symptom reports by +{lag} days: Mobility(t - {lag}) vs Count(t)"
            elif lag == 0:
                desc = "Simultaneous: Mobility(t) vs Count(t)"
            else:
                desc = f"Mobility lags symptom reports by {abs(lag)} days: Mobility(t + {abs(lag)}) vs Count(t)"

            x_counts: list[float] = []
            y_mobs: list[float] = []

            for _, row in surv_rows.iterrows():
                cur_date = row["observation_date"]
                # For lag +k, we look for mobility at (cur_date - k days)
                target_mob_date = cur_date - timedelta(days=lag)
                if target_mob_date in mob_map:
                    x_counts.append(float(row["report_count"]))
                    y_mobs.append(mob_map[target_mob_date])

            n = len(x_counts)
            if n < 10 or np.std(x_counts) == 0 or np.std(y_mobs) == 0:
                lag_points.append(
                    LagCorrelationPoint(
                        lag_days=lag,
                        sample_size_n=n,
                        pearson_r=None,
                        pearson_p_value=None,
                        spearman_rho=None,
                        spearman_p_value=None,
                        convention_description=desc,
                    )
                )
                continue

            r_val, p_pearson = stats.pearsonr(x_counts, y_mobs)
            rho_val, p_spearman = stats.spearmanr(x_counts, y_mobs)

            r_rounded = round(float(r_val), 4)
            lag_points.append(
                LagCorrelationPoint(
                    lag_days=lag,
                    sample_size_n=n,
                    pearson_r=r_rounded,
                    pearson_p_value=round(float(p_pearson), 4),
                    spearman_rho=round(float(rho_val), 4),
                    spearman_p_value=round(float(p_spearman), 4),
                    convention_description=desc,
                )
            )

            # Check for strongest positive lead lag
            if lag > 0 and abs(r_rounded) > max_abs_r:
                max_abs_r = abs(r_rounded)
                best_pos_r = r_rounded
                best_pos_lag = lag

        results.append(
            SeriesLagAnalysis(
                region_id=str(region_id),
                syndrome=str(syndrome),
                mobility_metric=mobility_metric,
                best_positive_lag_days=best_pos_lag,
                best_positive_lag_pearson_r=best_pos_r,
                lag_points=lag_points,
            )
        )

    return results


def plot_cross_correlation_profile(
    lag_analyses: Sequence[SeriesLagAnalysis],
    output_path: Path | str,
    target_region: str = "REGION_A",
    target_syndrome: str = "Respiratory",
) -> Path:
    """Plot cross-correlation curve across lags for a target region and syndrome."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError(
            "matplotlib is required for plotting cross-correlation profiles. "
            "Install matplotlib or full package dependencies."
        ) from exc

    # Find matching analysis
    match = next(
        (a for a in lag_analyses if a.region_id == target_region and a.syndrome == target_syndrome),
        None,
    )
    if not match and lag_analyses:
        match = lag_analyses[0]

    if not match:
        return out_file

    lags = [p.lag_days for p in match.lag_points]
    pearsons = [p.pearson_r if p.pearson_r is not None else 0.0 for p in match.lag_points]
    spearmans = [p.spearman_rho if p.spearman_rho is not None else 0.0 for p in match.lag_points]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(lags, pearsons, marker="o", linewidth=1.5, color="#1f77b4", label="Pearson r")
    ax.plot(lags, spearmans, marker="s", linewidth=1.5, color="#ff7f0e", linestyle="--", label="Spearman rho")

    ax.axvline(0, color="gray", linestyle=":", linewidth=1.2, label="Zero Lag (Same Day)")
    ax.axhline(0, color="black", linestyle="-", linewidth=0.8, alpha=0.5)

    ax.set_title(
        f"Cross-Correlation Profile: {match.syndrome} vs {match.mobility_metric} ({match.region_id})\n"
        f"Positive Lag (+k): Mobility leads symptoms by k days",
        fontsize=11,
        fontweight="bold",
    )
    ax.set_xlabel("Lag Offset (Days) [Negative: Symptoms Lead | Positive: Mobility Leads]", fontsize=10)
    ax.set_ylabel("Correlation Coefficient", fontsize=10)
    ax.set_xticks(lags)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="best", framealpha=0.9)
    plt.tight_layout()

    fig.savefig(out_file, dpi=150)
    plt.close(fig)
    return out_file
