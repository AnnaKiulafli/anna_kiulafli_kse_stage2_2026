from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

KYIV_TZ = ZoneInfo("Europe/Kyiv")
CURRENT_START_DATE = date(2026, 1, 1)
HISTORICAL_OBLAST_END_DATE = date(2025, 7, 31)
KYIV_CITY_REGION = "Kyiv City"
OUTPUT_COLUMNS = ["region", "oblast", "raion", "start", "end", "start_local_date", "duration_minutes"]

@dataclass(frozen=True)
class BuildSummary:
    latest_complete_day: date | None
    current_complete_rows: int
    partial_day_rows: int
    daily_rows: int
    kyiv_city_rows: int
    historical_oblast_rows: int


def latest_completed_day(current_local_date: date, latest_local_date_in_dataset: date) -> date:
    return min(current_local_date - timedelta(days=1), latest_local_date_in_dataset)


def read_alerts(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return normalize_alerts(df)


def normalize_alerts(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename = {
        "region_title": "region", "region": "region",
        "oblast_title": "oblast", "oblast": "oblast",
        "raion_title": "raion", "raion": "raion",
        "started_at": "start", "start": "start",
        "finished_at": "end", "ended_at": "end", "end": "end",
    }
    df = df.rename(columns={c: rename[c] for c in df.columns if c in rename})
    if "oblast" not in df.columns:
        df["oblast"] = pd.NA
    if "region" not in df.columns:
        df["region"] = df["oblast"]
    if "raion" not in df.columns:
        df["raion"] = pd.NA
    if "start" not in df.columns:
        raise ValueError("Input must contain a start/started_at column")
    if "end" not in df.columns:
        df["end"] = pd.NaT
    df["start"] = pd.to_datetime(df["start"], utc=True, errors="coerce")
    df["end"] = pd.to_datetime(df["end"], utc=True, errors="coerce")
    df = df[df["start"].notna()].copy()
    df["start_local"] = df["start"].dt.tz_convert(KYIV_TZ)
    df["end_local"] = df["end"].dt.tz_convert(KYIV_TZ)
    df["start_local_date"] = df["start_local"].dt.date
    df["duration_minutes"] = (df["end"] - df["start"]).dt.total_seconds() / 60
    return df


def split_kyiv_city(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = df["region"].eq(KYIV_CITY_REGION)
    return df[mask].copy(), df[~mask].copy()


def is_raion_record(df: pd.DataFrame) -> pd.Series:
    return df["raion"].notna() & df["raion"].astype(str).str.strip().ne("") & ~df["region"].eq(KYIV_CITY_REGION)


def current_raion_records(df: pd.DataFrame, current_local_date: date | None = None) -> tuple[pd.DataFrame, pd.DataFrame, date | None]:
    current_local_date = current_local_date or datetime.now(KYIV_TZ).date()
    raion = df[is_raion_record(df)].copy()
    raion = raion[raion["start_local_date"] >= CURRENT_START_DATE].copy()
    if raion.empty:
        return raion, raion, None
    latest = latest_completed_day(current_local_date, max(raion["start_local_date"]))
    complete = raion[raion["start_local_date"] <= latest].copy()
    partial = raion[raion["start_local_date"] == current_local_date].copy()
    return complete, partial, latest


def historical_oblast_context(df: pd.DataFrame) -> pd.DataFrame:
    oblast_level = df[df["raion"].isna() | df["raion"].astype(str).str.strip().eq("")].copy()
    return oblast_level[oblast_level["start_local_date"] <= HISTORICAL_OBLAST_END_DATE].copy()


def _split_interval(row) -> list[tuple[date, pd.Timestamp, pd.Timestamp]]:
    start = row.start_local
    end = row.end_local
    if pd.isna(end) or end <= start:
        return []
    pieces = []
    cur = start
    while cur < end:
        next_midnight = pd.Timestamp(cur.date() + timedelta(days=1), tz=KYIV_TZ)
        stop = min(end, next_midnight)
        pieces.append((cur.date(), cur, stop))
        cur = stop
    return pieces


def daily_raion_activity(complete: pd.DataFrame) -> pd.DataFrame:
    valid = complete[(complete["end"].notna()) & (complete["duration_minutes"] > 0)].copy()
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
        minutes = sum((e - s).total_seconds() / 60 for s, e in merged)
        totals.append({"local_date": day, "raion": raion, "minutes": minutes, "records": len(g)})
    by_raion = pd.DataFrame(totals)
    out = by_raion.groupby("local_date", as_index=False).agg(
        active_raions=("raion", "nunique"),
        alert_records=("records", "sum"),
        total_raion_time_under_alert_minutes=("minutes", "sum"),
    )
    return out.sort_values("local_date")


def build_datasets(raw_path: Path, processed_dir: Path, current_local_date: date | None = None) -> BuildSummary:
    processed_dir.mkdir(parents=True, exist_ok=True)
    df = read_alerts(raw_path)
    kyiv, _ = split_kyiv_city(df)
    complete, partial, latest = current_raion_records(df, current_local_date)
    historical = historical_oblast_context(df)
    daily = daily_raion_activity(complete)
    complete[OUTPUT_COLUMNS].to_csv(processed_dir / "current_2026_raion_alerts_complete_days.csv", index=False)
    partial[OUTPUT_COLUMNS].to_csv(processed_dir / "current_partial_day_raion_alerts.csv", index=False)
    historical[OUTPUT_COLUMNS].to_csv(processed_dir / "historical_oblast_context.csv", index=False)
    daily.to_csv(processed_dir / "daily_2026_raion_activity.csv", index=False)
    return BuildSummary(latest, len(complete), len(partial), len(daily), len(kyiv), len(historical))
