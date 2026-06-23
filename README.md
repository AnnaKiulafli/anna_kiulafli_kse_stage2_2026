# Ukraine air raid alerts time series

Focused preprocessing for current 2026 raion-level air raid alert analysis.

## Scope

Primary current analysis uses raion records from `2026-01-01` through the latest fully completed Europe/Kyiv local calendar day available at runtime. The endpoint is dynamic:

```python
latest_complete_day = min(current_local_date - one_day, latest_local_date_in_dataset)
```

There is no hard-coded June or July 2026 maximum date, so July 2026 and later raion records are included automatically when they are present and complete.

`data/processed/current_partial_day_raion_alerts.csv` contains raion alert records starting on the current partial local day. `data/processed/current_2026_non_raion_records_complete_days.csv` and `data/processed/current_partial_day_non_raion_records.csv` preserve all available non-raion administrative records (`level != "raion"`) for the same completed-day and partial-day windows. These records are excluded from completed raion daily series, rolling statistics, and future model-training targets.

## Historical context

`HISTORICAL_OBLAST_END_DATE = "2025-07-31"` defines a separate historically comparable oblast-level context period for `data/processed/historical_oblast_context.csv`. The cutoff defines a separate historically comparable oblast-level context period. It does not define the endpoint of the current 2026 analysis.

The historical oblast context dataset must never be joined directly to the 2026 raion-level count series.

## Daily duration metric

`daily_2026_raion_activity.csv` reports a complete calendar from `2026-01-01` through `latest_complete_day`. `records_started_on_date` counts original raion records whose local start date is that calendar date, while `interval_segments` counts calendar-day split interval pieces used for allocation. `total_raion_time_under_alert_minutes` is the sum of non-overlapping alert minutes across represented oblast+raion units. It may exceed 1,440 minutes per calendar day because several raions can be under alert simultaneously. It is not nationwide clock time under alert. Zero-duration, negative-duration, longer-than-seven-day, and missing-finished-at records are written to separate anomaly CSV files and excluded from this duration metric.
