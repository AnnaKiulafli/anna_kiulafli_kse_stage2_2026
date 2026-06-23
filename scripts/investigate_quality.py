"""Investigate deduplicated data quality, 2026 coverage, and granularity.

This script is diagnostic only. It does not modify the raw CSV and does not
create the final cleaned analysis dataset.
"""
from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

DATA_PATH = Path("data/raw/official_data_en.csv")
REPORT_DIR = Path("reports/data_quality")
FIELDS = ["oblast", "raion", "hromada", "level", "started_at", "finished_at", "source"]
KYIV_TZ = ZoneInfo("Europe/Kyiv")
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


def duplicate_rate_table(df: pd.DataFrame, duplicate_instance_mask: pd.Series, duplicate_excess_mask: pd.Series, column: str) -> pd.DataFrame:
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


def add_time_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["start_utc"] = pd.to_datetime(result["started_at"], errors="coerce", utc=True)
    result["end_utc"] = pd.to_datetime(result["finished_at"], errors="coerce", utc=True)
    result["start_kyiv"] = result["start_utc"].dt.tz_convert(KYIV_TZ)
    result["end_kyiv"] = result["end_utc"].dt.tz_convert(KYIV_TZ)
    result["year_month_kyiv"] = result["start_kyiv"].dt.strftime("%Y-%m")
    result["date_kyiv"] = result["start_kyiv"].dt.date
    result["duration_hours"] = (result["end_utc"] - result["start_utc"]).dt.total_seconds() / 3600
    result["duration_days"] = result["duration_hours"] / 24
    return result


def interval_overlap_summary(raion_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (oblast, raion), group in raion_df.dropna(subset=["raion"]).groupby(["oblast", "raion"], dropna=False):
        ordered = group.sort_values(["start_utc", "end_utc"])
        previous_end = None
        overlap_count = 0
        for row in ordered.itertuples(index=False):
            start = row.start_utc
            end = row.end_utc
            if previous_end is not None and start < previous_end:
                overlap_count += 1
                if end > previous_end:
                    previous_end = end
            else:
                previous_end = end
        rows.append(
            {
                "oblast": oblast,
                "raion": raion,
                "records": len(ordered),
                "records_starting_during_previous_interval": overlap_count,
                "overlap_start_rate": pct(overlap_count, len(ordered)),
            }
        )
    return pd.DataFrame(rows).sort_values("overlap_start_rate", ascending=False)


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(f"Missing {DATA_PATH}. Run `python scripts/download_data.py` first.")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(DATA_PATH)
    missing = [field for field in FIELDS if field not in raw.columns]
    if missing:
        raise SystemExit(f"Expected fields are missing from the real CSV: {missing}")

    duplicate_instance_mask = raw.duplicated(keep=False)
    duplicate_excess_mask = raw.duplicated(keep="first")
    raw_group_counts = raw.groupby(FIELDS, dropna=False).size().rename("multiplicity").reset_index()
    raw_duplicate_groups = raw_group_counts[raw_group_counts["multiplicity"] > 1].copy()

    dedup = raw.drop_duplicates().reset_index(drop=True)
    dedup = add_time_columns(dedup)
    dedup_group_counts = dedup.groupby(FIELDS, dropna=False).size().rename("multiplicity").reset_index()
    dedup_with_mult = dedup.merge(dedup_group_counts, on=FIELDS, how="left")

    duplicate_multiplicity_summary = pd.DataFrame(
        [
            {"bucket": "appearing_twice", "groups": int((raw_duplicate_groups["multiplicity"] == 2).sum())},
            {"bucket": "appearing_three_times", "groups": int((raw_duplicate_groups["multiplicity"] == 3).sum())},
            {"bucket": "appearing_four_times", "groups": int((raw_duplicate_groups["multiplicity"] == 4).sum())},
            {"bucket": "appearing_more_than_four_times", "groups": int((raw_duplicate_groups["multiplicity"] > 4).sum())},
            {"bucket": "maximum_multiplicity", "groups": int(raw_duplicate_groups["multiplicity"].max() if not raw_duplicate_groups.empty else 0)},
        ]
    )

    duplicate_by_level = duplicate_rate_table(raw, duplicate_instance_mask, duplicate_excess_mask, "level")
    duplicate_by_oblast = duplicate_rate_table(raw, duplicate_instance_mask, duplicate_excess_mask, "oblast")
    raw_for_month = add_time_columns(raw)
    duplicate_by_month = duplicate_rate_table(raw_for_month, duplicate_instance_mask, duplicate_excess_mask, "year_month_kyiv")

    daily_before = raw_for_month.groupby("date_kyiv").size().rename("before_exact_dedup").reset_index()
    daily_after = dedup.groupby("date_kyiv").size().rename("after_exact_dedup").reset_index()
    daily_compare = daily_before.merge(daily_after, on="date_kyiv", how="outer").fillna(0)
    daily_compare["difference"] = daily_compare["before_exact_dedup"] - daily_compare["after_exact_dedup"]

    top_longest = dedup_with_mult.sort_values("duration_hours", ascending=False).head(30)[
        ["oblast", "raion", "hromada", "level", "started_at", "finished_at", "duration_hours", "duration_days", "multiplicity"]
    ]
    zero_duration = dedup_with_mult[dedup_with_mult["duration_hours"] == 0][
        ["oblast", "raion", "hromada", "level", "started_at", "finished_at", "duration_hours", "duration_days", "multiplicity"]
    ]

    long_counts = []
    long_distribution_frames = []
    for label, hours in THRESHOLDS_HOURS.items():
        mask = dedup_with_mult["duration_hours"] > hours
        long_counts.append({"threshold": label, "deduplicated_records": int(mask.sum())})
        dist = (
            dedup_with_mult[mask]
            .groupby(["level", "oblast"], dropna=False)
            .size()
            .rename("deduplicated_records")
            .reset_index()
            .sort_values("deduplicated_records", ascending=False)
        )
        dist.insert(0, "threshold", label)
        long_distribution_frames.append(dist)
    long_duration_counts = pd.DataFrame(long_counts)
    long_duration_distribution = pd.concat(long_distribution_frames, ignore_index=True)

    monthly = (
        dedup.groupby(["year_month_kyiv", "level"], dropna=False)
        .size()
        .rename("records")
        .reset_index()
        .pivot(index="year_month_kyiv", columns="level", values="records")
        .fillna(0)
        .astype(int)
        .reset_index()
    )
    for col in ["oblast", "raion", "hromada"]:
        if col not in monthly.columns:
            monthly[col] = 0
    monthly = monthly[["year_month_kyiv", "oblast", "raion", "hromada"]]
    monthly["total_records"] = monthly[["oblast", "raion", "hromada"]].sum(axis=1)
    for col in ["oblast", "raion", "hromada"]:
        monthly[f"{col}_share"] = monthly[col] / monthly["total_records"]
    monthly = monthly[
        ["year_month_kyiv", "total_records", "oblast", "raion", "hromada", "oblast_share", "raion_share", "hromada_share"]
    ]

    milestone_checks = [
        ("oblast_share_below_75", monthly["oblast_share"] < 0.75),
        ("oblast_share_below_50", monthly["oblast_share"] < 0.50),
        ("oblast_share_below_25", monthly["oblast_share"] < 0.25),
        ("oblast_share_below_10", monthly["oblast_share"] < 0.10),
        ("raion_share_above_50", monthly["raion_share"] > 0.50),
        ("raion_share_above_75", monthly["raion_share"] > 0.75),
        ("raion_share_above_90", monthly["raion_share"] > 0.90),
    ]
    milestones = []
    for label, mask in milestone_checks:
        matching = monthly[mask]
        milestones.append({"milestone": label, "first_month": matching.iloc[0]["year_month_kyiv"] if not matching.empty else "not observed"})
    milestone_table = pd.DataFrame(milestones)

    candidate_cutoffs = []
    for cutoff in ["2025-07", "2025-08", "2025-09", "2025-11", "2025-12"]:
        before = monthly[monthly["year_month_kyiv"] < cutoff]
        after = monthly[monthly["year_month_kyiv"] >= cutoff]
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

    current_2026 = dedup[(dedup["start_kyiv"] >= pd.Timestamp("2026-01-01", tz=KYIV_TZ))].copy()
    coverage_2026_month_level = (
        current_2026.groupby(["year_month_kyiv", "level"], dropna=False)
        .size()
        .rename("records")
        .reset_index()
        .pivot(index="year_month_kyiv", columns="level", values="records")
        .fillna(0)
        .astype(int)
        .reset_index()
    )
    for col in ["oblast", "raion", "hromada"]:
        if col not in coverage_2026_month_level.columns:
            coverage_2026_month_level[col] = 0
    coverage_2026_month_level = coverage_2026_month_level[["year_month_kyiv", "oblast", "raion", "hromada"]]
    coverage_2026_month_level["total_records"] = coverage_2026_month_level[["oblast", "raion", "hromada"]].sum(axis=1)
    for col in ["oblast", "raion", "hromada"]:
        coverage_2026_month_level[f"{col}_share"] = coverage_2026_month_level[col] / coverage_2026_month_level["total_records"]
    coverage_2026_month_level = coverage_2026_month_level[
        ["year_month_kyiv", "total_records", "oblast", "raion", "hromada", "oblast_share", "raion_share", "hromada_share"]
    ]

    raion_2026 = current_2026[current_2026["level"] == "raion"].copy()
    raion_coverage_by_month = (
        raion_2026.groupby("year_month_kyiv")
        .agg(
            raion_records=("level", "size"),
            unique_oblasts=("oblast", "nunique"),
            unique_raions=("raion", "nunique"),
            first_start_kyiv=("start_kyiv", "min"),
            last_start_kyiv=("start_kyiv", "max"),
        )
        .reset_index()
    )

    raion_month_presence = (
        raion_2026.groupby(["oblast", "raion"], dropna=False)["year_month_kyiv"]
        .nunique()
        .rename("months_present")
        .reset_index()
    )
    total_2026_months = current_2026["year_month_kyiv"].nunique()
    raion_month_presence["total_2026_months"] = total_2026_months
    raion_month_presence["present_all_2026_months"] = raion_month_presence["months_present"] == total_2026_months

    oblast_raion_coverage_2026 = (
        raion_2026.groupby("oblast", dropna=False)
        .agg(
            raion_records=("level", "size"),
            unique_raions=("raion", "nunique"),
            first_start_kyiv=("start_kyiv", "min"),
            last_start_kyiv=("start_kyiv", "max"),
        )
        .reset_index()
        .sort_values("unique_raions", ascending=False)
    )

    month_oblast_raion_counts = (
        raion_2026.groupby(["year_month_kyiv", "oblast"], dropna=False)
        .agg(raion_records=("level", "size"), unique_raions=("raion", "nunique"))
        .reset_index()
        .sort_values(["year_month_kyiv", "oblast"])
    )

    covered_raions_by_month = (
        raion_2026.groupby("year_month_kyiv")["raion"]
        .apply(lambda s: " | ".join(sorted(s.dropna().unique())))
        .rename("covered_raions")
        .reset_index()
    )

    mixed_2026_records = current_2026[current_2026["level"] != "raion"].copy()
    mixed_2026_by_month_level_oblast = (
        mixed_2026_records.groupby(["year_month_kyiv", "level", "oblast"], dropna=False)
        .size()
        .rename("records")
        .reset_index()
        .sort_values(["year_month_kyiv", "level", "oblast"])
    )

    raion_overlap = interval_overlap_summary(raion_2026)

    generated = [
        save_csv(duplicate_multiplicity_summary, "duplicate_multiplicity_summary.csv"),
        save_csv(raw_duplicate_groups.sort_values("multiplicity", ascending=False).head(20), "top_20_duplicate_groups.csv"),
        save_csv(duplicate_by_level, "duplicates_by_level.csv"),
        save_csv(duplicate_by_oblast, "duplicates_by_oblast.csv"),
        save_csv(duplicate_by_month, "duplicates_by_month.csv"),
        save_csv(daily_compare, "daily_counts_before_after_exact_dedup.csv"),
        save_csv(top_longest, "deduplicated_top_30_longest_alerts.csv"),
        save_csv(zero_duration, "deduplicated_zero_duration_records.csv"),
        save_csv(long_duration_counts, "deduplicated_long_duration_counts.csv"),
        save_csv(long_duration_distribution, "deduplicated_long_duration_distribution_by_level_oblast.csv"),
        save_csv(monthly, "deduplicated_monthly_admin_level_shares.csv"),
        save_csv(milestone_table, "deduplicated_admin_granularity_milestones.csv"),
        save_csv(cutoff_table, "deduplicated_candidate_cutoff_comparison.csv"),
        save_csv(coverage_2026_month_level, "coverage_2026_month_level.csv"),
        save_csv(raion_coverage_by_month, "coverage_2026_raion_by_month.csv"),
        save_csv(raion_month_presence, "coverage_2026_raion_month_presence.csv"),
        save_csv(oblast_raion_coverage_2026, "coverage_2026_oblast_raion_counts.csv"),
        save_csv(month_oblast_raion_counts, "coverage_2026_month_oblast_raion_counts.csv"),
        save_csv(covered_raions_by_month, "coverage_2026_covered_raions_by_month.csv"),
        save_csv(mixed_2026_by_month_level_oblast, "coverage_2026_mixed_non_raion_records.csv"),
        save_csv(raion_overlap, "coverage_2026_raion_interval_overlaps.csv"),
    ]

    summary_lines = [
        "# Deduplicated Data Quality and 2026 Coverage Summary",
        "",
        f"Raw rows before exact deduplication: {len(raw)}",
        f"Rows after exact full-row deduplication: {len(dedup)}",
        f"Excess fully duplicated rows removed analytically: {int(raw.duplicated().sum())}",
        f"Distinct duplicate groups in raw data: {len(raw_duplicate_groups)}",
        "",
        "## Deduplicated duration anomaly counts",
        "```",
        long_duration_counts.to_string(index=False),
        "```",
        "",
        "## Deduplicated administrative granularity milestones",
        "```",
        milestone_table.to_string(index=False),
        "```",
        "",
        "## 2026 administrative-level coverage by month",
        "```",
        coverage_2026_month_level.to_string(index=False),
        "```",
        "",
        "## 2026 raion coverage by month",
        "```",
        raion_coverage_by_month.to_string(index=False),
        "```",
        "",
        "## Candidate historical cutoff comparison after deduplication",
        "```",
        cutoff_table.to_string(index=False),
        "```",
    ]
    summary_path = REPORT_DIR / "deduplicated_quality_and_2026_coverage_summary.md"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    generated.append(summary_path)

    print("Deduplicated data quality and 2026 coverage investigation complete")
    print(f"Input file: {DATA_PATH}")
    print(f"Raw rows before exact deduplication: {len(raw)}")
    print(f"Rows after exact full-row deduplication: {len(dedup)}")
    print(f"Excess fully duplicated rows removed analytically: {int(raw.duplicated().sum())}")
    print(f"Distinct duplicate groups in raw data: {len(raw_duplicate_groups)}")
    print("Deduplicated long-duration counts:")
    print(long_duration_counts.to_string(index=False))
    print("Deduplicated administrative granularity milestones:")
    print(milestone_table.to_string(index=False))
    print("2026 administrative-level coverage by month:")
    print(coverage_2026_month_level.to_string(index=False, formatters={
        "oblast_share": "{:.2%}".format,
        "raion_share": "{:.2%}".format,
        "hromada_share": "{:.2%}".format,
    }))
    print("2026 raion coverage by month:")
    print(raion_coverage_by_month.to_string(index=False))
    print("2026 raion month-presence summary:")
    print(raion_month_presence["months_present"].value_counts().sort_index().to_string())
    print("2026 non-raion record count:")
    print(len(mixed_2026_records))
    print("2026 raion interval overlap summary:")
    print(f"- Raions checked: {len(raion_overlap)}")
    print(f"- Raions with at least one overlapping start: {int((raion_overlap['records_starting_during_previous_interval'] > 0).sum())}")
    print(f"- Total records starting during previous interval: {int(raion_overlap['records_starting_during_previous_interval'].sum())}")
    print("Generated report files:")
    for path in generated:
        print(f"- {path}")


if __name__ == "__main__":
    main()
