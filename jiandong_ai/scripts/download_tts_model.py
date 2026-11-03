"""Download the sherpa-onnx Chinese VITS TTS model (system-TTS fallback).

Output layout under models/tts/ (copied verbatim into app assets/tts/ by
prepare_android_bridge._copy_tts_models):

    model.onnx   (vits-aishell3 int8, ~40MB, 174 speakers, 8kHz)
    lexicon.txt / tokens.txt
    phone.fst / date.fst / number.fst / new_heteronym.fst
    (rule FSTs: number/date 归一化，计数播报需要)

Model: csukuangfj/vits-zh-aishell3 (int8), docs:
https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/vits.html
"""

from __future__ import annotations

import shutil
import socket
import tarfile
import tempfile
import urllib.request
from pathlib import Path

# urlretrieve has no timeout; keep slow/blocked endpoints from hanging forever.
socket.setdefaulttimeout(60)

_URLS = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
    "vits-zh-aishell3.tar.bz2",
)

# hf-mirror fallback (CN): individual files from csukuangfj/vits-zh-aishell3.
_HF_BASE = "https://hf-mirror.com/csukuangfj/vits-zh-aishell3/resolve/main/"
_HF_FILES = {
    "vits-aishell3.int8.onnx": "model.onnx",
    "lexicon.txt": "lexicon.txt",
    "tokens.txt": "tokens.txt",
    "phone.fst": "phone.fst",
    "date.fst": "date.fst",
    "number.fst": "number.fst",
    "new_heteronym.fst": "new_heteronym.fst",
}

REQUIRED = ("model.onnx", "lexicon.txt", "tokens.txt")


def _tts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "models" / "tts"


def _pick(names: list[str], suffix: str) -> str | None:
    hits = [n for n in names if n.endswith(suffix)]
    return hits[0] if hits else None


def download() -> Path:
    dest = _tts_dir()
    dest.mkdir(parents=True, exist_ok=True)
    if all((dest / name).exists() for name in REQUIRED):
        print(f"Already present: {dest}")
        return dest
    last_err: Exception | None = None
    for url in _URLS:
        try:
            print(f"Downloading {url}")
            with tempfile.NamedTemporaryFile(suffix=".tar.bz2", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                urllib.request.urlretrieve(url, tmp_path)
                with tarfile.open(tmp_path) as tar:
                    names = tar.getnames()
                    mapping = {}
                    for suffix, out_name in (
                        (".int8.onnx", "model.onnx"),
                        ("lexicon.txt", "lexicon.txt"),
                        ("tokens.txt", "tokens.txt"),
                        ("phone.fst", "phone.fst"),
                        ("date.fst", "date.fst"),
                        ("number.fst", "number.fst"),
                        ("new_heteronym.fst", "new_heteronym.fst"),
                    ):
                        member = _pick(names, suffix)
                        if member is not None:
                            mapping[member] = out_name
                    if "model.onnx" not in mapping.values():
                        member = _pick(names, ".onnx")
                        if member:
                            mapping[member] = "model.onnx"
                    for member, out_name in mapping.items():
                        src = tar.extractfile(member)
                        if src is None:
                            raise RuntimeError(f"unreadable member {member}")
                        (dest / out_name).write_bytes(src.read())
                        print(f"  {member} -> {out_name}")
            finally:
                tmp_path.unlink(missing_ok=True)
            if all((dest / name).exists() for name in REQUIRED):
                return dest
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"  failed: {exc}")
    # GitHub release CDN 不可达时的 hf-mirror 回退（逐文件下载）。
    try:
        for src_name, out_name in _HF_FILES.items():
            url = _HF_BASE + src_name
            print(f"Downloading {url}")
            # hf-mirror 对 python-urllib 默认 UA 的 LFS 文件返回 403。
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            with urllib.request.urlopen(req) as resp, open(dest / out_name, "wb") as out:
                shutil.copyfileobj(resp, out)
            print(f"  {src_name} -> {out_name}")
        return dest
    except Exception as exc:  # noqa: BLE001
        last_err = exc
        print(f"  failed: {exc}")
    raise RuntimeError("Could not download the TTS model") from last_err


def main() -> None:
    dest = download()
    missing = [name for name in REQUIRED if not (dest / name).exists()]
    if missing:
        raise SystemExit(f"Incomplete model dir {dest}: missing {missing}")
    size_mb = (dest / "model.onnx").stat().st_size / 1e6
    print(f"Done. model.onnx {size_mb:.1f}MB. Run prepare_android_bridge.py to bundle into assets/tts/.")


if __name__ == "__main__":
    main()
