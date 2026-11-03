"""Generate packaged Serena prompts on a desktop GPU; never used by the app.

All downloads and temporary files stay on the project's D: drive. No cloud API.
Run with .tts-venv/Scripts/python.exe -m jiandong_ai.scripts.generate_serena_prompts.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import wave
import time

ROOT = Path(__file__).resolve().parents[2]
MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
OUTPUT = ROOT / "assets" / "voice" / "serena"


def configure_local_cache() -> None:
    cache = ROOT / ".speech-cache"
    for name, suffix in {
        "HF_HOME": "huggingface", "TORCH_HOME": "torch",
        "TEMP": "tmp", "TMP": "tmp", "TMPDIR": "tmp",
        "PIP_CACHE_DIR": "pip",
        "XDG_CACHE_HOME": "xdg", "NUMBA_CACHE_DIR": "numba",
        "MPLCONFIGDIR": "matplotlib", "GRADIO_TEMP_DIR": "gradio",
        "CUDA_CACHE_PATH": "cuda", "TORCH_EXTENSIONS_DIR": "extensions",
        "TRITON_CACHE_DIR": "triton", "TORCHINDUCTOR_CACHE_DIR": "inductor",
        "PYTORCH_KERNEL_CACHE_PATH": "kernels",
    }.items():
        path = cache / suffix
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def replace_file(source: Path, destination: Path) -> None:
    # Windows indexers may briefly hold a freshly written asset open.
    for attempt in range(20):
        try:
            source.replace(destination)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.1)


def count_speech(text: str) -> str | None:
    """Spell out training counts to avoid ambiguous digit pronunciation."""
    match = re.fullmatch(r"(\d{1,2})(次|秒)?", normalize(text))
    if not match or not 1 <= int(match[1]) <= 60:
        return None
    number = int(match[1])
    digits = "零一二三四五六七八九"
    spoken = digits[number] if number < 10 else (
        (digits[number // 10] if number >= 20 else "") + "十"
        + (digits[number % 10] if number % 10 else "")
    )
    return spoken + (match[2] or "") + "。"


def prompt_texts() -> list[str]:
    # Include actual constant speech from the app, rather than a second copy of it.
    texts = ["我在，你说。", "好的，随时叫我。", "组间休息", "准备开始",
             "好的，正在打开。", "训练结束", "热身", "拉伸"]
    sources = ["ai/session/voice_session.py", "ai/session/assistant_session.py", "pages/shell.py"]
    for relative in sources:
        tree = ast.parse((ROOT / "jiandong_ai" / relative).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "_speak" and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        texts.append(arg.value)
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                if any(isinstance(t, ast.Name) and t.id in {"GREETING", "_VOICE_ENABLED_GREETING"}
                       for t in node.targets) and isinstance(node.value.value, str):
                    texts.append(node.value.value)
        # Greeting passed as an `or` expression, and module-level help return values.
        if relative.endswith("voice_session.py"):
            for node in ast.walk(tree):
                if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant):
                    if isinstance(node.value.value, str) and "可以说" in node.value.value:
                        texts.append(node.value.value)
                if isinstance(node, ast.BoolOp):
                    for value in node.values:
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            if value.value.startswith("你好，想练"):
                                texts.append(value.value)
    tree = ast.parse((ROOT / "jiandong_ai/ai/action/exercise_kind.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if any(isinstance(t, ast.Name) and t.id.endswith("_label") for t in node.targets):
                if isinstance(node.value.value, str):
                    texts.extend([node.value.value, "下一个动作：" + node.value.value])
    for n in range(1, 61):
        texts.append(str(n))
        texts.append(f"{n} 次")
        texts.append(f"{n} 秒")
    return list({normalize(text): text for text in texts if text}.values())


def valid_wav(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as audio:
            if not (audio.getnchannels() == 1 and audio.getsampwidth() == 2
                    and audio.getframerate() == 24000 and audio.getnframes() > 0
                    and audio.getcomptype() == "NONE"):
                return False
            return len(audio.readframes(audio.getnframes())) == audio.getnframes() * 2
    except (OSError, EOFError, wave.Error):
        return False


def generate(*, limit: int | None = None) -> None:
    configure_local_cache()
    if (ROOT / ".speech-cache/qwen-serena-model/model.safetensors").exists():
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    # Heavy dependencies are desktop-only, intentionally absent from app requirements.
    import torch
    import faulthandler
    import soundfile as sf
    import numpy as np
    from qwen_tts import Qwen3TTSModel

    if not torch.cuda.is_available():
        raise RuntimeError("A CUDA GPU is required for this desktop generation workflow.")
    torch.set_num_threads(4)
    model = None
    local_model = ROOT / ".speech-cache/qwen-serena-model"
    if local_model.exists():
        for relative in ("model.safetensors", "speech_tokenizer/model.safetensors", "vocab.json", "tokenizer_config.json"):
            if not (local_model / relative).is_file():
                raise RuntimeError(f"Local model download is incomplete: {relative}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUTPUT / "manifest.json"
    manifest = {"schema": 1, "model": MODEL, "speaker": "Serena", "sample_rate": 24000,
                "license": "Apache-2.0", "clips": {}}
    source_info = local_model / "source.json"
    if source_info.exists():
        manifest["revision"] = json.loads(source_info.read_text(encoding="utf-8"))["revision"]
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("speaker") != "Serena" or existing.get("model") != MODEL:
            raise ValueError("Output directory contains a different voice or model.")
        manifest = existing
    from importlib.metadata import distribution
    package = distribution("qwen-tts")
    for entry in package.files or []:
        if str(entry).replace("\\", "/").endswith("/licenses/LICENSE"):
            (OUTPUT / "QWEN-LICENSE.txt").write_bytes(Path(package.locate_file(entry)).read_bytes())
            break
    (OUTPUT / "NOTICE.txt").write_text(
        "Local speech recordings generated with Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice.\n"
        "Speaker: Serena. Model license: Apache-2.0.\n"
        "Source: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice\n"
        "Model weights and Python inference dependencies are not shipped in the app.\n",
        encoding="utf-8",
    )
    texts = prompt_texts()
    if limit is not None:
        texts = texts[:limit]
    for index, text in enumerate(texts, 1):
        key = normalize(text)
        filename = hashlib.sha256(key.encode()).hexdigest()[:24] + ".wav"
        path = OUTPUT / filename
        count_text = count_speech(text)
        usable = valid_wav(path)
        if usable and count_text:
            with wave.open(str(path), "rb") as clip:
                usable = clip.getnframes() / clip.getframerate() <= 3.0
        if not usable:
            if model is None:
                model = Qwen3TTSModel.from_pretrained(
                    str(local_model) if local_model.is_dir() else MODEL,
                    device_map="cuda:0", dtype=torch.bfloat16,
                    attn_implementation="sdpa", local_files_only=local_model.is_dir(),
                )
                # Bound vocoder workspace on an 8 GB laptop GPU. Keep the official
                # decoder's left context so adjacent chunks remain continuous.
                from functools import partial
                decoder = model.model.speech_tokenizer.model.decoder
                decoder.chunked_decode = partial(decoder.chunked_decode, chunk_size=50)
            started = time.monotonic()
            print(f"Generating {index}/{len(texts)} ({len(text)} characters)", flush=True)
            faulthandler.dump_traceback_later(60, repeat=True)
            for attempt in range(3):
                with torch.inference_mode():
                    wavs, rate = model.generate_custom_voice(
                        text=count_text or text, language="Chinese", speaker="Serena",
                        non_streaming_mode=True, max_new_tokens=max(64, min(512, 24 + 12 * len(text))),
                    )
                if not np.isfinite(wavs[0]).all() or np.max(np.abs(wavs[0])) < 0.001:
                    raise RuntimeError(f"Silent or non-finite generated audio: {text}")
                if not count_text or len(wavs[0]) / rate <= 3.0:
                    break
            else:
                raise RuntimeError(f"Count audio is unexpectedly long after three attempts: {text}")
            faulthandler.cancel_dump_traceback_later()
            print(f"Synthesized in {time.monotonic() - started:.1f}s", flush=True)
            temporary = path.with_suffix(".tmp.wav")
            sf.write(str(temporary), wavs[0], rate, subtype="PCM_16")
            if not valid_wav(temporary):
                raise RuntimeError(f"Invalid generated audio: {temporary}")
            replace_file(temporary, path)
        manifest["clips"][key] = filename
        temporary_manifest = manifest_path.with_suffix(".tmp")
        temporary_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        replace_file(temporary_manifest, manifest_path)
        print(f"{index}/{len(texts)} {text}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Generate a small listening sample first")
    args = parser.parse_args()
    generate(limit=args.limit)
