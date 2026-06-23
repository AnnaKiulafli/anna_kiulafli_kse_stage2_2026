"""Download the official English Ukrainian air raid sirens dataset."""
from __future__ import annotations

import hashlib
from pathlib import Path

import requests

URL = "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_en.csv"
DESTINATION = Path("data/raw/official_data_en.csv")
TIMEOUT_SECONDS = 30
MIN_EXPECTED_BYTES = 1_000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    temp_path = DESTINATION.with_suffix(DESTINATION.suffix + ".tmp")

    try:
        response = requests.get(URL, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SystemExit(f"Download failed for {URL}: {exc}") from exc

    content = response.content
    size = len(content)
    if size < MIN_EXPECTED_BYTES:
        raise SystemExit(
            f"Downloaded file is unexpectedly small ({size} bytes); "
            "refusing to replace local data."
        )

    temp_path.write_bytes(content)
    temp_size = temp_path.stat().st_size
    if temp_size != size:
        temp_path.unlink(missing_ok=True)
        raise SystemExit(
            f"Incomplete write: expected {size} bytes but wrote {temp_size} bytes."
        )

    temp_path.replace(DESTINATION)
    checksum = sha256_file(DESTINATION)
    print(f"Downloaded: {URL}")
    print(f"Saved to: {DESTINATION}")
    print(f"File size: {DESTINATION.stat().st_size} bytes")
    print(f"SHA-256: {checksum}")


if __name__ == "__main__":
    main()
