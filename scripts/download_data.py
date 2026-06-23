from pathlib import Path
from urllib.request import urlretrieve

URL = "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_en.csv"
OUT = Path("data/raw/official_data_en.csv")

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(URL, OUT)
    print(f"Downloaded {URL} to {OUT}")
