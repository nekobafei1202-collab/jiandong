from __future__ import annotations

from jiandong_ai.services.mock_service import MockService


def _fresh_service(tmp_path):
    MockService._instance = None
    svc = MockService.instance()
    svc.init(tmp_path)
    return svc


def test_voice_settings_defaults(tmp_path):
    svc = _fresh_service(tmp_path)
    assert svc.get_voice_accessibility() is False
    assert svc.get_voice_correction_announce() is True
    assert svc.get_ai_assistant_enabled() is True


def test_voice_settings_persist(tmp_path):
    svc = _fresh_service(tmp_path)
    svc.set_voice_accessibility(True)
    svc.set_voice_correction_announce(False)
    svc.set_ai_assistant_enabled(False)
    assert svc.get_voice_accessibility() is True
    assert svc.get_voice_correction_announce() is False
    assert svc.get_ai_assistant_enabled() is False

    svc2 = _fresh_service(tmp_path)
    assert svc2.get_voice_accessibility() is True
    assert svc2.get_voice_correction_announce() is False
    assert svc2.get_ai_assistant_enabled() is False


def test_voice_settings_do_not_affect_existing_fields(tmp_path):
    svc = _fresh_service(tmp_path)
    svc.set_strict_mode(True)
    svc.set_voice_accessibility(True)
    assert svc.get_strict_mode() is True

    svc2 = _fresh_service(tmp_path)
    assert svc2.get_strict_mode() is True
    assert svc2.get_voice_accessibility() is True
    # 旧数据文件没有新字段时保持默认值。
    import json

    store = tmp_path / "jiandong_data.json"
    payload = json.loads(store.read_text(encoding="utf-8"))
    payload.pop("voice_accessibility", None)
    payload.pop("voice_correction_announce", None)
    payload.pop("ai_assistant_enabled", None)
    store.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    svc3 = _fresh_service(tmp_path)
    assert svc3.get_voice_accessibility() is False
    assert svc3.get_voice_correction_announce() is True
    assert svc3.get_ai_assistant_enabled() is True
    assert svc3.get_strict_mode() is True
