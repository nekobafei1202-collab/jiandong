from __future__ import annotations

import json
import time

from jiandong_ai.ai.session.assistant_session import AssistantSession
from jiandong_ai.services.ai_assistant import AssistantReply


class _Assistant:
    def __init__(self, *replies: AssistantReply):
        self.replies = list(replies)
        self.inputs: list[str] = []

    def chat(self, text: str) -> AssistantReply:
        self.inputs.append(text)
        return self.replies.pop(0)


def _make_session(tmp_path, reply=None, **kwargs):
    spoken: list[str] = []
    ai = _Assistant(reply or AssistantReply(action="chat", reply="回答"))
    session = AssistantSession(
        bridge_dir=tmp_path,
        ai_client=ai,
        speaker=spoken.append,
        poll_interval=0.02,
        **kwargs,
    )
    return session, ai, spoken


def _wake(session: AssistantSession, tmp_path) -> None:
    (tmp_path / "assistant_wake.flag").write_text("1", encoding="utf-8")
    session._tick()
    (tmp_path / "asr_ready.flag").write_text("1")
    session._tick()


def test_wake_enters_listening_and_creates_active_flag(tmp_path):
    session, _, spoken = _make_session(tmp_path)

    _wake(session, tmp_path)

    assert session.state == "listening"
    assert session.is_active
    assert (tmp_path / "assistant_active.flag").exists()
    assert not (tmp_path / "assistant_wake.flag").exists()
    assert spoken == ["我在，你说。"]


def test_wake_is_ignored_during_training(tmp_path):
    session, _, spoken = _make_session(tmp_path)
    (tmp_path / "training_active.flag").write_text("1", encoding="utf-8")

    _wake(session, tmp_path)

    assert session.state == "dormant"
    assert not (tmp_path / "assistant_active.flag").exists()
    assert not spoken


def test_asr_result_is_dispatched_once_per_sequence(tmp_path):
    reply = AssistantReply(action="chat", reply="核心收紧。")
    session, ai, spoken = _make_session(tmp_path, reply)
    _wake(session, tmp_path)
    result = tmp_path / "asr_result.json"
    result.write_text(json.dumps({"seq": 7, "text": "怎么做平板支撑"}), encoding="utf-8")

    session._tick()
    session._tick()

    assert ai.inputs == ["怎么做平板支撑"]
    assert spoken[-1] == "核心收紧。"
    assert session.state == "listening"


def test_exit_phrase_and_idle_timeout_deactivate(tmp_path, monkeypatch):
    session, _, spoken = _make_session(tmp_path)
    _wake(session, tmp_path)

    session.handle_utterance("请退出助手")

    assert session.state == "dormant"
    assert not (tmp_path / "assistant_active.flag").exists()
    assert spoken[-1] == "好的，随时叫我。"

    clock = iter([100.0, 100.0, 100.0, 161.0])
    monkeypatch.setattr(
        "jiandong_ai.ai.session.assistant_session.time.monotonic",
        lambda: next(clock),
    )
    _wake(session, tmp_path)
    session._tick()
    assert session.state == "dormant"
    assert spoken[-1] == "好的，随时叫我。"


def test_training_becoming_active_deactivates_assistant(tmp_path):
    session, _, _ = _make_session(tmp_path)
    _wake(session, tmp_path)
    (tmp_path / "training_active.flag").write_text("1", encoding="utf-8")

    session._tick()

    assert session.state == "dormant"
    assert not (tmp_path / "assistant_active.flag").exists()


def test_recommend_dispatches_normalized_part_and_falls_back_to_reply(tmp_path):
    reply = AssistantReply(action="recommend", body_part="腿部", reply="为你推荐腿部训练。")
    parts: list[str] = []
    session, _, spoken = _make_session(
        tmp_path,
        reply,
        on_recommend=lambda part: parts.append(part),
    )
    _wake(session, tmp_path)

    session.handle_utterance("我想练腿")

    assert parts == ["leg"]
    assert spoken[-1] == "为你推荐腿部训练。"


def test_recommend_callback_can_handle_its_own_speech(tmp_path):
    reply = AssistantReply(action="recommend", body_part="核心", reply="不会重复播")
    session, _, spoken = _make_session(
        tmp_path,
        reply,
        on_recommend=lambda part: "",
    )
    _wake(session, tmp_path)

    session.handle_utterance("练核心")

    assert spoken == ["我在，你说。"]


def test_control_and_query_callbacks_are_dispatched(tmp_path):
    controls: list[str] = []
    session, _, spoken = _make_session(
        tmp_path,
        AssistantReply(action="pause", reply="暂停"),
        on_control=lambda action: controls.append(action) or "已暂停",
    )
    _wake(session, tmp_path)
    session.handle_utterance("暂停")
    assert controls == ["pause"]
    assert spoken[-1] == "已暂停"

    session._ai = _Assistant(AssistantReply(action="query_plan", reply="计划"))
    session._on_query_plan = lambda: "今天练深蹲。"
    session.handle_utterance("计划")
    assert spoken[-1] == "今天练深蹲。"


def test_network_failure_keeps_conversation_active(tmp_path):
    reply = AssistantReply(
        action="chat",
        reply="网络不太好，请稍后再试。",
        error="network_error",
    )
    session, _, spoken = _make_session(tmp_path, reply)
    _wake(session, tmp_path)

    session.handle_utterance("练腿")

    assert spoken[-1] == "网络不太好，请稍后再试。"
    assert session.state == "listening"
    assert (tmp_path / "assistant_active.flag").exists()


def test_start_stop_and_tts_file_lifecycle(tmp_path):
    session = AssistantSession(
        bridge_dir=tmp_path,
        ai_client=_Assistant(AssistantReply(action="chat", reply="回答")),
        poll_interval=0.02,
    )
    assert session.start()
    assert session.is_running
    (tmp_path / "asr_ready.flag").write_text("1")
    (tmp_path / "assistant_wake.flag").write_text("1", encoding="utf-8")
    deadline = time.time() + 2.0
    while time.time() < deadline and session.state != "listening":
        time.sleep(0.02)
    assert session.state == "listening"
    payload = json.loads((tmp_path / "tts.json").read_text(encoding="utf-8"))
    assert payload["seq"] == 1
    assert payload["text"] == "我在，你说。"

    session.stop()
    assert not session.is_running
    assert not (tmp_path / "assistant_active.flag").exists()


def test_waits_for_asr_before_greeting(tmp_path):
    session, _, spoken = _make_session(tmp_path)
    (tmp_path / "assistant_wake.flag").write_text("1")
    session._tick()
    assert session.state == "woken"
    assert not spoken
    (tmp_path / "asr_ready.flag").write_text("1")
    session._tick()
    assert session.state == "listening"
    assert spoken == ["我在，你说。"]


def test_navigation_does_not_call_api(tmp_path):
    destinations = []
    session, ai, _ = _make_session(tmp_path, on_navigate=lambda target: destinations.append(target) or "好的")
    _wake(session, tmp_path)
    for phrase in ["打开首页", "进入课程", "打开计划", "个人中心"]:
        session.handle_utterance(phrase)
    assert destinations == ["home", "courses", "plan", "profile"]
    assert ai.inputs == []


def test_playback_pauses_idle_and_restarts_after_completion(tmp_path, monkeypatch):
    session, ai, _ = _make_session(tmp_path)
    _wake(session, tmp_path)
    session._pending_tts_seq = 3
    monkeypatch.setattr("jiandong_ai.ai.session.assistant_session.time.monotonic", lambda: 1000.0)
    (tmp_path / "tts_status.json").write_text(json.dumps({"seq": 3, "busy": True}))
    session._tick()
    assert session.state == "listening"
    (tmp_path / "tts_status.json").write_text(json.dumps({"seq": 3, "busy": False}))
    session._tick()
    assert session._last_input_at == 1000.0
    assert session.state == "listening"
    assert ai.inputs == []

