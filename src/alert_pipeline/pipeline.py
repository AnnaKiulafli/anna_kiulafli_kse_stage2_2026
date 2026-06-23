from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

KYIV_TZ = ZoneInfo("Europe/Kyiv")
CURRENT_START_DATE = date(2026, 1, 1)
HISTORICAL_OBLAST_END_DATE = date(2025, 7, 31)
KYIV_CITY_OBLAST = "Kyiv City"
DEDUP_FIELDS = ["oblast", "raion", "hromada", "level", "started_at", "finished_at", "source"]
OUTPUT_COLUMNS = [
    "oblast", "raion", "hromada", "level", "source", "started_at", "finished_at",
    "start_local", "end_local", "local_date", "duration_minutes",
]

@dataclass(frozen=True)
class BuildSummary:
    latest_complete_day: date | None
    current_complete_rows: int
    partial_day_rows: int
    daily_rows: int
    kyiv_city_complete_rows: int
    kyiv_city_partial_rows: int
    historical_oblast_rows: int
    audit: dict[str, object]


def latest_completed_day(current_local_date: date, latest_local_date_in_dataset: date) -> date:
    return min(current_local_date - timedelta(days=1), latest_local_date_in_dataset)


def _ensure_source_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename_to_source = {
        "region_title": "oblast", "region": "oblast", "oblast_title": "oblast",
        "raion_title": "raion", "community_title": "hromada", "hromada_title": "hromada",
        "start": "started_at", "end": "finished_at", "ended_at": "finished_at",
    }
    df = df.rename(columns={c: rename_to_source[c] for c in df.columns if c in rename_to_source})
    for col in DEDUP_FIELDS:
        if col not in df.columns:
            df[col] = pd.NA
    if "started_at" not in df.columns:
        raise ValueError("Input must contain started_at/start")
    return df


def exact_deduplicate_source(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicates on the original seven source fields before analytics."""
    return _ensure_source_columns(df).drop_duplicates(subset=DEDUP_FIELDS, keep="first").copy()


def normalize_alerts(df: pd.DataFrame, *, deduplicate: bool = True) -> pd.DataFrame:
    df = exact_deduplicate_source(df) if deduplicate else _ensure_source_columns(df)
    df["started_at"] = pd.to_datetime(df["started_at"], utc=True, errors="coerce")
    df["finished_at"] = pd.to_datetime(df["finished_at"], utc=True, errors="coerce")
    df = df[df["started_at"].notna()].copy()
    df["start_local"] = df["started_at"].dt.tz_convert(KYIV_TZ)
    df["end_local"] = df["finished_at"].dt.tz_convert(KYIV_TZ)
    df["local_date"] = df["start_local"].dt.date
    df["start_local_date"] = df["local_date"]  # backwards-compatible alias for tests/users
    df["duration_minutes"] = (df["finished_at"] - df["started_at"]).dt.total_seconds() / 60
    df["region"] = df["oblast"]  # normalized convenience column, not used for deduplication
    return df


def read_alerts(path: Path) -> pd.DataFrame:
    return normalize_alerts(pd.read_csv(path))


def is_raion_record(df: pd.DataFrame) -> pd.Series:
    return df["level"].eq("raion")


def current_raion_records(df: pd.DataFrame, current_local_date: date | None = None) -> tuple[pd.DataFrame, pd.DataFrame, date | None]:
    current_local_date = current_local_date or datetime.now(KYIV_TZ).date()
    raion = df[is_raion_record(df) & (df["local_date"] >= CURRENT_START_DATE)].copy()
    if raion.empty:
        return raion, raion, None
    latest = latest_completed_day(current_local_date, max(raion["local_date"]))
    complete = raion[raion["local_date"] <= latest].copy()
    partial = raion[raion["local_date"] == current_local_date].copy()
    return complete, partial, latest


def kyiv_city_records(df: pd.DataFrame, latest_complete_day_: date | None, current_local_date: date | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    current_local_date = current_local_date or datetime.now(KYIV_TZ).date()
    kyiv_2026 = df[df["oblast"].eq(KYIV_CITY_OBLAST) & (df["local_date"] >= CURRENT_START_DATE)].copy()
    complete = kyiv_2026.iloc[0:0].copy() if latest_complete_day_ is None else kyiv_2026[kyiv_2026["local_date"] <= latest_complete_day_].copy()
    partial = kyiv_2026[kyiv_2026["local_date"] == current_local_date].copy()
    return complete, partial


def split_kyiv_city(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = df["oblast"].eq(KYIV_CITY_OBLAST)
    return df[mask].copy(), df[~mask].copy()


def historical_oblast_context(df: pd.DataFrame) -> pd.DataFrame:
    hist = df[df["level"].eq("oblast") & (df["local_date"] <= HISTORICAL_OBLAST_END_DATE)].copy()
    assert hist.duplicated(subset=DEDUP_FIELDS).sum() == 0
    return hist


def _split_interval(row) -> list[tuple[date, pd.Timestamp, pd.Timestamp]]:
    start = row.start_local
    end = row.end_local
    if pd.isna(end) or end <= start or (end - start) > pd.Timedelta(days=7):
        return []
    pieces = []
    cur = start
    while cur < end:
        stop = min(end, pd.Timestamp(cur.date() + timedelta(days=1), tz=KYIV_TZ))
        pieces.append((cur.date(), cur, stop))
        cur = stop
    return pieces


def daily_raion_activity(complete: pd.DataFrame) -> pd.DataFrame:
    valid = complete[is_raion_record(complete) & complete["finished_at"].notna() & (complete["duration_minutes"] > 0) & (complete["duration_minutes"] <= 7 * 24 * 60)].copy()
    rows = []
    for row in valid.itertuples(index=False):
        for d, s, e in _split_interval(row):
            rows.append({"raion": row.raion, "local_date": d, "start": s, "end": e})
    if not rows:
        return pd.DataFrame(columns=["local_date", "active_raions", "alert_records", "total_raion_time_under_alert_minutes"])
    parts = pd.DataFrame(rows)
    totals = []
    for (day, raion), g in parts.sort_values("start").groupby(["local_date", "raion"]):
        merged = []
        for r in g.itertuples(index=False):
            if not merged or r.start > merged[-1][1]:
                merged.append([r.start, r.end])
            elif r.end > merged[-1][1]:
                merged[-1][1] = r.end
        totals.append({"local_date": day, "raion": raion, "minutes": sum((e - s).total_seconds() / 60 for s, e in merged), "records": len(g)})
    return pd.DataFrame(totals).groupby("local_date", as_index=False).agg(
        active_raions=("raion", "nunique"), alert_records=("records", "sum"), total_raion_time_under_alert_minutes=("minutes", "sum")
    ).sort_values("local_date")


def validate_invariants(complete: pd.DataFrame, partial: pd.DataFrame, historical: pd.DataFrame, latest: date | None, current_local_date: date) -> dict[str, int]:
    checks = {
        "complete_non_raion": int((~complete["level"].eq("raion")).sum()),
        "complete_before_2026": int((complete["local_date"] < CURRENT_START_DATE).sum()),
        "complete_after_latest": int(0 if latest is None else (complete["local_date"] > latest).sum()),
        "complete_current_partial": int((complete["local_date"] == current_local_date).sum()),
        "complete_exact_duplicates": int(complete.duplicated(subset=DEDUP_FIELDS).sum()),
        "partial_not_current_day": int((partial["local_date"] != current_local_date).sum()),
        "historical_exact_duplicates": int(historical.duplicated(subset=DEDUP_FIELDS).sum()),
    }
    bad = {k: v for k, v in checks.items() if v}
    if bad:
        raise AssertionError(f"Invariant violations: {bad}")
    return checks


def audit_counts(raw: pd.DataFrame, dedup: pd.DataFrame) -> dict[str, int]:
    norm_raw = normalize_alerts(raw, deduplicate=False)
    rows_2026 = dedup[dedup["local_date"] >= CURRENT_START_DATE]
    hist_raw = norm_raw[norm_raw["level"].eq("oblast") & (norm_raw["local_date"] <= HISTORICAL_OBLAST_END_DATE)]
    hist_dedup = dedup[dedup["level"].eq("oblast") & (dedup["local_date"] <= HISTORICAL_OBLAST_END_DATE)]
    current_date = datetime.now(KYIV_TZ).date()
    complete, partial, latest = current_raion_records(dedup, current_date)
    return {
        "raw rows": len(raw), "exact-deduplicated rows": len(dedup), "2026 rows": len(rows_2026),
        "2026 raion rows": int((rows_2026["level"].eq("raion")).sum()),
        "2026 raion completed-day rows": len(complete), "2026 raion partial-day rows": len(partial),
        "2026 non-raion rows": int((~rows_2026["level"].eq("raion")).sum()),
        "2026 exact Kyiv City rows": int((rows_2026["oblast"].eq(KYIV_CITY_OBLAST)).sum()),
        "historical oblast rows before deduplication": len(hist_raw),
        "historical oblast rows after exact deduplication": len(hist_dedup),
        "historical oblast rows through 2025-07-31": len(hist_dedup),
    }


def build_datasets(raw_path: Path, processed_dir: Path, current_local_date: date | None = None) -> BuildSummary:
    processed_dir.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(raw_path)
    df = normalize_alerts(raw, deduplicate=True)
    current_local_date = current_local_date or datetime.now(KYIV_TZ).date()
    complete, partial, latest = current_raion_records(df, current_local_date)
    kyiv_complete, kyiv_partial = kyiv_city_records(df, latest, current_local_date)
    historical = historical_oblast_context(df)
    daily = daily_raion_activity(complete)
    checks = validate_invariants(complete, partial, historical, latest, current_local_date)
    complete[OUTPUT_COLUMNS].to_csv(processed_dir / "current_2026_raion_alerts_complete_days.csv", index=False)
    partial[OUTPUT_COLUMNS].to_csv(processed_dir / "current_partial_day_raion_alerts.csv", index=False)
    kyiv_complete[OUTPUT_COLUMNS].to_csv(processed_dir / "current_2026_kyiv_city_complete_days.csv", index=False)
    kyiv_partial[OUTPUT_COLUMNS].to_csv(processed_dir / "current_partial_day_kyiv_city.csv", index=False)
    historical[OUTPUT_COLUMNS].to_csv(processed_dir / "historical_oblast_context.csv", index=False)
    daily.to_csv(processed_dir / "daily_2026_raion_activity.csv", index=False)
    return BuildSummary(latest, len(complete), len(partial), len(daily), len(kyiv_complete), len(kyiv_partial), len(historical), {"counts": audit_counts(raw, df), "invariants": checks})
