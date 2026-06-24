# Nationwide Ukrainian raion air-raid alert EDA

## Dataset scope
This report summarizes completed-day processed 2026 Ukrainian raion-level alert records from 2026-01-01 through **2026-06-23**. It uses `oblast + raion` as the administrative identifier and excludes current partial-day records from time-series summaries. Results describe historical recorded alert activity only and are not real-time safety or operational guidance.

## Main nationwide findings
- Latest completed date: **2026-06-23**.
- Completed daily rows: **174**.
- Represented oblast values: **23**.
- Unique oblast + raion units: **118**.
- Total completed raion records: **48286**; non-raion records: **4135**.
- Total allocated valid raion alert minutes: **6,444,838.0**.
- Unusually high-activity days use the transparent IQR rule: total minutes > Q3 + 1.5*IQR (54489.14); flagged days: **13**.

## Coverage limitations
Coverage is based on records present in the processed source data, not an external authoritative administrative register. A concise oblast coverage table is in `reports/eda/tables/coverage_by_oblast.csv`; per-raion first/last dates and months-with-no-recorded-alerts audits are in sibling CSV files.

## Raion vs non-raion distinction
Primary analysis covers the whole country at oblast + raion level. Non-raion records are audited separately by level, oblast, raion, and hromada. These are all available non-raion administrative records in the dataset, not a complete list of Ukrainian cities; Kyiv City is only one administrative exception in this audit.

## Duration anomaly handling
Duration statistics exclude missing `finished_at`, zero-duration, negative-duration, and intervals longer than seven days. Reported anomaly counts in the completed raion data are: {'zero_duration_records': 0, 'negative_duration_records': 0, 'longer_than_7_day_records': 0, 'missing_finished_at_records': 0}.

## Historical context
Historical oblast context date range: **2022-03-15 to 2025-07-31**. It is summarized separately in `historical_monthly_totals.csv` and `historical_granularity.csv` because historical oblast-level counts are a different administrative granularity and are not directly comparable with the current 2026 raion-level series.

## Generated tables and figures
Tables are under `reports/eda/tables/`; figures are under `reports/eda/figures/`. Core figures: national daily activity, monthly activity, monthly recorded raion activity presence, top oblasts, top raions, valid duration distribution, and raion versus non-raion share.
