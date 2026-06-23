import hashlib
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from alert_pipeline.pipeline import (  # noqa: E402
    CURRENT_START_DATE,
    DEDUP_FIELDS,
    HISTORICAL_OBLAST_END_DATE,
    KYIV_CITY_OBLAST,
    KYIV_TZ,
    build_datasets,
    normalize_alerts,
)

RAW = Path("data/raw/official_data_en.csv")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    summary = build_datasets(RAW, Path("data/processed"))
    raw = pd.read_csv(RAW)
    dedup = normalize_alerts(raw, deduplicate=True)
    raw_norm = normalize_alerts(raw, deduplicate=False)
    current_local_date = datetime.now(KYIV_TZ).date()
    print("Source snapshot")
    print(f"file_size_bytes={RAW.stat().st_size}")
    print(f"sha256={sha256(RAW)}")
    print(f"raw_row_count={len(raw)}")
    print(f"exact_deduplicated_row_count={len(dedup)}")
    print(f"duplicates_removed={len(raw) - len(dedup)}")
    print(f"maximum_source_timestamp={dedup['started_at'].max()}")
    print(f"current_local_run_date={current_local_date}")
    print(f"latest_complete_day={summary.latest_complete_day}")
    print("\nExact deduplication")
    print(f"DEDUP_FIELDS={DEDUP_FIELDS}")
    print("Deduplication is applied before analytical filtering in normalize_alerts/read_alerts/build_datasets.")
    print("\nFilters")
    print(f"current_2026_raion_alerts_complete_days: level == 'raion' and local_date >= {CURRENT_START_DATE} and local_date <= latest_complete_day")
    print("current_partial_day_raion_alerts: level == 'raion' and local_date == current_local_run_date")
    print(f"current_2026_kyiv_city_complete_days: oblast == {KYIV_CITY_OBLAST!r} and local_date >= {CURRENT_START_DATE} and local_date <= latest_complete_day")
    print(f"current_partial_day_kyiv_city: oblast == {KYIV_CITY_OBLAST!r} and local_date == current_local_run_date")
    print(f"historical_oblast_context: level == 'oblast' and local_date <= {HISTORICAL_OBLAST_END_DATE}")
    print("daily_2026_raion_activity: daily merged non-overlapping alert minutes by raion from current_2026_raion_alerts_complete_days")
    print("\nAudit table")
    for k, v in summary.audit["counts"].items():
        print(f"{k}: {v}")
    print("\nKyiv City counts")
    print(f"all-time exact Kyiv City count={int(dedup['oblast'].eq(KYIV_CITY_OBLAST).sum())}")
    rows_2026 = dedup[dedup['local_date'] >= CURRENT_START_DATE]
    print(f"2026 exact Kyiv City count={int(rows_2026['oblast'].eq(KYIV_CITY_OBLAST).sum())}")
    print(f"completed-day 2026 Kyiv City count={summary.kyiv_city_complete_rows}")
    print(f"partial-day 2026 Kyiv City count={summary.kyiv_city_partial_rows}")
    print("\nHistorical context")
    hist_raw = raw_norm[raw_norm['level'].eq('oblast') & (raw_norm['local_date'] <= HISTORICAL_OBLAST_END_DATE)]
    hist = dedup[dedup['level'].eq('oblast') & (dedup['local_date'] <= HISTORICAL_OBLAST_END_DATE)]
    print(f"raw oblast rows through cutoff={len(hist_raw)}")
    print(f"deduplicated oblast rows through cutoff={len(hist)}")
    print(f"duplicates removed={len(hist_raw) - len(hist)}")
    print(f"earliest local date={hist['local_date'].min() if not hist.empty else None}")
    print(f"latest local date={hist['local_date'].max() if not hist.empty else None}")
    print(f"distinct oblast values={hist['oblast'].nunique(dropna=True)}")
    print("\nInvariant checks")
    for k, v in summary.audit["invariants"].items():
        print(f"{k}: {v}")
