"""Download the sherpa-onnx SenseVoice ASR model and Silero VAD.

Output layout under models/asr/ (copied verbatim into app assets/asr/ by
prepare_android_bridge._copy_asr_models):

    model.onnx       SenseVoice-small int8, ~228MB
    tokens.txt
    silero_vad.onnx  Silero VAD v5, ~630KB

GitHub release CDN is unreliable in the local CN environment, so the primary
sources are hf-mirror mirrors of the official sherpa-onnx artifacts.
"""

from __future__ import annotations

import shutil
import socket
import urllib.request
from pathlib import Path

socket.setdefaulttimeout(60)

_BASE_SENSE_VOICE = (
    "https://hf-mirror.com/chris-cao/"
    "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/resolve/main/"
)
_BASE_VAD = "https://hf-mirror.com/R4kSo1997/sherpa-onnx-silero-vad-v5/resolve/main/"

FILES: dict[str, tuple[str, int]] = {
    "model.onnx": (_BASE_SENSE_VOICE + "model.int8.onnx", 239_233_841),
    "tokens.txt": (_BASE_SENSE_VOICE + "tokens.txt", 315_894),
    "silero_vad.onnx": (_BASE_VAD + "silero_vad.onnx", 643_854),
}


def _asr_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "models" / "asr"


def _download(url: str, dest: Path, min_size: int) -> None:
    if dest.exists() and dest.stat().st_size >= min_size:
        print(f"Already present: {dest.name} ({dest.stat().st_size} bytes)")
        return
    print(f"Downloading {url}")
    # hf-mirror rejects python-urllib's default UA on LFS files.
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with urllib.request.urlopen(req) as resp, open(tmp, "wb") as out:
            shutil.copyfileobj(resp, out)
        if tmp.stat().st_size < min_size:
            raise RuntimeError(f"truncated download: {tmp.stat().st_size} bytes")
        tmp.replace(dest)
        print(f"  -> {dest.name} ({dest.stat().st_size} bytes)")
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    dest = _asr_dir()
    dest.mkdir(parents=True, exist_ok=True)
    for name, (url, min_size) in FILES.items():
        _download(url, dest / name, min_size)
    print("Done. Run prepare_android_bridge.py to bundle into assets/asr/.")


if __name__ == "__main__":
    main()
