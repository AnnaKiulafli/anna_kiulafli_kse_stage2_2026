# Time Series Analysis of Air Raid Alerts in Ukraine

## Project overview

This project analyses recorded Ukrainian air-raid alert data as a nationwide administrative time series. The primary analysis uses **raion-level** records from `2026-01-01` through the latest fully completed `Europe/Kyiv` local calendar day available in the downloaded dataset. The endpoint is calculated dynamically during processing, and the current partial local day is intentionally excluded from analysis and modeling.

The results describe recorded alert activity in the processed source data. They must not be interpreted as predictions of attacks, safety conditions, military activity, or operational risk.

## Research questions

1. How does recorded nationwide raion-level alert activity change over time?
2. Which oblasts and raions account for the largest amounts of recorded alert activity?
3. Are there weekday, monthly, duration, or coverage patterns?
4. How well do simple historical baselines estimate the next completed day's recorded alert count?

## Data source

The raw input is downloaded from the public dataset repository `Vadimkin/ukrainian-air-raid-sirens-dataset`, file `official_data_en.csv`.

The source contains administrative levels including oblast, raion, and hromada records. This repository does **not** treat the file as a complete city-level dataset. For the main 2026 series, `oblast + raion` is used as the primary geographic identifier.

Important granularity decisions:

- Kyiv City and other non-raion records are audited separately from the primary raion-level series.
- Historical oblast-level context is kept separate from the 2026 raion-level series.
- The historical oblast-level cutoff is `2025-07-31`.
- Historical oblast data is not joined directly to the current raion series because the administrative granularity differs.

## Data-processing methodology

The preprocessing pipeline applies the following decisions before producing analysis tables:

- Deduplicate records exactly using the original source fields.
- Parse source timestamps as UTC-aware datetimes and convert analysis dates to `Europe/Kyiv` local time.
- Calculate the latest complete local calendar day dynamically from the downloaded data and the current local date.
- Separate completed-day records from current partial-day records.
- Filter the primary 2026 series strictly to `level == "raion"`.
- Build a complete daily calendar from `2026-01-01` through the latest completed day, including dates with zero recorded alert activity in the processed source data.
- Split alert intervals at local midnight so duration can be allocated to the correct local calendar dates.
- Merge overlapping intervals within each `oblast + raion + local_date` before summing duration.
- Exclude missing-finish, zero-duration, negative-duration, and longer-than-seven-day intervals from duration metrics.
- Preserve anomaly audits and non-raion audit outputs separately from the primary raion time series.

`total_raion_time_under_alert_minutes` is a sum of non-overlapping alert minutes across represented raions. National raion-minutes can exceed 1,440 minutes per day because several raions may be under alert simultaneously.

## Repository structure

| Path | Role |
| --- | --- |
| `scripts/` | Command-line entry points for downloading data, building processed datasets, running EDA, and running baselines. |
| `src/alert_pipeline/` | Reusable preprocessing, EDA, and modeling code used by the scripts and tests. |
| `tests/` | Automated tests for preprocessing, EDA, and baseline modeling behavior. |
| `data/processed/` | Locally generated processed datasets, anomaly CSVs, partial-day files, and non-raion audit outputs. |
| `reports/eda/` | Committed EDA summaries and tables; generated figures are ignored where configured. |
| `reports/modeling/` | Committed baseline modeling metrics, walk-forward predictions, next-day analytical snapshots, and summaries. |
| `notebooks/` | Notebook workspace for nationwide EDA review. |

Main scripts:

- `scripts/download_data.py` downloads `official_data_en.csv` into the local raw data directory.
- `scripts/build_datasets.py` builds processed current, historical, anomaly, partial-day, and audit datasets.
- `scripts/run_eda.py` generates EDA tables, figures, and `reports/eda/eda_summary.md`.
- `scripts/run_baselines.py` runs leakage-free walk-forward baseline evaluation and writes modeling reports.

## Reproducibility

Run the workflow from the repository root in this order:

```bash
python -m pip install -r requirements.txt
python scripts/download_data.py
python scripts/build_datasets.py
python scripts/run_eda.py
python scripts/run_baselines.py
pytest -q
python -m py_compile scripts/*.py src/alert_pipeline/*.py
```

Raw and processed data files are generated locally and ignored by Git. Figures are also generated locally and ignored where configured. The committed Markdown and CSV reports should be regenerated when the source dataset advances so that README values match the current snapshot.

## Exploratory analysis

The committed EDA output summarizes completed-day 2026 raion-level records from `2026-01-01` through `2026-06-23`.

| Finding | Value |
| --- | ---: |
| Dynamic analysis date range | `2026-01-01` to `2026-06-23` |
| Completed daily rows | 174 |
| Represented oblast values | 23 |
| Unique `oblast + raion` units | 118 |
| Completed raion records | 48,286 |
| Non-raion completed records audited separately | 4,135 |
| Total allocated valid raion alert minutes | 6,444,838.0 |
| Unusually high-activity days flagged by IQR rule | 13 |

The IQR rule flagged days where total raion-minutes exceeded 54,489.14. Examples include `2026-01-20` with 61,132.82 raion-minutes, `2026-02-03` with 67,486.82, and `2026-02-07` with 73,746.35.

Leading oblasts by allocated valid raion alert minutes were:

| Oblast | Allocated raion alert minutes | Completed raion records | Represented raions |
| --- | ---: | ---: | ---: |
| Donetska oblast | 1,771,489.2 | 3,760 | 8 |
| Zaporizka oblast | 978,515.3 | 4,295 | 5 |
| Kharkivska oblast | 824,124.3 | 7,386 | 7 |
| Dnipropetrovska oblast | 590,983.2 | 5,458 | 7 |
| Sumska oblast | 579,187.4 | 4,466 | 5 |

The highest raion-level allocated-minute rows are tied Donetska oblast raions: Bakhmutskyi, Horlivskyi, Donetskyi, Mariupolskyi, and Kramatorskyi raions each have 221,436.15 allocated minutes, 470 completed records, and 174 active days in the processed source data.

Coverage tables should be read as recorded activity in the processed source data. A date or unit with no rows means no recorded alert activity in the processed source data, not proof that no alert occurred.

## Baseline modeling

The modeling target is `records_started_on_date`: the number of completed-day raion-level alert records whose local start date is that calendar day. It is not a count of attacks, independent military events, or safety incidents.

The evaluation is chronological walk-forward validation:

- The final 20% of completed dates are used for evaluation, with a minimum of 28 evaluation days.
- In the current snapshot, evaluation covers 35 dates from `2026-05-20` through `2026-06-23`, after 139 initial-history days.
- Each evaluation date is forecast using only earlier actuals.
- The actual value is revealed and appended only after forecasting that date.

Three deliberately simple baselines are evaluated:

- `persistence`: use the immediately preceding actual value.
- `seasonal_7`: use the actual value from seven days earlier.
- `trailing_mean_7`: use the mean of the seven previous actual values.

| Model | MAE | RMSE |
| --- | ---: | ---: |
| `trailing_mean_7` | 76.910 | 115.540 |
| `persistence` | 96.600 | 133.036 |
| `seasonal_7` | 112.800 | 163.805 |

`trailing_mean_7` had the lowest historical evaluation MAE in this snapshot. This historical ranking does not guarantee future performance.

The generated modeling figure compares historical actual values with the three walk-forward baseline estimates, and the final markers show the three one-step-ahead estimates for the dynamic next forecast date. Values represent recorded raion-level alert records started on a date, not attacks or safety forecasts. Generate the figure locally with `python scripts/run_baselines.py`.

One-step-ahead baseline estimates in `reports/modeling/next_day_baseline_estimates.csv` are a dated analytical snapshot for forecast date `2026-06-24`, using data observed through `2026-06-23`: persistence 505.000, seasonal_7 197.000, and trailing_mean_7 390.286. These values are not operational predictions.

## Limitations and responsible interpretation

- Source coverage may be incomplete or change over time.
- Administrative granularity is not constant historically.
- Raion records are not equivalent to independent attacks.
- Simultaneous records across raions are counted separately.
- The current partial day is intentionally excluded from analysis and modeling.
- Baseline models use only historical recorded counts.
- Military, operational, political, weather, infrastructure, and other external causal variables are absent.
- This is not a warning, military, or safety forecasting system.

## Tests

The current test suite contains 33 tests. It covers preprocessing, timezone and complete-day logic, cross-midnight interval allocation, overlap merging, geographic reconciliation, EDA validation, leakage-free walk-forward modeling, and metric calculations.

## AI assistance

ChatGPT and Codex were used for project planning, prompt development, implementation scaffolding, code review, test design, debugging, and documentation refinement. The repository owner retained the scope, methodological, review, and merge decisions. The summary in `docs/AI_ASSISTANCE_SUMMARY.md` is only a concise summary of AI-assisted work, not the full AI conversation log required for submission.

## References

- Dataset: `Vadimkin/ukrainian-air-raid-sirens-dataset`, `official_data_en.csv`.
- Python libraries used in the workflow include pandas for data processing, matplotlib for generated figures, and pytest for automated validation.
