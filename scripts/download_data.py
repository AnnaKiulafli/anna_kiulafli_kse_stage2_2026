from __future__ import annotations

from pathlib import Path
import requests

SOURCE_URL = "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_en.csv"
RAW_PATH = Path("data/raw/official_data_en.csv")

def main() -> None:
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(SOURCE_URL, timeout=120)
    response.raise_for_status()
    RAW_PATH.write_bytes(response.content)
    print(f"Downloaded {len(response.content)} bytes to {RAW_PATH}")

if __name__ == "__main__":
    main()
