from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pandas as pd

TARGET_COLUMN = "records_started_on_date"
REQUIRED_COLUMNS = ["local_date", TARGET_COLUMN]
MODEL_COLUMNS = {
    "persistence": "persistence_prediction",
    "seasonal_7": "seasonal_7_prediction",
    "trailing_mean_7": "trailing_mean_7_prediction",
}
TARGET_DESCRIPTION = "completed-day raion-level alert records whose local start date is that calendar day"


@dataclass(frozen=True)
class BaselineResult:
    metrics: pd.DataFrame
    predictions: pd.DataFrame
    next_day_estimates: pd.DataFrame


def load_daily_series(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required processed daily activity file is missing: {path}")
    return validate_daily_series(pd.read_csv(path))


def validate_daily_series(df: pd.DataFrame) -> pd.DataFrame:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")
    out = df[REQUIRED_COLUMNS].copy()
    out["local_date"] = pd.to_datetime(out["local_date"], errors="raise").dt.date
    out[TARGET_COLUMN] = pd.to_numeric(out[TARGET_COLUMN], errors="raise")
    out = out.sort_values("local_date", kind="mergesort").reset_index(drop=True)
    if out["local_date"].duplicated().any():
        dupes = out.loc[out["local_date"].duplicated(), "local_date"].astype(str).tolist()
        raise ValueError(f"Duplicate local_date value(s) found: {', '.join(dupes[:5])}")
    expected = pd.date_range(out["local_date"].min(), out["local_date"].max(), freq="D").date
    if list(out["local_date"]) != list(expected):
        present = set(out["local_date"])
        missing_dates = [d.isoformat() for d in expected if d not in present]
        raise ValueError(f"Daily calendar is not contiguous; missing local_date value(s): {', '.join(missing_dates[:10])}")
    return out


def evaluation_test_size(n_dates: int) -> int:
    test_size = max(28, math.ceil(n_dates * 0.20))
    if n_dates <= test_size:
        raise ValueError(f"Need more completed dates than the evaluation size; got {n_dates} dates and test_size={test_size}")
    return test_size


def persistence(history: list[float]) -> float:
    return float(history[-1])


def seasonal_7(history: list[float]) -> float:
    return float(history[-7])


def trailing_mean_7(history: list[float]) -> float:
    return float(sum(history[-7:]) / 7)


def split_history_and_evaluation(series: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    test_size = evaluation_test_size(len(series))
    return series.iloc[:-test_size].copy(), series.iloc[-test_size:].copy()


def walk_forward_predictions(series: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    initial, evaluation = split_history_and_evaluation(series)
    if len(initial) < 7:
        raise ValueError("At least seven initial-history days are required for seasonal and trailing-seven baselines")
    history = initial[TARGET_COLUMN].astype(float).tolist()
    rows = []
    for row in evaluation.itertuples(index=False):
        actual = float(getattr(row, TARGET_COLUMN))
        rows.append(
            {
                "local_date": row.local_date,
                "actual": actual,
                MODEL_COLUMNS["persistence"]: persistence(history),
                MODEL_COLUMNS["seasonal_7"]: seasonal_7(history),
                MODEL_COLUMNS["trailing_mean_7"]: trailing_mean_7(history),
            }
        )
        history.append(actual)
    return pd.DataFrame(rows), len(initial)


def calculate_metrics(predictions: pd.DataFrame, initial_history_days: int) -> pd.DataFrame:
    rows = []
    actual = predictions["actual"].astype(float)
    for model, col in MODEL_COLUMNS.items():
        error = predictions[col].astype(float) - actual
        rows.append(
            {
                "model": model,
                "target": TARGET_COLUMN,
                "evaluation_start": predictions["local_date"].iloc[0],
                "evaluation_end": predictions["local_date"].iloc[-1],
                "initial_history_days": initial_history_days,
                "evaluation_days": len(predictions),
                "mae": error.abs().mean(),
                "rmse": math.sqrt((error**2).mean()),
                "mean_error": error.mean(),
            }
        )
    return pd.DataFrame(rows).sort_values(["mae", "rmse", "model"]).reset_index(drop=True)


def next_day_estimates(series: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    history = series[TARGET_COLUMN].astype(float).tolist()
    latest = series["local_date"].iloc[-1]
    forecast_date = latest + timedelta(days=1)
    estimates = {"persistence": persistence(history), "seasonal_7": seasonal_7(history), "trailing_mean_7": trailing_mean_7(history)}
    metric_lookup = metrics.set_index("model")
    return pd.DataFrame(
        [
            {
                "forecast_date": forecast_date,
                "latest_observed_date": latest,
                "model": model,
                "estimate": value,
                "historical_evaluation_mae": metric_lookup.loc[model, "mae"],
                "historical_evaluation_rmse": metric_lookup.loc[model, "rmse"],
            }
            for model, value in estimates.items()
        ]
    )


def run_baseline_evaluation(series: pd.DataFrame) -> BaselineResult:
    validated = validate_daily_series(series)
    predictions, initial_history_days = walk_forward_predictions(validated)
    metrics = calculate_metrics(predictions, initial_history_days)
    estimates = next_day_estimates(validated, metrics)
    return BaselineResult(metrics=metrics, predictions=predictions, next_day_estimates=estimates)
