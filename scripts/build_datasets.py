import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from alert_pipeline.pipeline import HISTORICAL_OBLAST_END_DATE, build_datasets

if __name__ == "__main__":
    summary = build_datasets(Path("data/raw/official_data_en.csv"), Path("data/processed"))
    print(f"latest_complete_day={summary.latest_complete_day}")
    print(f"current_complete_rows={summary.current_complete_rows}")
    print(f"partial_day_rows={summary.partial_day_rows}")
    print(f"daily_rows={summary.daily_rows}")
    print(f"kyiv_city_rows={summary.kyiv_city_rows}")
    print(f"historical_oblast_rows={summary.historical_oblast_rows}")
    print(f"historical_oblast_end_date={HISTORICAL_OBLAST_END_DATE}")
