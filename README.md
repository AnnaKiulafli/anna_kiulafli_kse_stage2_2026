# Ukraine air raid alerts time series

Focused preprocessing for current 2026 raion-level air raid alert analysis.

## Scope

Primary current analysis uses raion records from `2026-01-01` through the latest fully completed Europe/Kyiv local calendar day available at runtime. The endpoint is dynamic:

```python
latest_complete_day = min(current_local_date - one_day, latest_local_date_in_dataset)
```

There is no hard-coded June or July 2026 maximum date, so July 2026 and later raion records are included automatically when they are present and complete.

`data/processed/current_partial_day_raion_alerts.csv` contains raion alert records starting on the current partial local day. These records are excluded from completed daily series, rolling statistics, and future model-training targets.

## Historical context

`HISTORICAL_OBLAST_END_DATE = "2025-07-31"` defines a separate historically comparable oblast-level context period for `data/processed/historical_oblast_context.csv`. The cutoff defines a separate historically comparable oblast-level context period. It does not define the endpoint of the current 2026 analysis.

The historical oblast context dataset must never be joined directly to the 2026 raion-level count series.

## Daily duration metric

`daily_2026_raion_activity.csv` reports `total_raion_time_under_alert_minutes`: the sum of non-overlapping alert minutes across represented raions. It may exceed 1,440 minutes per calendar day because several raions can be under alert simultaneously. It is not nationwide clock time under alert.
