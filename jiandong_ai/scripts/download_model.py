"""Download MediaPipe pose_landmarker_lite.task into models/."""

from __future__ import annotations

import urllib.request
from pathlib import Path

URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    dest = root / "models" / "pose_landmarker_lite.task"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"Already present: {dest} ({dest.stat().st_size} bytes)")
        return
    print(f"Downloading {URL}")
    urllib.request.urlretrieve(URL, dest)
    print(f"Saved {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
