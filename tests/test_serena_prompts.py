from __future__ import annotations

import json
from pathlib import Path
import struct
import wave

import pytest

from jiandong_ai.scripts.generate_serena_prompts import count_speech, normalize, prompt_texts, valid_wav
from jiandong_ai.scripts import prepare_android_bridge as prepare
from jiandong_ai.scripts.build_android import packaging_exclusions, sanitize_staging


def test_build_expands_debug_globs_into_real_excluded_paths(tmp_path):
    (tmp_path / '_phone_home.png').write_bytes(b'debug')
    (tmp_path / '_test_assistant_tmp4').mkdir()
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'assets/logo.png').write_bytes(b'app asset')
    excluded = packaging_exclusions(tmp_path, ['.speech-cache', '_*.png', '_test_assistant_tmp*'])
    assert set(excluded) == {'.speech-cache', '_phone_home.png', '_test_assistant_tmp4'}


def test_staging_cleanup_preserves_source_and_rejects_parent_paths(tmp_path):
    original = tmp_path / 'storage'
    original.mkdir()
    (original / 'data.json').write_text('keep')
    stage = tmp_path / 'build/python-app'
    stage.mkdir(parents=True)
    (stage / 'main.pyc').write_bytes(b'app')
    (stage / 'storage').mkdir()
    (stage / 'storage/data.json').write_text('do not package')
    sanitize_staging(tmp_path, ['storage'])
    assert (original / 'data.json').read_text() == 'keep'
    assert not (stage / 'storage').exists()
    assert (stage / 'main.pyc').read_bytes() == b'app'
    with pytest.raises(ValueError, match='Unsafe'):
        sanitize_staging(tmp_path, ['../../storage'])
    assert (original / 'data.json').read_text() == 'keep'


@pytest.mark.parametrize(("text", "spoken"), [
    ("1", "一。"), ("10 秒", "十秒。"), ("11 次", "十一次。"),
    ("20", "二十。"), ("60 次", "六十次。"), ("准备开始", None),
])
def test_training_counts_have_unambiguous_chinese_pronunciation(text, spoken):
    assert count_speech(text) == spoken


def _recording(root: Path) -> Path:
    source = root / "assets/voice/serena"
    source.mkdir(parents=True)
    with wave.open(str(source / ("a" * 24 + ".wav")), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24000)
        output.writeframes(struct.pack("<hhh", -12000, 0, 12000))
    manifest = {"schema": 1, "speaker": "Serena", "clips": {
        normalize(text): "a" * 24 + ".wav" for text in prompt_texts()
    }}
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return source


def test_packaging_copies_only_valid_referenced_audio(tmp_path, monkeypatch):
    source = _recording(tmp_path)
    (source / "debug.log").write_text("not an app asset")
    monkeypatch.setattr(prepare, "ROOT", tmp_path)
    destination = tmp_path / "native-assets"
    prepare._copy_serena_prompts(destination)
    packaged = destination / "voice/serena"
    assert set(p.name for p in packaged.iterdir()) == {"manifest.json", "a" * 24 + ".wav"}
    assert valid_wav(packaged / ("a" * 24 + ".wav"))


def test_incomplete_generation_cannot_be_packaged(tmp_path, monkeypatch):
    source = _recording(tmp_path)
    path = source / "manifest.json"
    manifest = json.loads(path.read_text())
    del manifest["clips"][normalize("我在，你说。")]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(prepare, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="incomplete"):
        prepare._copy_serena_prompts(tmp_path / "native-assets")


@pytest.mark.parametrize("filename", ["../outside.wav", "a" * 24 + ".wav"])
def test_unsafe_or_corrupt_audio_is_rejected(tmp_path, monkeypatch, filename):
    source = _recording(tmp_path)
    (source / ("a" * 24 + ".wav")).write_bytes(b"broken audio")
    path = source / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["clips"][normalize("我在，你说。")] = filename
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(prepare, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="invalid"):
        prepare._copy_serena_prompts(tmp_path / "native-assets")
