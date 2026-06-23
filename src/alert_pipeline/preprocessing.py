from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

KYIV_TZ = "Europe/Kyiv"
DEDUP_FIELDS = ["oblast", "raion", "hromada", "level", "started_at", "finished_at", "source"]
REQUIRED_OUTPUT_FIELDS = [
    "oblast", "raion", "hromada", "level", "source", "started_at", "finished_at",
    "started_at_utc", "finished_at_utc", "started_at_kyiv", "finished_at_kyiv",
    "local_date", "local_year_month", "iso_week", "local_weekday", "local_hour",
    "duration_minutes", "duration_hours", "is_zero_duration", "is_negative_duration",
    "is_over_7_days", "is_complete_day",
]

@dataclass(frozen=True)
class Snapshot:
    source_url: str
    run_timestamp_utc: str
    run_timestamp_kyiv: str
    source_file_size: int
    sha256_checksum: str
    maximum_source_timestamp: str | None
    latest_represented_local_date: str | None
    latest_completed_day_used_for_analysis: str | None
    source_lag_days: int | None
    partial_day_status: dict

def remove_exact_duplicates(df: pd.DataFrame, fields: Iterable[str] = DEDUP_FIELDS) -> pd.DataFrame:
    return df.drop_duplicates(subset=list(fields), keep="first").reset_index(drop=True)

def parse_utc_timestamps(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce")

def convert_utc_to_kyiv(series: pd.Series) -> pd.Series:
    return series.dt.tz_convert(KYIV_TZ)

def add_timestamp_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["started_at_utc"] = parse_utc_timestamps(out["started_at"])
    out["finished_at_utc"] = parse_utc_timestamps(out["finished_at"])
    out["started_at_kyiv"] = convert_utc_to_kyiv(out["started_at_utc"])
    out["finished_at_kyiv"] = convert_utc_to_kyiv(out["finished_at_utc"])
    out["local_date"] = out["started_at_kyiv"].dt.date.astype("string")
    out["local_year_month"] = out["started_at_kyiv"].dt.strftime("%Y-%m")
    out["iso_week"] = out["started_at_kyiv"].dt.isocalendar().week.astype("Int64")
    out["local_weekday"] = out["started_at_kyiv"].dt.day_name()
    out["local_hour"] = out["started_at_kyiv"].dt.hour.astype("Int64")
    return out

def add_duration_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    duration = out["finished_at_utc"] - out["started_at_utc"]
    out["duration_minutes"] = duration.dt.total_seconds() / 60
    out["duration_hours"] = out["duration_minutes"] / 60
    return out

def add_duration_quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["is_zero_duration"] = out["duration_minutes"].eq(0).fillna(False)
    out["is_negative_duration"] = out["duration_minutes"].lt(0).fillna(False)
    out["is_over_7_days"] = out["duration_minutes"].gt(7 * 24 * 60).fillna(False)
    return out

def enrich_records(df: pd.DataFrame, latest_complete_day: str | pd.Timestamp | None = None) -> pd.DataFrame:
    out = add_duration_quality_flags(add_duration_columns(add_timestamp_columns(df)))
    if latest_complete_day is None:
        out["is_complete_day"] = False
    else:
        cutoff = pd.to_datetime(latest_complete_day).date()
        out["is_complete_day"] = pd.to_datetime(out["local_date"]).dt.date.le(cutoff)
    return out

def latest_local_date_in_dataset(df: pd.DataFrame) -> pd.Timestamp | None:
    dates = pd.to_datetime(df["local_date"], errors="coerce").dropna()
    return None if dates.empty else dates.max().normalize()

def calculate_latest_complete_day(current_local_ts, latest_local_date) -> pd.Timestamp | None:
    if latest_local_date is None or pd.isna(latest_local_date):
        return None
    current_local_date = pd.Timestamp(current_local_ts).tz_localize(None).normalize()
    latest_local_date = pd.Timestamp(latest_local_date).tz_localize(None).normalize()
    return min(current_local_date - pd.Timedelta(days=1), latest_local_date)

def detect_stale_source(current_local_ts, latest_local_date, stale_after_days: int = 1) -> tuple[int | None, bool]:
    if latest_local_date is None or pd.isna(latest_local_date):
        return None, True
    current_date = pd.Timestamp(current_local_ts).tz_localize(None).normalize()
    lag = int((current_date - pd.Timestamp(latest_local_date).tz_localize(None).normalize()).days)
    return lag, lag > stale_after_days

def separate_completed_and_partial_days(df: pd.DataFrame, latest_complete_day, current_local_ts) -> tuple[pd.DataFrame, pd.DataFrame]:
    latest_complete_day = pd.Timestamp(latest_complete_day).normalize()
    current_date = pd.Timestamp(current_local_ts).tz_localize(None).normalize()
    dates = pd.to_datetime(df["local_date"])
    completed = df.loc[dates.le(latest_complete_day)].copy()
    partial = df.loc[dates.eq(current_date)].copy()
    partial["is_complete_day"] = False
    return completed, partial

def complete_daily_date_index(start_date: str, end_date: str | pd.Timestamp) -> pd.DataFrame:
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    return pd.DataFrame({"date": pd.Series(dates.date).astype("string")})

def filter_2026_raion_records(df: pd.DataFrame, latest_complete_day) -> pd.DataFrame:
    dates = pd.to_datetime(df["local_date"])
    return df.loc[(df["level"] == "raion") & dates.ge("2026-01-01") & dates.le(pd.Timestamp(latest_complete_day))].copy()

def split_excluded_mixed_levels(df: pd.DataFrame) -> pd.DataFrame:
    dates = pd.to_datetime(df["local_date"])
    return df.loc[dates.ge("2026-01-01") & df["level"].isin(["oblast", "hromada"])].copy()

def split_kyiv_city(df: pd.DataFrame) -> pd.DataFrame:
    mask = df["oblast"].astype("string").str.contains("Kyiv City|Kyiv city|м. Київ|Kyiv", case=False, na=False) & df["raion"].isna()
    return df.loc[mask].copy()

def build_daily_activity(raion_df: pd.DataFrame, latest_complete_day) -> pd.DataFrame:
    base = complete_daily_date_index("2026-01-01", latest_complete_day)
    df = raion_df.copy()
    ordinary = ~(df["is_zero_duration"] | df["is_negative_duration"] | df["is_over_7_days"])
    grouped = df.groupby("local_date", dropna=False).agg(
        alert_record_count=("local_date", "size"), unique_raions=("raion", "nunique"), unique_oblasts=("oblast", "nunique"),
        zero_duration_record_count=("is_zero_duration", "sum"), over_seven_day_anomaly_count=("is_over_7_days", "sum"),
    ).reset_index().rename(columns={"local_date": "date"})
    durations = df.loc[ordinary].groupby("local_date")["duration_minutes"].agg(total_duration_minutes="sum", median_duration_minutes="median").reset_index().rename(columns={"local_date": "date"})
    out = base.merge(grouped, on="date", how="left").merge(durations, on="date", how="left")
    count_cols = ["alert_record_count", "unique_raions", "unique_oblasts", "zero_duration_record_count", "over_seven_day_anomaly_count"]
    out[count_cols] = out[count_cols].fillna(0).astype(int)
    out[["total_duration_minutes", "median_duration_minutes"]] = out[["total_duration_minutes", "median_duration_minutes"]].fillna(0.0)
    d = pd.to_datetime(out["date"])
    out["weekday"] = d.dt.day_name(); out["month"] = d.dt.month; out["is_complete_day"] = True
    return out

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def write_snapshot(snapshot: Snapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot.__dict__, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
