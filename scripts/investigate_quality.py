"""Investigate duplicates, duration anomalies, and administrative granularity.

This script is intentionally diagnostic only. It does not modify the raw CSV and
it does not create a cleaned dataset.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_PATH = Path("data/raw/official_data_en.csv")
REPORT_DIR = Path("reports/data_quality")
FIELDS = ["oblast", "raion", "hromada", "level", "started_at", "finished_at", "source"]
THRESHOLDS_HOURS = {
    "gt_12_hours": 12,
    "gt_24_hours": 24,
    "gt_7_days": 24 * 7,
    "gt_30_days": 24 * 30,
    "gt_90_days": 24 * 90,
}


def pct(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def save_csv(df: pd.DataFrame, name: str) -> Path:
    path = REPORT_DIR / name
    df.to_csv(path, index=False)
    return path


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(f"Missing {DATA_PATH}. Run `python scripts/download_data.py` first.")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_PATH)
    missing = [field for field in FIELDS if field not in df.columns]
    if missing:
        raise SystemExit(f"Expected fields are missing from the real CSV: {missing}")

    rows_before = len(df)
    unique_rows = df.drop_duplicates()
    rows_after = len(unique_rows)
    fully_duplicate_rows = int(df.duplicated().sum())

    starts = pd.to_datetime(df["started_at"], errors="coerce", utc=True)
    ends = pd.to_datetime(df["finished_at"], errors="coerce", utc=True)
    df["start_ts"] = starts
    df["end_ts"] = ends
    df["year_month"] = starts.dt.strftime("%Y-%m")
    df["duration_hours"] = (ends - starts).dt.total_seconds() / 3600
    df["duration_days"] = df["duration_hours"] / 24

    group_counts = df.groupby(FIELDS, dropna=False).size().rename("multiplicity").reset_index()
    duplicate_groups = group_counts[group_counts["multiplicity"] > 1].copy()
    distinct_duplicate_groups = len(duplicate_groups)
    multiplicities = duplicate_groups["multiplicity"]

    multiplicity_summary = pd.DataFrame(
        [
            {"bucket": "appearing_twice", "groups": int((multiplicities == 2).sum())},
            {"bucket": "appearing_three_times", "groups": int((multiplicities == 3).sum())},
            {"bucket": "appearing_four_times", "groups": int((multiplicities == 4).sum())},
            {"bucket": "appearing_more_than_four_times", "groups": int((multiplicities > 4).sum())},
            {"bucket": "maximum_multiplicity", "groups": int(multiplicities.max() if not multiplicities.empty else 0)},
        ]
    )

    top_duplicate_groups = duplicate_groups.sort_values("multiplicity", ascending=False).head(20)

    duplicate_instance_mask = df.duplicated(keep=False)
    duplicate_excess_mask = df.duplicated(keep="first")

    def duplicate_rate_table(column: str) -> pd.DataFrame:
        table = (
            df.assign(
                duplicate_instances=duplicate_instance_mask.astype(int),
                duplicate_excess=duplicate_excess_mask.astype(int),
            )
            .groupby(column, dropna=False)
            .agg(
                records=(column, "size"),
                duplicate_instances=("duplicate_instances", "sum"),
                duplicate_excess=("duplicate_excess", "sum"),
            )
            .reset_index()
        )
        table["duplicate_instance_rate"] = table["duplicate_instances"] / table["records"]
        table["duplicate_excess_rate"] = table["duplicate_excess"] / table["records"]
        return table.sort_values("duplicate_excess_rate", ascending=False)

    duplicate_by_level = duplicate_rate_table("level")
    duplicate_by_oblast = duplicate_rate_table("oblast")
    duplicate_by_month = duplicate_rate_table("year_month")

    daily_counts = (
        pd.DataFrame({"date": starts.dt.date})
        .assign(before_exact_dedup=1)
        .groupby("date", dropna=False)["before_exact_dedup"]
        .sum()
        .reset_index()
    )
    daily_after = (
        pd.DataFrame({"date": pd.to_datetime(unique_rows["started_at"], utc=True).dt.date})
        .assign(after_exact_dedup=1)
        .groupby("date", dropna=False)["after_exact_dedup"]
        .sum()
        .reset_index()
    )
    daily_compare = daily_counts.merge(daily_after, on="date", how="outer").fillna(0)
    daily_compare["difference"] = daily_compare["before_exact_dedup"] - daily_compare["after_exact_dedup"]

    with_mult = df.merge(group_counts, on=FIELDS, how="left")
    top_longest = with_mult.sort_values("duration_hours", ascending=False).head(30)[
        [
            "oblast",
            "raion",
            "hromada",
            "level",
            "started_at",
            "finished_at",
            "duration_hours",
            "duration_days",
            "multiplicity",
        ]
    ]
    zero_duration = with_mult[with_mult["duration_hours"] == 0][
        [
            "oblast",
            "raion",
            "hromada",
            "level",
            "started_at",
            "finished_at",
            "duration_hours",
            "duration_days",
            "multiplicity",
        ]
    ]

    long_counts = []
    long_distribution_frames = []
    for label, hours in THRESHOLDS_HOURS.items():
        mask = with_mult["duration_hours"] > hours
        long_counts.append({"threshold": label, "records": int(mask.sum())})
        dist = (
            with_mult[mask]
            .groupby(["level", "oblast"], dropna=False)
            .size()
            .rename("records")
            .reset_index()
            .sort_values("records", ascending=False)
        )
        dist.insert(0, "threshold", label)
        long_distribution_frames.append(dist)
    long_duration_counts = pd.DataFrame(long_counts)
    long_duration_distribution = pd.concat(long_distribution_frames, ignore_index=True)

    monthly = (
        df.groupby(["year_month", "level"], dropna=False)
        .size()
        .rename("records")
        .reset_index()
        .pivot(index="year_month", columns="level", values="records")
        .fillna(0)
        .astype(int)
        .reset_index()
    )
    for col in ["oblast", "raion", "hromada"]:
        if col not in monthly.columns:
            monthly[col] = 0
    monthly = monthly[["year_month", "oblast", "raion", "hromada"]]
    monthly["total_records"] = monthly[["oblast", "raion", "hromada"]].sum(axis=1)
    for col in ["oblast", "raion", "hromada"]:
        monthly[f"{col}_share"] = monthly[col] / monthly["total_records"]
    monthly = monthly[
        [
            "year_month",
            "total_records",
            "oblast",
            "raion",
            "hromada",
            "oblast_share",
            "raion_share",
            "hromada_share",
        ]
    ]

    milestone_checks = [
        ("oblast_share_below_75", monthly["oblast_share"] < 0.75),
        ("oblast_share_below_50", monthly["oblast_share"] < 0.50),
        ("oblast_share_below_25", monthly["oblast_share"] < 0.25),
        ("oblast_share_below_10", monthly["oblast_share"] < 0.10),
        ("raion_share_above_50", monthly["raion_share"] > 0.50),
    ]
    milestones = []
    for label, mask in milestone_checks:
        matching = monthly[mask]
        milestones.append(
            {
                "milestone": label,
                "first_month": matching.iloc[0]["year_month"] if not matching.empty else "not observed",
            }
        )
    milestone_table = pd.DataFrame(milestones)

    candidate_cutoffs = []
    for cutoff in ["2025-07", "2025-08", "2025-09", "2025-11", "2025-12"]:
        before = monthly[monthly["year_month"] < cutoff]
        after = monthly[monthly["year_month"] >= cutoff]
        candidate_cutoffs.append(
            {
                "cutoff_month_exclusive_for_historical_period": cutoff,
                "months_before": len(before),
                "records_before": int(before["total_records"].sum()),
                "oblast_share_before": pct(before["oblast"].sum(), before["total_records"].sum()),
                "raion_share_before": pct(before["raion"].sum(), before["total_records"].sum()),
                "months_after": len(after),
                "records_after": int(after["total_records"].sum()),
                "oblast_share_after": pct(after["oblast"].sum(), after["total_records"].sum()),
                "raion_share_after": pct(after["raion"].sum(), after["total_records"].sum()),
            }
        )
    cutoff_table = pd.DataFrame(candidate_cutoffs)

    generated = [
        save_csv(multiplicity_summary, "duplicate_multiplicity_summary.csv"),
        save_csv(top_duplicate_groups, "top_20_duplicate_groups.csv"),
        save_csv(duplicate_by_level, "duplicates_by_level.csv"),
        save_csv(duplicate_by_oblast, "duplicates_by_oblast.csv"),
        save_csv(duplicate_by_month, "duplicates_by_month.csv"),
        save_csv(daily_compare, "daily_counts_before_after_exact_dedup.csv"),
        save_csv(top_longest, "top_30_longest_alerts.csv"),
        save_csv(zero_duration, "zero_duration_records.csv"),
        save_csv(long_duration_counts, "long_duration_counts.csv"),
        save_csv(long_duration_distribution, "long_duration_distribution_by_level_oblast.csv"),
        save_csv(monthly, "monthly_admin_level_shares.csv"),
        save_csv(milestone_table, "admin_granularity_milestones.csv"),
        save_csv(cutoff_table, "candidate_cutoff_comparison.csv"),
    ]

    summary_lines = [
        "# Data Quality Investigation Summary",
        "",
        f"Rows before exact deduplication: {rows_before}",
        f"Unique rows after exact deduplication: {rows_after}",
        f"Excess fully duplicated rows: {fully_duplicate_rows}",
        f"Distinct duplicate groups: {distinct_duplicate_groups}",
        "",
        "## Duplicate multiplicity summary",
        "```",
        multiplicity_summary.to_string(index=False),
        "```",
        "",
        "## Duration anomaly counts",
        "```",
        long_duration_counts.to_string(index=False),
        "```",
        "",
        "## Administrative granularity milestones",
        "```",
        milestone_table.to_string(index=False),
        "```",
        "",
        "## Candidate cutoff comparison",
        "```",
        cutoff_table.to_string(index=False),
        "```",
    ]
    summary_path = REPORT_DIR / "quality_investigation_summary.md"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    generated.append(summary_path)

    print("Data quality investigation complete")
    print(f"Input file: {DATA_PATH}")
    print(f"Rows before exact deduplication: {rows_before}")
    print(f"Unique rows after exact deduplication: {rows_after}")
    print(f"Excess fully duplicated rows: {fully_duplicate_rows}")
    print(f"Distinct duplicate groups: {distinct_duplicate_groups}")
    print("Duplicate multiplicity summary:")
    print(multiplicity_summary.to_string(index=False))
    print("Daily count difference before vs after exact deduplication:")
    print(f"- Total before: {int(daily_compare['before_exact_dedup'].sum())}")
    print(f"- Total after: {int(daily_compare['after_exact_dedup'].sum())}")
    print(f"- Total difference: {int(daily_compare['difference'].sum())}")
    print(f"- Median daily difference: {daily_compare['difference'].median():.2f}")
    print(f"- Maximum daily difference: {int(daily_compare['difference'].max())}")
    print("Long-duration counts:")
    print(long_duration_counts.to_string(index=False))
    print("Administrative granularity milestones:")
    print(milestone_table.to_string(index=False))
    print("Candidate cutoff comparison:")
    print(cutoff_table.to_string(index=False, formatters={
        "oblast_share_before": "{:.2%}".format,
        "raion_share_before": "{:.2%}".format,
        "oblast_share_after": "{:.2%}".format,
        "raion_share_after": "{:.2%}".format,
    }))
    print("Generated report files:")
    for path in generated:
        print(f"- {path}")


if __name__ == "__main__":
    main()
