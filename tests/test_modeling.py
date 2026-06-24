from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from alert_pipeline.modeling import (
    TARGET_COLUMN,
    calculate_metrics,
    evaluation_test_size,
    next_day_estimates,
    run_baseline_evaluation,
    validate_daily_series,
    walk_forward_predictions,
)


def daily(values, start=date(2026, 1, 1)):
    return pd.DataFrame({"local_date": [start + timedelta(days=i) for i in range(len(values))], TARGET_COLUMN: values})


def test_persistence_uses_immediately_preceding_actual():
    result = run_baseline_evaluation(daily(list(range(40))))
    preds = result.predictions.reset_index(drop=True)
    assert preds.loc[0, "persistence_prediction"] == 11
    assert preds.loc[1, "persistence_prediction"] == preds.loc[0, "actual"]


def test_seasonal_naive_uses_exactly_value_from_seven_days_earlier():
    result = run_baseline_evaluation(daily(list(range(40))))
    preds = result.predictions.reset_index(drop=True)
    assert preds.loc[0, "seasonal_7_prediction"] == 5
    assert preds.loc[1, "seasonal_7_prediction"] == 6


def test_trailing_mean_uses_previous_seven_values_only_excluding_forecast_date():
    result = run_baseline_evaluation(daily(list(range(40))))
    preds = result.predictions.reset_index(drop=True)
    assert preds.loc[0, "trailing_mean_7_prediction"] == pytest.approx(sum(range(5, 12)) / 7)
    assert preds.loc[1, "trailing_mean_7_prediction"] == pytest.approx(sum(range(6, 13)) / 7)


def test_walk_forward_predictions_are_chronological():
    preds, _ = walk_forward_predictions(validate_daily_series(daily(list(range(50, 90)))))
    assert preds["local_date"].tolist() == sorted(preds["local_date"].tolist())


def test_revealed_test_actual_becomes_available_only_for_subsequent_dates():
    values = [10] * 12 + [100, 200] + [0] * 26
    result = run_baseline_evaluation(daily(values))
    preds = result.predictions.reset_index(drop=True)
    assert preds.loc[0, "persistence_prediction"] == 10
    assert preds.loc[1, "persistence_prediction"] == 100
    assert preds.loc[2, "persistence_prediction"] == 200


def test_mae_and_rmse_calculated_on_known_example():
    predictions = pd.DataFrame({
        "local_date": [date(2026, 1, 1), date(2026, 1, 2)],
        "actual": [1.0, 3.0],
        "persistence_prediction": [2.0, 5.0],
        "seasonal_7_prediction": [1.0, 1.0],
        "trailing_mean_7_prediction": [4.0, 3.0],
    })
    metrics = calculate_metrics(predictions, initial_history_days=10).set_index("model")
    assert metrics.loc["persistence", "mae"] == pytest.approx(1.5)
    assert metrics.loc["persistence", "rmse"] == pytest.approx(math.sqrt(2.5))


def test_split_uses_final_twenty_percent_with_minimum_28_days():
    assert evaluation_test_size(100) == 28
    assert evaluation_test_size(200) == 40
    preds, initial = walk_forward_predictions(validate_daily_series(daily(list(range(100)))))
    assert initial == 72
    assert len(preds) == 28
    assert preds["local_date"].iloc[0] == date(2026, 3, 14)


def test_zero_target_values_do_not_break_evaluation():
    result = run_baseline_evaluation(daily([0] * 40))
    assert result.metrics["mae"].eq(0).all()
    assert result.next_day_estimates["estimate"].eq(0).all()


def test_missing_calendar_dates_trigger_clear_validation_error():
    frame = daily([1, 2, 3]).drop(index=1)
    with pytest.raises(ValueError, match="not contiguous.*missing local_date"):
        validate_daily_series(frame)


def test_missing_required_columns_trigger_clear_validation_error():
    with pytest.raises(ValueError, match="Missing required column"):
        validate_daily_series(pd.DataFrame({"local_date": [date(2026, 1, 1)]}))


def test_next_day_estimate_uses_only_data_through_latest_completed_date():
    series = validate_daily_series(daily(list(range(1, 41))))
    preds, initial = walk_forward_predictions(series)
    metrics = calculate_metrics(preds, initial)
    estimates = next_day_estimates(series, metrics).set_index("model")
    assert estimates.loc["persistence", "latest_observed_date"] == date(2026, 2, 9)
    assert estimates.loc["persistence", "forecast_date"] == date(2026, 2, 10)
    assert estimates.loc["persistence", "estimate"] == 40
    assert estimates.loc["seasonal_7", "estimate"] == 34
    assert estimates.loc["trailing_mean_7", "estimate"] == pytest.approx(sum(range(34, 41)) / 7)


def test_no_current_partial_day_data_is_read_by_modeling_script():
    from pathlib import Path

    script_text = Path("scripts/run_baselines.py").read_text(encoding="utf-8")
    assert "daily_2026_raion_activity.csv" in script_text
    assert "current_partial_day" not in script_text
