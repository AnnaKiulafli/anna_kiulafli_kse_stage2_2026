from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from alert_pipeline.modeling import TARGET_COLUMN, TARGET_DESCRIPTION, load_daily_series, run_baseline_evaluation


def markdown_table(frame) -> str:
    text = frame.copy()
    for col in text.columns:
        text[col] = text[col].map(lambda value: f"{value:.3f}" if isinstance(value, float) else str(value))
    header = "| " + " | ".join(text.columns) + " |"
    divider = "| " + " | ".join(["---"] * len(text.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in text.astype(str).values.tolist()]
    return "\n".join([header, divider, *rows])


def write_summary(series, result, path: Path) -> None:
    actual = result.predictions["actual"]
    best = result.metrics.iloc[0]
    estimates = result.next_day_estimates
    lines = [
        "# Baseline modeling summary",
        "",
        f"Target: `{TARGET_COLUMN}` is defined as the number of {TARGET_DESCRIPTION}.",
        "It is not a count of attacks, military events, or independent nationwide alerts.",
        "",
        "National daily activity was selected instead of individual raion modeling because this phase establishes a simple reproducible baseline on one contiguous completed-day series before introducing sparse local models.",
        f"The date range is derived dynamically from the processed data: {series['local_date'].iloc[0]} through {series['local_date'].iloc[-1]}.",
        f"The chronological evaluation split uses the final {len(result.predictions)} completed dates, from {result.predictions['local_date'].iloc[0]} through {result.predictions['local_date'].iloc[-1]}, after {int(best['initial_history_days'])} initial-history days.",
        "Walk-forward validation forecasts each evaluation date using only observations strictly before that date; the actual is then revealed and appended before the next forecast.",
        "Persistence uses the immediately preceding actual, seasonal naive uses the actual from seven days earlier, and the trailing mean uses only the seven previous actual values.",
        "",
        "## Historical evaluation metrics",
        "",
        f"Evaluation actual mean: {actual.mean():.3f}; standard deviation: {actual.std(ddof=1):.3f}.",
        "",
        markdown_table(result.metrics),
        "",
        f"The lowest historical evaluation MAE is from `{best['model']}` (MAE={best['mae']:.3f}, RMSE={best['rmse']:.3f}).",
        "This historical ranking does not imply that the same baseline will remain best in the future.",
        "",
        "## One-step-ahead estimates",
        "",
        "One-step-ahead statistical baseline estimate of recorded raion alert activity, based only on historical alert-record counts.",
        "",
        markdown_table(estimates),
        "",
        "These results have limited predictive meaning: the baselines use only past recorded counts and do not include external military, operational, weather, political, or other causal variables.",
        "This is not an operational warning system and must not be interpreted as predicting attacks or safety conditions.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def plot_predictions(result, path: Path) -> None:
    plt.figure(figsize=(12, 6))
    x = result.predictions["local_date"]
    plt.plot(x, result.predictions["actual"], label="Actual", linewidth=2)
    plt.plot(x, result.predictions["persistence_prediction"], label="Persistence", alpha=0.8)
    plt.plot(x, result.predictions["seasonal_7_prediction"], label="Seasonal naive (7-day)", alpha=0.8)
    plt.plot(x, result.predictions["trailing_mean_7_prediction"], label="Trailing 7-day mean", alpha=0.8)
    plt.title("Walk-forward actual vs. baseline estimates")
    plt.xlabel("Local date")
    plt.ylabel(TARGET_COLUMN)
    plt.legend()
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150)
    plt.close()


def main() -> None:
    processed_path = ROOT / "data" / "processed" / "daily_2026_raion_activity.csv"
    out_dir = ROOT / "reports" / "modeling"
    out_dir.mkdir(parents=True, exist_ok=True)
    series = load_daily_series(processed_path)
    result = run_baseline_evaluation(series)
    result.metrics.to_csv(out_dir / "baseline_metrics.csv", index=False)
    result.predictions.to_csv(out_dir / "walk_forward_predictions.csv", index=False)
    result.next_day_estimates.to_csv(out_dir / "next_day_baseline_estimates.csv", index=False)
    write_summary(series, result, out_dir / "modeling_summary.md")
    plot_predictions(result, out_dir / "figures" / "walk_forward_actual_vs_baselines.png")
    print(f"date_range={series['local_date'].iloc[0]}..{series['local_date'].iloc[-1]}")
    print(f"evaluation={result.predictions['local_date'].iloc[0]}..{result.predictions['local_date'].iloc[-1]} ({len(result.predictions)} days)")
    print(result.metrics.to_string(index=False))
    print(result.next_day_estimates.to_string(index=False))


if __name__ == "__main__":
    main()
