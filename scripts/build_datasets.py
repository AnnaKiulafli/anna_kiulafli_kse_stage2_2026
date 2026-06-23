from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from alert_pipeline.preprocessing import (
    REQUIRED_OUTPUT_FIELDS, Snapshot, build_daily_activity, calculate_latest_complete_day,
    detect_stale_source, enrich_records, filter_2026_raion_records, remove_exact_duplicates,
    separate_completed_and_partial_days, sha256_file, split_excluded_mixed_levels, split_kyiv_city,
    write_snapshot,
)
from download_data import RAW_PATH, SOURCE_URL

PROCESSED_DIR = Path("data/processed")
SNAPSHOT_PATH = Path("reports/metadata/analysis_snapshot.json")

def _write_csv(df: pd.DataFrame, path: Path, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is not None:
        for col in columns:
            if col not in df.columns:
                df[col] = pd.NA
        df = df[columns]
    df.to_csv(path, index=False)
    print(f"Wrote {len(df)} rows to {path}")

def main() -> None:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Run scripts/download_data.py first; missing {RAW_PATH}")
    raw = pd.read_csv(RAW_PATH)
    deduped = remove_exact_duplicates(raw)
    enriched = enrich_records(deduped)

    now_utc = pd.Timestamp.now(tz="UTC")
    now_kyiv = now_utc.tz_convert("Europe/Kyiv")
    latest_local = enriched["started_at_kyiv"].dropna().dt.tz_localize(None).dt.normalize().max()
    latest_complete_day = calculate_latest_complete_day(now_kyiv, latest_local)
    source_lag, stale = detect_stale_source(now_kyiv, latest_local)
    enriched = enrich_records(deduped, latest_complete_day)

    completed_all, partial_all = separate_completed_and_partial_days(enriched, latest_complete_day, now_kyiv)
    complete_raion = filter_2026_raion_records(completed_all, latest_complete_day)
    partial_raion = partial_all.loc[partial_all["level"].eq("raion")].copy()
    excluded_mixed = split_excluded_mixed_levels(enriched)
    kyiv_city = split_kyiv_city(enriched.loc[pd.to_datetime(enriched["local_date"]).ge("2026-01-01")])
    historical_oblast = enriched.loc[(enriched["level"].eq("oblast")) & pd.to_datetime(enriched["local_date"]).lt("2026-01-01")].copy()
    daily = build_daily_activity(complete_raion, latest_complete_day)

    _write_csv(complete_raion, PROCESSED_DIR / "current_2026_raion_alerts_complete_days.csv", REQUIRED_OUTPUT_FIELDS)
    _write_csv(partial_raion, PROCESSED_DIR / "current_partial_day_raion_alerts.csv", REQUIRED_OUTPUT_FIELDS)
    _write_csv(excluded_mixed, PROCESSED_DIR / "current_2026_excluded_mixed_levels.csv", REQUIRED_OUTPUT_FIELDS)
    _write_csv(kyiv_city, PROCESSED_DIR / "current_2026_kyiv_city.csv", REQUIRED_OUTPUT_FIELDS)
    _write_csv(historical_oblast, PROCESSED_DIR / "historical_oblast_context.csv", REQUIRED_OUTPUT_FIELDS)
    _write_csv(daily, PROCESSED_DIR / "daily_2026_raion_activity.csv")

    max_source_ts = pd.concat([enriched["started_at_utc"], enriched["finished_at_utc"]]).dropna().max()
    has_current = pd.to_datetime(enriched["local_date"]).eq(now_kyiv.tz_localize(None).normalize()).any()
    snapshot = Snapshot(
        source_url=SOURCE_URL,
        run_timestamp_utc=now_utc.isoformat(),
        run_timestamp_kyiv=now_kyiv.isoformat(),
        source_file_size=RAW_PATH.stat().st_size,
        sha256_checksum=sha256_file(RAW_PATH),
        maximum_source_timestamp=None if pd.isna(max_source_ts) else max_source_ts.isoformat(),
        latest_represented_local_date=None if pd.isna(latest_local) else latest_local.date().isoformat(),
        latest_completed_day_used_for_analysis=None if latest_complete_day is None else latest_complete_day.date().isoformat(),
        source_lag_days=source_lag,
        partial_day_status={"current_local_date_records_present": bool(has_current), "potentially_stale": bool(stale)},
    )
    write_snapshot(snapshot, SNAPSHOT_PATH)
    print(f"raw_row_count={len(raw)}")
    print(f"deduplicated_row_count={len(deduped)}")
    print(f"latest_source_timestamp={snapshot.maximum_source_timestamp}")
    print(f"latest_represented_local_date={snapshot.latest_represented_local_date}")
    print(f"latest_completed_day={snapshot.latest_completed_day_used_for_analysis}")
    print(f"source_lag_days={source_lag}")
    print(f"partial_day_status={snapshot.partial_day_status}")

if __name__ == "__main__":
    main()
