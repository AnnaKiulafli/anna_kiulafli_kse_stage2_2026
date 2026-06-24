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


def load_run_baselines_module():
    import importlib.util
    from pathlib import Path

    module_path = Path("scripts/run_baselines.py")
    spec = importlib.util.spec_from_file_location("run_baselines", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_plot_predictions_includes_dynamic_forecast_markers_without_future_actual(tmp_path, monkeypatch):
    import matplotlib.pyplot as plt

    plot_predictions = load_run_baselines_module().plot_predictions

    result = run_baseline_evaluation(daily(list(range(1, 41))))
    output = tmp_path / "walk_forward_actual_vs_baselines.png"

    monkeypatch.setattr(plt, "close", lambda *args, **kwargs: None)
    plot_predictions(result, output)

    assert output.exists()
    assert output.stat().st_size > 0

    ax = plt.gcf().axes[0]
    forecast_date = result.next_day_estimates["forecast_date"].iloc[0]
    last_observed_date = result.predictions["local_date"].iloc[-1]
    expected_estimates = result.next_day_estimates.set_index("model")["estimate"].to_dict()

    actual_line = next(line for line in ax.lines if line.get_label() == "Actual")
    assert list(actual_line.get_xdata())[-1] == last_observed_date
    assert forecast_date not in list(actual_line.get_xdata())

    model_labels = {
        "persistence": "Persistence",
        "seasonal_7": "Seasonal naive (7-day)",
        "trailing_mean_7": "Trailing 7-day mean",
    }
    for model, label in model_labels.items():
        line = next(line for line in ax.lines if line.get_label() == label)
        assert list(line.get_xdata())[-1] == forecast_date
        assert list(line.get_ydata())[-1] == pytest.approx(expected_estimates[model])

    annotation_text = "\n".join(text.get_text() for text in ax.texts)
    for model, estimate in expected_estimates.items():
        assert f"{model}: {estimate:.0f}" in annotation_text

    plt.close("all")


def test_plot_predictions_preserves_baseline_metrics_and_predictions(tmp_path):
    plot_predictions = load_run_baselines_module().plot_predictions

    result = run_baseline_evaluation(daily(list(range(1, 41))))
    metrics_before = result.metrics.copy(deep=True)
    predictions_before = result.predictions.copy(deep=True)

    plot_predictions(result, tmp_path / "walk_forward_actual_vs_baselines.png")

    pd.testing.assert_frame_equal(result.metrics, metrics_before)
    pd.testing.assert_frame_equal(result.predictions, predictions_before)
