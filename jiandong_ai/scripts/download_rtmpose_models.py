"""Download Good-GYM lightweight RTMPose ONNX models into models/."""

from __future__ import annotations

import urllib.request
from pathlib import Path

# Prefer jsDelivr (GitHub raw often times out in CN networks).
_BASES = (
    "https://cdn.jsdelivr.net/gh/yo-WASSUP/Good-GYM@master/models",
    "https://github.com/yo-WASSUP/Good-GYM/raw/master/models",
)

FILES = (
    "yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx",
    "rtmpose-t_simcc-body7_pt-body7_420e-256x192-026a1439_20230504.onnx",
)


def _models_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "models"


def download_one(name: str) -> Path:
    dest = _models_dir() / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"Already present: {dest} ({dest.stat().st_size} bytes)")
        return dest
    last_err: Exception | None = None
    for base in _BASES:
        url = f"{base}/{name}"
        try:
            print(f"Downloading {url}")
            urllib.request.urlretrieve(url, dest)
            if dest.stat().st_size > 1_000_000:
                print(f"Saved {dest} ({dest.stat().st_size} bytes)")
                return dest
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"  failed: {exc}")
    raise RuntimeError(f"Could not download {name}") from last_err


def main() -> None:
    for name in FILES:
        download_one(name)
    print(
        "Source: https://github.com/yo-WASSUP/Good-GYM (MIT) — "
        "RTMPose via rtmlib / OpenMMLab."
    )


if __name__ == "__main__":
    main()
