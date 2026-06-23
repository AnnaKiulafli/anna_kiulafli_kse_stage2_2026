import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from alert_pipeline.pipeline import HISTORICAL_OBLAST_END_DATE, build_datasets

if __name__ == "__main__":
    summary = build_datasets(Path("data/raw/official_data_en.csv"), Path("data/processed"))
    print(f"latest_complete_day={summary.latest_complete_day}")
    print(f"current_complete_rows={summary.current_complete_rows}")
    print(f"partial_day_rows={summary.partial_day_rows}")
    print(f"non_raion_complete_rows={summary.non_raion_complete_rows}")
    print(f"non_raion_partial_rows={summary.non_raion_partial_rows}")
    print(f"daily_rows={summary.daily_rows}")
    print(f"kyiv_city_rows={summary.kyiv_city_rows}")
    print(f"historical_oblast_rows={summary.historical_oblast_rows}")
    print(f"zero_activity_dates={summary.zero_activity_dates}")
    print(f"zero_duration_anomalies={summary.zero_duration_anomalies}")
    print(f"negative_duration_anomalies={summary.negative_duration_anomalies}")
    print(f"longer_than_seven_day_anomalies={summary.longer_than_seven_day_anomalies}")
    print(f"missing_finished_at_anomalies={summary.missing_finished_at_anomalies}")
    print(f"historical_oblast_end_date={HISTORICAL_OBLAST_END_DATE}")
