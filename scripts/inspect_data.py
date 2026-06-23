"""Inspect the downloaded official Ukrainian air raid sirens dataset."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

DATA_PATH = Path("data/raw/official_data_en.csv")
SAMPLE_ROWS = 5


def find_column(columns: list[str], patterns: list[str]) -> str | None:
    lowered = {column.lower(): column for column in columns}
    for pattern in patterns:
        regex = re.compile(pattern, flags=re.IGNORECASE)
        for lower, original in lowered.items():
            if regex.search(lower):
                return original
    return None


def format_pct(count: int, total: int) -> str:
    return f"{(count / total * 100):.2f}%" if total else "0.00%"


def parse_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True)


def print_value_counts(df: pd.DataFrame, column: str | None, label: str) -> None:
    if column is None:
        print(f"\n{label}: column not detected")
        return
    print(f"\n{label} ({column}) unique values and counts:")
    print(df[column].value_counts(dropna=False).to_string())


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(
            f"Dataset not found at {DATA_PATH}. Run `python scripts/download_data.py` first."
        )

    print(f"Dataset path: {DATA_PATH}")
    print(f"File size: {DATA_PATH.stat().st_size} bytes")

    df = pd.read_csv(DATA_PATH)
    rows, cols = df.shape
    print(f"Rows: {rows}")
    print(f"Columns: {cols}")
    print("\nExact column names:")
    for column in df.columns:
        print(f"- {column}")

    print("\nPandas dtypes before conversion:")
    print(df.dtypes.to_string())

    print(f"\nFirst {SAMPLE_ROWS} sample rows:")
    print(df.head(SAMPLE_ROWS).to_string(index=False))

    print("\nMissing values by column:")
    for column in df.columns:
        count = int(df[column].isna().sum())
        print(f"- {column}: {count} ({format_pct(count, rows)})")

    duplicated_rows = int(df.duplicated().sum())
    print(f"\nFully duplicated rows: {duplicated_rows}")

    columns = list(df.columns)
    id_col = find_column(columns, [r"^id$", r"alert.*id", r"uuid"])
    level_col = find_column(columns, [r"level", r"admin"])
    alert_type_col = find_column(columns, [r"alert.*type", r"event.*type", r"type"])
    source_col = find_column(columns, [r"source"])
    start_col = find_column(columns, [r"started?_?at", r"start", r"begin"])
    end_col = find_column(columns, [r"finished?_?at", r"end", r"stop"])
    oblast_col = find_column(columns, [r"oblast", r"region"])
    raion_col = find_column(columns, [r"raion", r"district"])
    hromada_col = find_column(columns, [r"hromada", r"community"])

    print("\nDetected schema roles:")
    for label, column in [
        ("ID", id_col),
        ("Administrative level", level_col),
        ("Alert type", alert_type_col),
        ("Source", source_col),
        ("Start timestamp", start_col),
        ("End timestamp", end_col),
        ("Oblast/region", oblast_col),
        ("Raion/district", raion_col),
        ("Hromada/community", hromada_col),
    ]:
        print(f"- {label}: {column or 'not detected'}")

    if id_col is not None:
        duplicate_ids = int(df[id_col].duplicated().sum())
        print(f"\nDuplicate IDs in {id_col}: {duplicate_ids}")
    else:
        print("\nDuplicate IDs: no ID column detected")

    print_value_counts(df, level_col, "Administrative level")
    print_value_counts(df, alert_type_col, "Alert type")
    print_value_counts(df, source_col, "Source")

    for label, column in [
        ("oblasts/regions", oblast_col),
        ("raions/districts", raion_col),
        ("hromadas/communities", hromada_col),
    ]:
        if column is None:
            print(f"\nUnique {label}: column not detected")
        else:
            print(f"\nUnique {label} ({column}): {df[column].nunique(dropna=True)}")

    if start_col is None or end_col is None:
        print("\nTimestamp inspection skipped: start or end timestamp column not detected")
        return

    print("\nTimestamp raw examples:")
    print(df[[start_col, end_col]].head(SAMPLE_ROWS).to_string(index=False))
    offset_regex = re.compile(r"(?:Z$|[+-]\d{2}:?\d{2}$)")
    for label, column in [("start", start_col), ("end", end_col)]:
        non_null = df[column].dropna().astype(str)
        offset_count = int(non_null.str.contains(offset_regex).sum())
        print(
            f"Timezone offsets in raw {label} timestamps: "
            f"{offset_count}/{len(non_null)} ({format_pct(offset_count, len(non_null))})"
        )

    starts = parse_datetime(df[start_col])
    ends = parse_datetime(df[end_col])
    print(f"\nMinimum start timestamp: {starts.min()}")
    print(f"Maximum start timestamp: {starts.max()}")
    print(f"Minimum end timestamp: {ends.min()}")
    print(f"Maximum end timestamp: {ends.max()}")
    print(f"Records with missing/unparseable start timestamps: {int(starts.isna().sum())}")
    print(f"Records with missing/unparseable end timestamps: {int(ends.isna().sum())}")

    valid_both = starts.notna() & ends.notna()
    durations = ends[valid_both] - starts[valid_both]
    negative = int((durations < pd.Timedelta(0)).sum())
    zero = int((durations == pd.Timedelta(0)).sum())
    print(f"Records where end timestamp is earlier than start timestamp: {negative}")
    print(f"Zero-duration alerts: {zero}")

    valid_completed = durations[durations >= pd.Timedelta(0)].dt.total_seconds() / 60
    print("\nDuration statistics for valid completed alerts (minutes):")
    if valid_completed.empty:
        print("No valid completed alerts available for duration statistics.")
    else:
        print(f"- minimum: {valid_completed.min():.2f}")
        print(f"- median: {valid_completed.median():.2f}")
        print(f"- mean: {valid_completed.mean():.2f}")
        print(f"- 95th percentile: {valid_completed.quantile(0.95):.2f}")
        print(f"- maximum: {valid_completed.max():.2f}")

    if level_col is not None:
        print("\nRecords by administrative level:")
        level_counts = df[level_col].value_counts(dropna=False)
        for level, count in level_counts.items():
            print(f"- {level}: {count} ({format_pct(int(count), rows)})")

        monthly = (
            pd.DataFrame({"month": starts.dt.strftime("%Y-%m"), "level": df[level_col]})
            .dropna(subset=["month"])
            .groupby(["month", "level"], dropna=False)
            .size()
            .rename("records")
            .reset_index()
        )
        monthly["month_total"] = monthly.groupby("month")["records"].transform("sum")
        monthly["share"] = monthly["records"] / monthly["month_total"]
        print("\nAdministrative level by month (records and share):")
        print(monthly.to_string(index=False, formatters={"share": "{:.2%}".format}))

        daily_all = starts.dt.date.value_counts().sort_index().rename("all_levels")
        oblast_mask = df[level_col].astype(str).str.lower().eq("oblast")
        daily_oblast = starts[oblast_mask].dt.date.value_counts().sort_index().rename("oblast_only")
        daily_compare = pd.concat([daily_all, daily_oblast], axis=1).fillna(0).astype(int)
        daily_compare["difference"] = daily_compare["all_levels"] - daily_compare["oblast_only"]
        print("\nDaily alert count difference: all levels vs oblast-only")
        print(f"- Days compared: {len(daily_compare)}")
        print(f"- Total all-level records: {int(daily_compare['all_levels'].sum())}")
        print(f"- Total oblast-only records: {int(daily_compare['oblast_only'].sum())}")
        print(f"- Total difference: {int(daily_compare['difference'].sum())}")
        print(f"- Median daily difference: {daily_compare['difference'].median():.2f}")
        print(f"- Mean daily difference: {daily_compare['difference'].mean():.2f}")
        print(f"- Maximum daily difference: {int(daily_compare['difference'].max())}")
        print("\nLargest daily differences:")
        print(daily_compare.sort_values("difference", ascending=False).head(10).to_string())


if __name__ == "__main__":
    main()
