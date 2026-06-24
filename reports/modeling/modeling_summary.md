# Baseline modeling summary

Target: `records_started_on_date` is defined as the number of completed-day raion-level alert records whose local start date is that calendar day.
It is not a count of attacks, military events, or independent nationwide alerts.

National daily activity was selected instead of individual raion modeling because this phase establishes a simple reproducible baseline on one contiguous completed-day series before introducing sparse local models.
The date range is derived dynamically from the processed data: 2026-01-01 through 2026-06-23.
The chronological evaluation split uses the final 35 completed dates, from 2026-05-20 through 2026-06-23, after 139 initial-history days.
Walk-forward validation forecasts each evaluation date using only observations strictly before that date; the actual is then revealed and appended before the next forecast.
Persistence uses the immediately preceding actual, seasonal naive uses the actual from seven days earlier, and the trailing mean uses only the seven previous actual values.

## Historical evaluation metrics

Evaluation actual mean: 311.343; standard deviation: 107.491.

| model | target | evaluation_start | evaluation_end | initial_history_days | evaluation_days | mae | rmse | mean_error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| trailing_mean_7 | records_started_on_date | 2026-05-20 | 2026-06-23 | 139 | 35 | 76.910 | 115.540 | -8.453 |
| persistence | records_started_on_date | 2026-05-20 | 2026-06-23 | 139 | 35 | 96.600 | 133.036 | -0.543 |
| seasonal_7 | records_started_on_date | 2026-05-20 | 2026-06-23 | 139 | 35 | 112.800 | 163.805 | -1.143 |

The lowest historical evaluation MAE is from `trailing_mean_7` (MAE=76.910, RMSE=115.540).
This historical ranking does not imply that the same baseline will remain best in the future.

## One-step-ahead estimates

One-step-ahead statistical baseline estimate of recorded raion alert activity, based only on historical alert-record counts.

| forecast_date | latest_observed_date | model | estimate | historical_evaluation_mae | historical_evaluation_rmse |
| --- | --- | --- | --- | --- | --- |
| 2026-06-24 | 2026-06-23 | persistence | 505.000 | 96.600 | 133.036 |
| 2026-06-24 | 2026-06-23 | seasonal_7 | 197.000 | 112.800 | 163.805 |
| 2026-06-24 | 2026-06-23 | trailing_mean_7 | 390.286 | 76.910 | 115.540 |

These results have limited predictive meaning: the baselines use only past recorded counts and do not include external military, operational, weather, political, or other causal variables.
This is not an operational warning system and must not be interpreted as predicting attacks or safety conditions.
