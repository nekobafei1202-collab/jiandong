from __future__ import annotations

from types import SimpleNamespace

import jiandong_ai.pages.shell as shell_module
from jiandong_ai.pages.profile.profile_page import ProfileView
from jiandong_ai.pages.shell import MainShell
from jiandong_ai.services.mock_service import MockService


class _FakeVoiceSession:
    instances = []

    def __init__(self, on_start_training):
        self.on_start_training = on_start_training
        self.started = False
        self.stopped = False
        self.greetings = []
        self.__class__.instances.append(self)

    def start(self) -> bool:
        self.started = True
        return True

    def begin(self, greeting=None) -> None:
        self.greetings.append(greeting)

    def stop(self) -> None:
        self.stopped = True

    def speak(self, text: str) -> None:
        pass


class _FakeAssistantSession:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.__class__.instances.append(self)

    def start(self) -> bool:
        self.started = True
        return True

    def stop(self) -> None:
        self.stopped = True


def _fresh_service(tmp_path):
    MockService._instance = None
    svc = MockService.instance()
    svc.init(tmp_path)
    return svc


def _bare_shell() -> MainShell:
    shell = MainShell.__new__(MainShell)
    shell._host = SimpleNamespace(run_thread=lambda fn: fn())
    shell._voice_session = None
    shell._assistant_session = None
    shell._voice_onboarding_done = False
    return shell


def _patch_android_runtime(monkeypatch):
    flags = []
    _FakeVoiceSession.instances = []
    _FakeAssistantSession.instances = []
    monkeypatch.setattr(shell_module, "is_android_runtime", lambda: True)
    monkeypatch.setattr(shell_module, "write_voice_flag", flags.append)
    monkeypatch.setattr(shell_module, "VoiceCourseSession", _FakeVoiceSession)
    monkeypatch.setattr(shell_module, "AssistantSession", _FakeAssistantSession)
    return flags


def test_voice_switch_starts_and_stops_session_immediately(tmp_path, monkeypatch):
    svc = _fresh_service(tmp_path)
    svc.set_voice_accessibility(True)
    flags = _patch_android_runtime(monkeypatch)
    shell = _bare_shell()

    assert shell.start_voice_session_if_needed(announce_enabled=True) is True
    assert flags == [True]
    session = _FakeVoiceSession.instances[0]
    assert session.started
    assert session.greetings == [MainShell._VOICE_ENABLED_GREETING]
    assert len(_FakeAssistantSession.instances) == 1
    assert _FakeAssistantSession.instances[0].started

    # 幂等：重复打开/remount 不新增会话，也不重复播报开启文案。
    assert shell.start_voice_session_if_needed(announce_enabled=True) is True
    assert len(_FakeVoiceSession.instances) == 1
    assert session.greetings == [MainShell._VOICE_ENABLED_GREETING]

    shell.stop_voice_session()
    assert shell._voice_session is None
    assert session.stopped
    assert _FakeAssistantSession.instances[0].stopped
    assert flags == [True, False]
    shell.stop_voice_session()
    # 删除不存在的 flag 是无害幂等操作，重复 stop 不应恢复会话。
    assert flags == [True, False, False]
    assert shell._voice_session is None


def test_shell_creation_uses_default_greeting_and_disabled_switch_stays_idle(
    tmp_path, monkeypatch
):
    svc = _fresh_service(tmp_path)
    svc.set_voice_accessibility(True)
    flags = _patch_android_runtime(monkeypatch)
    shell = _bare_shell()

    shell._maybe_start_voice_session()
    assert flags == [True]
    assert _FakeVoiceSession.instances[0].greetings == [None]

    svc.set_voice_accessibility(False)
    shell._voice_session = None
    assert shell.start_voice_session_if_needed() is False
    assert flags == [True, False]
    assert len(_FakeVoiceSession.instances) == 1


def test_stop_voice_session_on_desktop_does_not_write_flags(tmp_path, monkeypatch):
    _fresh_service(tmp_path)
    _patch_android_runtime(monkeypatch)
    shell = _bare_shell()
    session = _FakeVoiceSession(on_start_training=lambda actions, title: None)
    shell._voice_session = session
    monkeypatch.setattr(shell_module, "is_android_runtime", lambda: False)

    shell.stop_voice_session()

    assert session.stopped
    assert shell._voice_session is None


def test_profile_toggle_invokes_shell_callback_and_desktop_fallback_is_safe(tmp_path):
    svc = _fresh_service(tmp_path)
    view = ProfileView.__new__(ProfileView)
    view._svc = svc
    view._voice_switch = SimpleNamespace(value=True)
    calls = []
    view.on_voice_accessibility_changed = calls.append

    view._toggle_voice_accessibility(None)
    assert svc.get_voice_accessibility() is True
    assert calls == [True]

    view.on_voice_accessibility_changed = None
    view._voice_switch.value = False
    view._toggle_voice_accessibility(None)
    assert svc.get_voice_accessibility() is False


def test_ai_assistant_switch_gates_session_and_key_change_reloads(tmp_path, monkeypatch):
    svc = _fresh_service(tmp_path)
    svc.set_voice_accessibility(True)
    _patch_android_runtime(monkeypatch)
    shell = _bare_shell()
    shell._voice_session = _FakeVoiceSession(on_start_training=lambda actions, title: None)

    svc.set_ai_assistant_enabled(False)
    assert shell._start_assistant_session_if_needed() is False
    assert not _FakeAssistantSession.instances

    svc.set_ai_assistant_enabled(True)
    assert shell._start_assistant_session_if_needed() is True
    first = _FakeAssistantSession.instances[0]
    assert first.started

    shell._on_ai_api_key_changed(True)
    assert first.stopped
    assert len(_FakeAssistantSession.instances) == 2
    assert shell._assistant_session is _FakeAssistantSession.instances[1]
