# PublicHealthSentinel — Phase 4 Mobility Analysis and Predictive Evaluation Report

> **SYNTHETIC-DATA EXPERIMENT DISCLOSURE**
> All surveillance records and mobility indicators evaluated herein are synthetically generated.
> Observed statistical associations and predictive performance differences reflect synthetic stochastic
> parameters and shared time-trend dynamics. They do **NOT** demonstrate real-world clinical, behavioral,
> or epidemiological transmission relationships.

---

## 1. Executive Summary

- **Evaluation Dataset**: 2700 aligned observations across 5 regions.
- **Date Span**: 2026-01-01 to 2026-06-29.
- **Model Comparison**: Chronological split (70% train / 30% test). Target = Next-Day Syndromic Surge.
- **Baseline F1-Score**: `0.1864` (Precision: `0.1073`, Recall: `0.7097`, Specificity: `0.7401`).
- **Augmented F1-Score**: `0.2300` (Precision: `0.1361`, Recall: `0.7419`, Specificity: `0.7926`).
- **Delta F1-Score**: `+0.0436` (`Delta Precision: +0.0288`, `Delta Recall: +0.0322`).
- **Performance Verdict**: Mobility-augmented model showed positive improvement in F1-score (+0.0436) over the surveillance-only baseline on held-out test data in this synthetic experiment.

---

## 2. Dataset Alignment and Data Integrity Audit

| Alignment Parameter | Value | Integrity Verification |
| :--- | :--- | :--- |
| Raw Surveillance Observations | 2700 rows | Input verified |
| Raw Mobility Records | 2700 rows | Input verified |
| Pivoted Wide Mobility | 900 rows | Grouped by `(observation_date, region_id)` |
| Aligned Dataset Rows | 2700 rows | **Zero Cartesian row multiplication** |
| Complete Cases (Surveillance + Mobility) | 2700 rows | 100% complete overlap |
| Missing Mobility Rows | 0 | Preserved as `NaN` (no silent imputation) |
| Duplicate Keys Detected | 0 | Candidate key uniqueness enforced |
| Mobility Metrics Aligned | `residential_pct_change, transit_station_pct_change, workplace_pct_change` | Standardized column names |
| Regions Evaluated | `REGION_A, REGION_B, REGION_C, REGION_D, REGION_E` | Preserved regional identifiers |

---

## 3. Exploratory Statistics and Correlation Analysis

### 3.1 Syndromic Surveillance Summaries

| Syndrome | Observation Count | Mean Reports | Std Dev | Median (Q1 - Q3) | Min - Max |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Febrile** | 900 | 79.50 | 45.14 | 70.0 (43.0 - 108.0) | 13 - 250 |
| **Gastrointestinal** | 900 | 52.60 | 29.61 | 45.0 (28.0 - 72.0) | 5 - 140 |
| **Respiratory** | 900 | 122.95 | 67.82 | 105.5 (67.0 - 170.0) | 26 - 337 |

### 3.2 Mobility Indicator Distributions

| Mobility Indicator | Non-null Count | Mean (% change) | Std Dev | Median | Range [Min, Max] |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `residential_pct_change` | 2700 | +9.52% | 6.87 | +8.45% | [-3.69%, +27.19%] |
| `transit_station_pct_change` | 2700 | -20.69% | 10.57 | -18.04% | [-48.13%, +1.33%] |
| `workplace_pct_change` | 2700 | -24.54% | 26.09 | -10.82% | [-74.91%, +5.43%] |

### 3.3 Selected Pairwise Correlations (Pearson r & Spearman rho)

| Region | Syndrome | Mobility Metric | N | Pearson r (p-val) | Spearman rho (p-val) | Significant (p < 0.05) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `REGION_A` | Febrile | `residential_pct_change` | 180 | -0.4206 (0.0000) | -0.4318 (0.0000) | Yes |
| `REGION_A` | Febrile | `transit_station_pct_change` | 180 | +0.4068 (0.0000) | +0.3728 (0.0000) | Yes |
| `REGION_A` | Febrile | `workplace_pct_change` | 180 | +0.4863 (0.0000) | +0.3828 (0.0000) | Yes |
| `REGION_A` | Gastrointestinal | `residential_pct_change` | 180 | -0.3831 (0.0000) | -0.3406 (0.0000) | Yes |
| `REGION_A` | Gastrointestinal | `transit_station_pct_change` | 180 | +0.3669 (0.0000) | +0.3468 (0.0000) | Yes |
| `REGION_A` | Gastrointestinal | `workplace_pct_change` | 180 | +0.4402 (0.0000) | +0.3817 (0.0000) | Yes |
| `REGION_A` | Respiratory | `residential_pct_change` | 180 | -0.2249 (0.0024) | -0.3584 (0.0000) | Yes |
| `REGION_A` | Respiratory | `transit_station_pct_change` | 180 | +0.3632 (0.0000) | +0.4061 (0.0000) | Yes |

> **Statistical Notice on Correlation Interpretation**:
> Correlation measures bivariate linear (Pearson) or monotonic (Spearman) association.
> In public health surveillance, apparent correlations between mobility metrics (e.g. residential vs workplace)
> and clinic visits are frequently confounded by shared exogenous cycles (e.g. weekend clinic closures and weekend
> residential increases). Observed statistical significance must NOT be conflated with epidemiological transmission lead.

---

## 4. Temporal Lagged Cross-Correlation Analysis

- **Sign Convention**: **Positive Lag (+k)** specifies that mobility observations at day `(t - k)` are paired with symptom reports at day `t` (**mobility leads symptoms**).
- **Zero Lag (0)**: Synchronous same-day pairing.
- **Negative Lag (-k)**: Mobility at day `(t + k)` paired with symptoms at day `t` (**mobility follows symptoms**).
- **Temporal Window**: Evaluated across `[-7, +14]` calendar days.

| Region | Syndrome | Metric | Best Lead Lag (+k days) | Max Lead Pearson r | Sample Size Range |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `REGION_A` | Febrile | `residential_pct_change` | +9 days | +0.5120 | N = 166 to 180 |
| `REGION_A` | Gastrointestinal | `residential_pct_change` | +9 days | +0.4672 | N = 166 to 180 |
| `REGION_A` | Respiratory | `residential_pct_change` | +9 days | +0.5123 | N = 166 to 180 |
| `REGION_B` | Febrile | `residential_pct_change` | +7 days | -0.3972 | N = 166 to 180 |
| `REGION_B` | Gastrointestinal | `residential_pct_change` | +9 days | +0.4596 | N = 166 to 180 |
| `REGION_B` | Respiratory | `residential_pct_change` | +9 days | +0.5612 | N = 166 to 180 |

---

## 5. Predictive Modeling and Comparative Evaluation

### 5.1 Experimental Setup & Target Definition
- **Target Variable**: `Next-day syndromic surge: count(t+1) > rolling_median(t) + 2.5 * rolling_MAD(t) (14-day causal window)`
- **Training Period**: `2026-01-14` to `2026-05-10` (1755 observations)
- **Held-Out Test Period**: `2026-05-11` to `2026-06-28` (735 observations, 31 positive surges)
- **Validation Strategy**: Strict chronological split (zero random shuffling; zero future leakage).
- **Model Class**: Regularized L2 Logistic Regression with balanced class weighting.

### 5.2 Comparative Performance Table

| Evaluation Metric | Model A: Surveillance-Only | Model B: Surveillance + Mobility | Absolute Difference (B - A) |
| :--- | :--- | :--- | :--- |
| **F1-Score** | **`0.1864`** | **`0.2300`** | **`+0.0436`** |
| **Precision** | `0.1073` | `0.1361` | `+0.0288` |
| **Recall (Sensitivity)** | `0.7097` | `0.7419` | `+0.0322` |
| **Specificity (TNR)** | `0.7401` | `0.7926` | `+0.0525` |
| **Accuracy** | `0.7388` | `0.7905` | `+0.0517` |
| **Confusion Matrix (TN, FP, FN, TP)** | `521, 183, 9, 22` | `558, 146, 8, 23` | — |

### 5.3 Model Interpretability and Feature Importance

#### Baseline Surveillance Model Coefficients
- `surv_count_rolling_mean_7`: `+5.0675`
- `surv_count_lag_3`: `-2.3379`
- `surv_count_lag_2`: `-2.0924`
- `surv_count_lag_1`: `-0.9809`
- `surv_count_lag_0`: `-0.7525`
- `day_of_week`: `+0.7387`
- `surv_count_velocity`: `+0.6277`
- `surv_count_lag_7`: `+0.5156`
- `surv_count_rolling_std_7`: `-0.0771`

#### Augmented Model Mobility Coefficients (Selected)
- `mob_workplace_pct_change_lag_1`: `-1.4198`
- `mob_transit_station_pct_change_rolling_mean_7`: `+0.9089`
- `mob_workplace_pct_change_lag_0`: `-0.8298`
- `mob_workplace_pct_change_lag_3`: `-0.6426`
- `mob_residential_pct_change_lag_7`: `+0.5317`
- `mob_residential_pct_change_lag_0`: `-0.5036`
- `mob_workplace_pct_change_velocity`: `+0.4937`
- `mob_residential_pct_change_lag_1`: `-0.4538`

---

## 6. Generated Visualizations

| Figure Description | File Path |
| :--- | :--- |
| mobility_trends | `reports\mobility\figures\mobility_trends.png` |
| surveillance_mobility_timeseries | `reports\mobility\figures\surveillance_mobility_timeseries.png` |
| correlation_matrix | `reports\mobility\figures\correlation_matrix.png` |
| cross_correlation_profile | `reports\mobility\figures\cross_correlation_lags.png` |

---

## 7. Methodological and Epidemiological Limitations

1. **Synthetic Data Realism**: Synthetic datasets capture mathematical generating equations and stochastic noise. They do not emulate true human behavioral adaptations, diagnostic testing delays, or multi-modal transmission dynamics.
2. **Confounding by Day-of-Week**: Both clinic reporting counts and commercial/transit mobility indicators exhibit profound 7-day periodicity. Apparent lead-lag signals can easily arise from harmonic phase shifts rather than pathogen incubation.
3. **Geographic Granularity**: Aggregated regional indicators may mask localized suburban or community transmission clusters.
4. **No Replacement for Clinical Diagnosis**: Anomaly signals and mobility shifts serve solely as exploratory situational awareness tools, not clinical diagnoses.
