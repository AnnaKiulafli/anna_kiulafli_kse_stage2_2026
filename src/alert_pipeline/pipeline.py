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
LONG_INTERVAL_DAYS = 7
ORIGINAL_COLUMNS = ["oblast", "raion", "hromada", "level", "source", "started_at", "finished_at"]
PROCESSED_COLUMNS = ORIGINAL_COLUMNS + ["start_local", "end_local", "local_date", "duration_minutes"]
DAILY_COLUMNS = ["local_date", "active_raions", "records_started_on_date", "interval_segments", "total_raion_time_under_alert_minutes"]

@dataclass(frozen=True)
class BuildSummary:
    latest_complete_day: date | None
    current_complete_rows: int
    partial_day_rows: int
    non_raion_complete_rows: int
    non_raion_partial_rows: int
    daily_rows: int
    kyiv_city_rows: int
    historical_oblast_rows: int
    zero_activity_dates: int
    zero_duration_anomalies: int
    negative_duration_anomalies: int
    longer_than_seven_day_anomalies: int
    missing_finished_at_anomalies: int


def latest_completed_day(current_local_date: date, latest_local_date_in_dataset: date) -> date:
    return min(current_local_date - timedelta(days=1), latest_local_date_in_dataset)


def read_alerts(path: Path) -> pd.DataFrame:
    return normalize_alerts(pd.read_csv(path))


def normalize_alerts(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rename = {"region_title": "oblast", "region": "oblast", "oblast_title": "oblast", "started_at": "started_at", "start": "started_at", "finished_at": "finished_at", "ended_at": "finished_at", "end": "finished_at"}
    df = df.rename(columns={c: rename[c] for c in df.columns if c in rename})
    for c in ORIGINAL_COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    if "started_at" not in df.columns:
        raise ValueError("Input must contain a started_at/start column")
    df["start"] = pd.to_datetime(df["started_at"], utc=True, errors="coerce")
    df["end"] = pd.to_datetime(df["finished_at"], utc=True, errors="coerce")
    df = df[df["start"].notna()].copy()
    df["start_local"] = df["start"].dt.tz_convert(KYIV_TZ)
    df["end_local"] = df["end"].dt.tz_convert(KYIV_TZ)
    df["local_date"] = df["start_local"].dt.date
    df["duration_minutes"] = (df["end"] - df["start"]).dt.total_seconds() / 60
    df["region"] = df["oblast"]
    return exact_deduplicate(df)


def exact_deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    subset = [c for c in ORIGINAL_COLUMNS if c in df.columns]
    return df.drop_duplicates(subset=subset).copy()


def latest_dataset_local_date(df: pd.DataFrame) -> date | None:
    if df.empty:
        return None
    return max(df["local_date"])


def split_kyiv_city(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    mask = df["oblast"].eq(KYIV_CITY_REGION)
    return df[mask].copy(), df[~mask].copy()


def is_raion_record(df: pd.DataFrame) -> pd.Series:
    return df["level"].eq("raion")


def is_non_raion_record(df: pd.DataFrame) -> pd.Series:
    return ~df["level"].eq("raion")


def split_current_records(df: pd.DataFrame, current_local_date: date | None = None, latest_local_date_in_dataset: date | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, date | None]:
    current_local_date = current_local_date or datetime.now(KYIV_TZ).date()
    latest_local_date_in_dataset = latest_local_date_in_dataset or latest_dataset_local_date(df)
    if latest_local_date_in_dataset is None:
        empty = df.iloc[0:0].copy()
        return empty, empty, empty, empty, None
    latest = latest_completed_day(current_local_date, latest_local_date_in_dataset)
    current = df[df["local_date"] >= CURRENT_START_DATE].copy()
    complete_all = current[current["local_date"] <= latest].copy()
    partial_all = current[current["local_date"] == current_local_date].copy()
    return (
        complete_all[is_raion_record(complete_all)].copy(),
        partial_all[is_raion_record(partial_all)].copy(),
        complete_all[is_non_raion_record(complete_all)].copy(),
        partial_all[is_non_raion_record(partial_all)].copy(),
        latest,
    )


def current_raion_records(df: pd.DataFrame, current_local_date: date | None = None, latest_local_date_in_dataset: date | None = None) -> tuple[pd.DataFrame, pd.DataFrame, date | None]:
    complete, partial, _, _, latest = split_current_records(df, current_local_date, latest_local_date_in_dataset)
    return complete, partial, latest


def historical_oblast_context(df: pd.DataFrame) -> pd.DataFrame:
    historical = df[df["level"].eq("oblast")].copy()
    return historical[historical["local_date"] <= HISTORICAL_OBLAST_END_DATE].copy()


def anomaly_frames(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    missing = df[df["end"].isna()].copy()
    with_end = df[df["end"].notna()].copy()
    zero = with_end[with_end["duration_minutes"].eq(0)].copy()
    negative = with_end[with_end["duration_minutes"].lt(0)].copy()
    long = with_end[with_end["duration_minutes"].gt(LONG_INTERVAL_DAYS * 24 * 60)].copy()
    return {"zero_duration_intervals": zero, "negative_duration_intervals": negative, "longer_than_seven_day_intervals": long, "missing_finished_at_intervals": missing}


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


def daily_raion_activity(complete: pd.DataFrame, latest_complete_day: date | None = None) -> pd.DataFrame:
    if latest_complete_day is None:
        latest_complete_day = max(complete["local_date"]) if not complete.empty else CURRENT_START_DATE - timedelta(days=1)
    calendar = pd.DataFrame({"local_date": list(pd.date_range(CURRENT_START_DATE, latest_complete_day, freq="D").date)})
    records_started = complete.groupby("local_date").size().rename("records_started_on_date").reset_index() if not complete.empty else pd.DataFrame(columns=["local_date", "records_started_on_date"])
    valid = complete[(complete["end"].notna()) & (complete["duration_minutes"] > 0) & (complete["duration_minutes"] <= LONG_INTERVAL_DAYS * 24 * 60)].copy()
    rows = []
    for row in valid.itertuples(index=False):
        for d, s, e in _split_interval(row):
            rows.append({"oblast": row.oblast, "raion": row.raion, "local_date": d, "start": s, "end": e})
    if rows:
        parts = pd.DataFrame(rows)
        totals = []
        for (day, oblast, raion), g in parts.sort_values("start").groupby(["local_date", "oblast", "raion"]):
            merged = []
            for r in g.itertuples(index=False):
                if not merged or r.start > merged[-1][1]:
                    merged.append([r.start, r.end])
                elif r.end > merged[-1][1]:
                    merged[-1][1] = r.end
            totals.append({"local_date": day, "oblast": oblast, "raion": raion, "minutes": sum((e - s).total_seconds() / 60 for s, e in merged), "segments": len(g)})
        by_raion = pd.DataFrame(totals)
        daily = by_raion.groupby("local_date", as_index=False).agg(active_raions=("raion", "count"), interval_segments=("segments", "sum"), total_raion_time_under_alert_minutes=("minutes", "sum"))
    else:
        daily = pd.DataFrame(columns=["local_date", "active_raions", "interval_segments", "total_raion_time_under_alert_minutes"])
    out = calendar.merge(records_started, on="local_date", how="left").merge(daily, on="local_date", how="left")
    for c in ["active_raions", "records_started_on_date", "interval_segments"]:
        out[c] = out[c].fillna(0).astype(int)
    out["total_raion_time_under_alert_minutes"] = out["total_raion_time_under_alert_minutes"].fillna(0.0)
    return out[DAILY_COLUMNS]


def non_raion_audit(non_raion: pd.DataFrame) -> pd.DataFrame:
    return non_raion.groupby(["level", "oblast", "raion", "hromada"], dropna=False).size().rename("records").reset_index()


def build_datasets(raw_path: Path, processed_dir: Path, current_local_date: date | None = None) -> BuildSummary:
    processed_dir.mkdir(parents=True, exist_ok=True)
    df = read_alerts(raw_path)
    full_latest = latest_dataset_local_date(df)
    complete, partial, non_raion_complete, non_raion_partial, latest = split_current_records(df, current_local_date, full_latest)
    kyiv, _ = split_kyiv_city(df[(df["local_date"] >= CURRENT_START_DATE) & (df["local_date"] <= latest)].copy() if latest else df.iloc[0:0].copy())
    historical = historical_oblast_context(df)
    daily = daily_raion_activity(complete, latest)
    anomalies = anomaly_frames(df[df["local_date"] >= CURRENT_START_DATE].copy())
    complete[PROCESSED_COLUMNS].to_csv(processed_dir / "current_2026_raion_alerts_complete_days.csv", index=False)
    partial[PROCESSED_COLUMNS].to_csv(processed_dir / "current_partial_day_raion_alerts.csv", index=False)
    non_raion_complete[PROCESSED_COLUMNS].to_csv(processed_dir / "current_2026_non_raion_records_complete_days.csv", index=False)
    non_raion_partial[PROCESSED_COLUMNS].to_csv(processed_dir / "current_partial_day_non_raion_records.csv", index=False)
    non_raion_audit(non_raion_complete).to_csv(processed_dir / "current_2026_non_raion_records_complete_days_audit.csv", index=False)
    historical[PROCESSED_COLUMNS].to_csv(processed_dir / "historical_oblast_context.csv", index=False)
    daily.to_csv(processed_dir / "daily_2026_raion_activity.csv", index=False)
    for name, frame in anomalies.items():
        frame[PROCESSED_COLUMNS].to_csv(processed_dir / f"{name}.csv", index=False)
    zero_activity = int((daily["active_raions"].eq(0) & daily["total_raion_time_under_alert_minutes"].eq(0)).sum())
    return BuildSummary(latest, len(complete), len(partial), len(non_raion_complete), len(non_raion_partial), len(daily), len(kyiv), len(historical), zero_activity, len(anomalies["zero_duration_intervals"]), len(anomalies["negative_duration_intervals"]), len(anomalies["longer_than_seven_day_intervals"]), len(anomalies["missing_finished_at_intervals"]))
