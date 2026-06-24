from __future__ import annotations

from pathlib import Path
from datetime import date

import pandas as pd

from .pipeline import CURRENT_START_DATE, KYIV_TZ, LONG_INTERVAL_DAYS, ORIGINAL_COLUMNS

VALID_MAX_MINUTES = LONG_INTERVAL_DAYS * 24 * 60


def read_processed(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    for c in ["local_date"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c]).dt.date
    for c in ["start_local", "end_local", "started_at", "finished_at"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", utc=True).dt.tz_convert(KYIV_TZ)
    return df


def geo_key(df: pd.DataFrame) -> pd.Series:
    return df["oblast"].fillna("<missing_oblast>") + " | " + df["raion"].fillna("<missing_raion>")


def valid_duration_mask(df: pd.DataFrame) -> pd.Series:
    return df["finished_at"].notna() & df["duration_minutes"].gt(0) & df["duration_minutes"].le(VALID_MAX_MINUTES)


def validate_inputs(raion: pd.DataFrame, daily: pd.DataFrame, non_raion: pd.DataFrame, latest_complete_day: date, oblast_totals: pd.DataFrame | None = None, raion_totals: pd.DataFrame | None = None) -> None:
    if not raion.empty and not raion["level"].eq("raion").all():
        raise AssertionError("Primary raion input contains non-raion rows")
    if not non_raion.empty and non_raion["level"].eq("raion").any():
        raise AssertionError("Non-raion input contains raion rows")
    if not raion.empty and max(raion["local_date"]) > latest_complete_day:
        raise AssertionError("Partial-day raion records are present in complete-days data")
    if not non_raion.empty and max(non_raion["local_date"]) > latest_complete_day:
        raise AssertionError("Partial-day non-raion records are present in complete-days data")
    for label, frame in [("raion", raion), ("non-raion", non_raion)]:
        subset = [c for c in ORIGINAL_COLUMNS if c in frame.columns]
        if subset and frame.duplicated(subset=subset).any():
            raise AssertionError(f"Exact duplicate source {label} records are present")
    expected = pd.date_range(CURRENT_START_DATE, latest_complete_day, freq="D").date
    if list(daily["local_date"]) != list(expected):
        raise AssertionError("Daily calendar is incomplete or out of order")
    if "geo_id" in raion.columns and not raion["geo_id"].equals(geo_key(raion)):
        raise AssertionError("Geographic key must be oblast + raion")
    if oblast_totals is not None and raion_totals is not None:
        national = float(daily["total_raion_time_under_alert_minutes"].sum())
        oblast_sum = float(oblast_totals["total_allocated_raion_alert_minutes"].sum())
        raion_sum = float(raion_totals["total_allocated_alert_minutes"].sum())
        if max(abs(national - oblast_sum), abs(national - raion_sum)) > 1e-6:
            raise AssertionError("National, oblast, and raion allocated-minute totals do not reconcile")


def national_daily(daily: pd.DataFrame) -> pd.DataFrame:
    out = daily.sort_values("local_date").copy()
    out["rolling_7d_total_minutes"] = out["total_raion_time_under_alert_minutes"].rolling(7, min_periods=1).mean()
    out["rolling_14d_total_minutes"] = out["total_raion_time_under_alert_minutes"].rolling(14, min_periods=1).mean()
    q1 = out["total_raion_time_under_alert_minutes"].quantile(0.25)
    q3 = out["total_raion_time_under_alert_minutes"].quantile(0.75)
    cutoff = q3 + 1.5 * (q3 - q1)
    out["unusually_high_activity"] = out["total_raion_time_under_alert_minutes"].gt(cutoff)
    out.attrs["high_activity_rule"] = f"total minutes > Q3 + 1.5*IQR ({cutoff:.2f})"
    return out


def monthly_national(daily: pd.DataFrame) -> pd.DataFrame:
    x = daily.copy(); x["month"] = pd.to_datetime(x["local_date"]).dt.to_period("M").astype(str)
    return x.groupby("month", as_index=False).agg(
        total_records_started=("records_started_on_date", "sum"),
        total_interval_segments=("interval_segments", "sum"),
        total_raion_time_under_alert_minutes=("total_raion_time_under_alert_minutes", "sum"),
        average_daily_active_raions=("active_raions", "mean"),
        average_daily_minutes=("total_raion_time_under_alert_minutes", "mean"),
    )


def weekday_patterns(daily: pd.DataFrame) -> pd.DataFrame:
    x = daily.copy(); d = pd.to_datetime(x["local_date"]); x["weekday"] = d.dt.day_name(); x["weekday_num"] = d.dt.weekday
    return x.groupby(["weekday_num", "weekday"], as_index=False).agg(average_daily_minutes=("total_raion_time_under_alert_minutes", "mean"), average_active_raions=("active_raions", "mean"), days=("local_date", "count")).sort_values("weekday_num")


def coverage_tables(raion: pd.DataFrame) -> dict[str, pd.DataFrame]:
    x = raion.copy(); x["geo_id"] = geo_key(x); x["month"] = pd.to_datetime(x["local_date"]).dt.to_period("M").astype(str)
    first_last = x.groupby(["oblast", "raion", "geo_id"], dropna=False, as_index=False).agg(first_date=("local_date","min"), last_date=("local_date","max"), records=("geo_id","size"))
    active_by_month = x.groupby("month")["geo_id"].nunique().rename("active_raions").reset_index()
    all_months = set(x["month"].unique())
    missing = x.groupby(["oblast", "raion", "geo_id"], dropna=False)["month"].apply(lambda s: ", ".join(sorted(all_months - set(s)))).reset_index(name="months_with_no_recorded_alerts")
    missing = missing[missing["months_with_no_recorded_alerts"].ne("")]
    oblast_month = x.groupby(["oblast", "month"], dropna=False)["geo_id"].nunique().reset_index(name="active_raions")
    changing = oblast_month.groupby("oblast", dropna=False)["active_raions"].nunique().reset_index(name="distinct_monthly_recorded_raion_counts")
    changing = changing[changing["distinct_monthly_recorded_raion_counts"].gt(1)]
    missing_values = raion[raion["oblast"].isna() | raion["raion"].isna()].copy()
    concise = first_last.groupby("oblast", dropna=False).agg(represented_raions=("geo_id","nunique"), first_date=("first_date","min"), last_date=("last_date","max"), records=("records","sum")).reset_index()
    return {"first_last_raion": first_last, "monthly_recorded_activity_presence": active_by_month, "raions_without_recorded_alerts_in_one_or_more_months": missing, "oblasts_with_changing_recorded_raion_presence": changing, "missing_oblast_or_raion": missing_values, "coverage_by_oblast": concise}



def allocated_minutes_by_geo_day(raion: pd.DataFrame, latest_complete_day: date | None = None) -> pd.DataFrame:
    """Split valid intervals by Kyiv local day and merge overlaps within each oblast + raion + day."""
    valid = raion[valid_duration_mask(raion)].copy()
    if latest_complete_day is None and not raion.empty:
        latest_complete_day = max(raion["local_date"])
    if not valid.empty:
        valid["geo_id"] = geo_key(valid)
    rows: list[dict[str, object]] = []
    for r in valid.itertuples(index=False):
        start = r.start_local
        end = r.end_local
        cur = start
        while cur < end:
            next_midnight = pd.Timestamp(cur.date() + pd.Timedelta(days=1), tz=KYIV_TZ)
            stop = min(end, next_midnight)
            if latest_complete_day is None or cur.date() <= latest_complete_day:
                rows.append({
                    "oblast": r.oblast,
                    "raion": r.raion,
                    "geo_id": r.geo_id,
                    "local_date": cur.date(),
                    "start": cur,
                    "end": stop,
                })
            cur = stop
    if not rows:
        return pd.DataFrame(columns=["oblast", "raion", "geo_id", "local_date", "allocated_minutes", "interval_segments"])
    parts = pd.DataFrame(rows)
    totals: list[dict[str, object]] = []
    for (oblast, raion_name, geo_id_value, day), group in parts.sort_values("start").groupby(["oblast", "raion", "geo_id", "local_date"], dropna=False):
        merged: list[list[pd.Timestamp]] = []
        for seg in group.itertuples(index=False):
            if not merged or seg.start > merged[-1][1]:
                merged.append([seg.start, seg.end])
            elif seg.end > merged[-1][1]:
                merged[-1][1] = seg.end
        totals.append({
            "oblast": oblast,
            "raion": raion_name,
            "geo_id": geo_id_value,
            "local_date": day,
            "allocated_minutes": sum((end - start).total_seconds() / 60 for start, end in merged),
            "interval_segments": len(group),
        })
    return pd.DataFrame(totals)

def regional_comparisons(raion: pd.DataFrame, latest_complete_day: date | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = raion.copy(); x["geo_id"] = geo_key(x); valid = x[valid_duration_mask(x)].copy()
    if latest_complete_day is None and not x.empty:
        latest_complete_day = max(x["local_date"])
    analysis_day_count = (latest_complete_day - CURRENT_START_DATE).days + 1 if latest_complete_day is not None else 0
    allocated = allocated_minutes_by_geo_day(x, latest_complete_day)
    oblast = x.groupby("oblast", dropna=False).agg(total_alert_records=("oblast","size"), represented_raions=("geo_id","nunique")).reset_index()
    mins = allocated.groupby("oblast", dropna=False)["allocated_minutes"].sum().rename("total_allocated_raion_alert_minutes").reset_index()
    oblast_active = allocated.groupby("oblast", dropna=False)["local_date"].nunique().rename("active_days").reset_index()
    oblast = oblast.merge(mins, how="left", on="oblast").merge(oblast_active, how="left", on="oblast").fillna({"total_allocated_raion_alert_minutes":0, "active_days":0})
    oblast["active_days"] = oblast["active_days"].astype(int)
    oblast["average_daily_allocated_minutes"] = oblast["total_allocated_raion_alert_minutes"] / analysis_day_count if analysis_day_count else 0
    oblast["records_per_represented_raion"] = oblast["total_alert_records"] / oblast["represented_raions"]
    ra = x.groupby(["oblast","raion","geo_id"], dropna=False).agg(total_alert_records=("geo_id","size")).reset_index()
    alloc_raion = allocated.groupby(["oblast","raion","geo_id"], dropna=False)["allocated_minutes"].sum().rename("total_allocated_alert_minutes").reset_index()
    raion_active = allocated.groupby(["oblast","raion","geo_id"], dropna=False)["local_date"].nunique().rename("active_days").reset_index()
    ds = valid.groupby(["oblast","raion","geo_id"], dropna=False)["duration_minutes"].agg(average_duration_per_valid_alert="mean", median_duration="median", longest_valid_alert="max").reset_index()
    return oblast.sort_values("total_allocated_raion_alert_minutes", ascending=False), ra.merge(alloc_raion, how="left", on=["oblast","raion","geo_id"]).merge(raion_active, how="left", on=["oblast","raion","geo_id"]).merge(ds, how="left", on=["oblast","raion","geo_id"]).fillna({"total_allocated_alert_minutes":0, "active_days":0})


def duration_summary(raion: pd.DataFrame) -> dict[str, pd.DataFrame]:
    valid = raion[valid_duration_mask(raion)].copy(); valid["month"] = pd.to_datetime(valid["local_date"]).dt.to_period("M").astype(str)
    overall = valid["duration_minutes"].describe(percentiles=[.25,.5,.75,.9,.95]).to_frame("duration_minutes")
    return {"overall": overall, "by_month": valid.groupby("month")["duration_minutes"].describe(percentiles=[.25,.5,.75,.9,.95]).reset_index(), "by_oblast": valid.groupby("oblast", dropna=False)["duration_minutes"].describe(percentiles=[.25,.5,.75,.9,.95]).reset_index(), "longest_valid_alerts": valid.nlargest(25, "duration_minutes")}


def non_raion_counts(non_raion: pd.DataFrame, raion: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {f"by_{c}": non_raion.groupby(c, dropna=False).size().rename("records").reset_index() for c in ["level","oblast","raion","hromada"]}
    out["raion_vs_non_raion"] = pd.DataFrame({"category":["raion","non_raion"], "records":[len(raion), len(non_raion)]})
    return out


def historical_context(hist: pd.DataFrame) -> dict[str, pd.DataFrame | str]:
    if hist.empty: return {"date_range":"No historical records", "monthly_totals":pd.DataFrame(), "granularity":pd.DataFrame()}
    x=hist.copy(); x["month"]=pd.to_datetime(x["local_date"]).dt.to_period("M").astype(str)
    return {"date_range":f"{min(x['local_date'])} to {max(x['local_date'])}", "monthly_totals":x.groupby("month").size().rename("records").reset_index(), "granularity":x.groupby(["month","level"], dropna=False).size().rename("records").reset_index()}
