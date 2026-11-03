from __future__ import annotations

import json
import time

from jiandong_ai.ai.session.voice_session import (
    LoginVoiceGuide,
    VoiceCourseSession,
    map_voice_command,
)


def _make_session(tmp_path, spoken=None, started=None):
    spoken_list = spoken if spoken is not None else []
    started_list = started if started is not None else []
    session = VoiceCourseSession(
        bridge_dir=tmp_path,
        speaker=spoken_list.append,
        on_start_training=lambda actions, title: started_list.append(
            (list(actions), title)
        ),
        poll_interval=0.02,
    )
    return session, spoken_list, started_list


def test_full_course_selection_flow(tmp_path):
    session, spoken, started = _make_session(tmp_path)
    assert session.state == "idle"

    session.begin()
    assert session.state == "ask_part"
    assert any("部位" in text for text in spoken)

    session.handle_keyword("腿部")
    assert session.state == "confirm"
    assert any("腿部训练" in text for text in spoken)

    session.handle_keyword("确认")
    assert session.state == "ready"
    assert any("开始训练" in text for text in spoken)

    session.handle_keyword("开始训练")
    assert session.state == "idle"
    assert len(started) == 1
    actions, title = started[0]
    assert title == "腿部训练"
    assert actions[0] == "热身" and actions[-1] == "拉伸"


def test_change_recommendation(tmp_path):
    session, spoken, _ = _make_session(tmp_path)
    session.begin()
    session.handle_keyword("核心")
    first = spoken[-1]
    session.handle_keyword("换一个")
    assert session.state == "confirm"
    assert spoken[-1] != first


def test_invalid_keyword_stays_in_state(tmp_path):
    session, spoken, _ = _make_session(tmp_path)
    session.begin()
    session.handle_keyword("今天天气怎么样")
    assert session.state == "ask_part"
    session.handle_keyword("腿部")
    session.handle_keyword("随便来一个")
    assert session.state == "confirm"


def test_change_part_mid_confirm(tmp_path):
    session, spoken, _ = _make_session(tmp_path)
    session.begin()
    session.handle_keyword("腿部")
    session.handle_keyword("背部")
    assert session.state == "confirm"
    assert "背部训练" in spoken[-1]


def test_ready_stage_other_keywords_stay(tmp_path):
    session, _, started = _make_session(tmp_path)
    session.begin()
    session.handle_keyword("上肢")
    session.handle_keyword("确认")
    session.handle_keyword("确认")
    assert session.state == "ready"
    assert not started


def test_poll_voice_cmd_file(tmp_path):
    session, spoken, started = _make_session(tmp_path)
    assert session.start()
    session.begin()

    cmd = tmp_path / "voice_cmd.json"
    cmd.write_text(json.dumps({"seq": 1, "keyword": "全身"}), encoding="utf-8")
    deadline = time.time() + 2.0
    while time.time() < deadline and session.state != "confirm":
        time.sleep(0.02)
    assert session.state == "confirm"

    # 同一 seq 不应被重复消费。
    last_spoken = len(spoken)
    time.sleep(0.15)
    assert len(spoken) == last_spoken

    cmd.write_text(json.dumps({"seq": 2, "keyword": "确认"}), encoding="utf-8")
    deadline = time.time() + 2.0
    while time.time() < deadline and session.state != "ready":
        time.sleep(0.02)
    assert session.state == "ready"
    session.stop()
    assert not session.is_running


def test_tts_written_to_bridge_dir(tmp_path):
    # 不传 speaker 时对话文本原子写入 tts.json。
    session = VoiceCourseSession(bridge_dir=tmp_path)
    session.begin()
    payload = json.loads((tmp_path / "tts.json").read_text(encoding="utf-8"))
    assert payload["seq"] == 1
    assert "部位" in payload["text"]
    session._speak("第二条")
    payload = json.loads((tmp_path / "tts.json").read_text(encoding="utf-8"))
    assert payload["seq"] == 2


def test_start_without_bridge_dir_writable_fails_silently(tmp_path):
    bad = tmp_path / "blocked"
    bad.write_text("not a dir", encoding="utf-8")
    session = VoiceCourseSession(bridge_dir=bad / "sub", speaker=lambda t: None)
    assert session.start() is False


def test_login_keyword_ignored_by_course_session(tmp_path):
    session, spoken, _ = _make_session(tmp_path)
    session.begin()
    spoken_before = len(spoken)

    assert map_voice_command("登录", in_training=False) is None
    session.handle_keyword("登录")

    assert session.state == "ask_part"
    assert len(spoken) == spoken_before


def test_help_keyword_speaks_course_help_outside_training(tmp_path):
    session, spoken, _ = _make_session(tmp_path)
    session.begin()
    spoken_before = len(spoken)

    session.handle_keyword("帮助")

    assert session.state == "ask_part"
    assert len(spoken) == spoken_before + 1
    assert "腿部" in spoken[-1]
    assert "确认" in spoken[-1]


def test_voice_session_active_flag_lifecycle_and_tts_seq_handoff(tmp_path):
    flag = tmp_path / "voice_session_active.flag"
    guide = LoginVoiceGuide(on_login=lambda: None, bridge_dir=tmp_path)
    assert guide.start()
    assert flag.exists()
    greeting = json.loads((tmp_path / "tts.json").read_text(encoding="utf-8"))
    assert greeting["seq"] == 1
    assert greeting["text"] == LoginVoiceGuide.GREETING
    assert "演示账号" in greeting["text"]
    assert "用户协议和隐私政策" in greeting["text"]
    guide.stop()
    assert not flag.exists()

    course = VoiceCourseSession(bridge_dir=tmp_path)
    assert course.start()
    course.begin()
    opening = json.loads((tmp_path / "tts.json").read_text(encoding="utf-8"))
    assert opening["seq"] == 2
    assert "部位" in opening["text"]

    # 登录页重复退出清理不能误删 MainShell 新会话的 flag。
    guide.stop()
    assert flag.exists()
    course.stop()
    assert not flag.exists()


def test_session_stop_preserves_new_owner_flag(tmp_path):
    flag = tmp_path / "voice_session_active.flag"
    first = VoiceCourseSession(bridge_dir=tmp_path, speaker=lambda t: None)
    second = VoiceCourseSession(bridge_dir=tmp_path, speaker=lambda t: None)
    assert first.start()
    assert second.start()

    first.stop()
    assert flag.exists()
    second.stop()
    assert not flag.exists()


def test_login_voice_guide_consumes_login_and_help(tmp_path):
    logins = []
    guide = LoginVoiceGuide(
        on_login=lambda: logins.append("login"),
        bridge_dir=tmp_path,
        poll_interval=0.02,
    )
    assert guide.start()
    cmd = tmp_path / "voice_cmd.json"
    tts = tmp_path / "tts.json"
    cmd.write_text(json.dumps({"seq": 1, "keyword": "腿部"}), encoding="utf-8")
    time.sleep(0.08)
    assert not logins

    cmd.write_text(json.dumps({"seq": 2, "keyword": "帮助"}), encoding="utf-8")
    deadline = time.time() + 2.0
    while time.time() < deadline:
        payload = json.loads(tts.read_text(encoding="utf-8"))
        if payload["seq"] == 2:
            break
        time.sleep(0.02)
    payload = json.loads(tts.read_text(encoding="utf-8"))
    assert payload["seq"] == 2
    assert payload["text"] == LoginVoiceGuide.GREETING
    assert not logins

    cmd.write_text(json.dumps({"seq": 3, "keyword": "登录"}), encoding="utf-8")
    deadline = time.time() + 2.0
    while time.time() < deadline and not logins:
        time.sleep(0.02)
    assert logins == ["login"]
    time.sleep(0.08)
    assert logins == ["login"]
    guide.stop()
    assert not (tmp_path / "voice_session_active.flag").exists()
