"""语音训练的入镜门槛、引导步骤和状态反馈，使用真实队列与桥文件。"""
import json
import time
from types import SimpleNamespace

import pytest

from jiandong_ai.ai.pose.keypoint import Keypoint, KeypointName
from jiandong_ai.ai.pose.pose_result import PoseResult
from jiandong_ai.ai.session.android_bridge_session import AndroidBridgePoseSession
from jiandong_ai.pages.training import training_page
from jiandong_ai.services.mock_service import MockService


@pytest.fixture
def training(tmp_path, monkeypatch):
    service = MockService()
    service.init(tmp_path / "settings")
    service.set_voice_accessibility(True)
    monkeypatch.setattr(MockService, "_instance", service)
    bridge = AndroidBridgePoseSession(bridge_dir=tmp_path / "bridge")
    monkeypatch.setattr(training_page, "create_pose_session", lambda: bridge)
    view = training_page.TrainingView(SimpleNamespace(run_thread=lambda fn: fn()))
    view.prepare_native_entry(actions=["热身", "深蹲", "拉伸"])
    assert view.launch_native_preview()
    try:
        yield view, bridge
    finally:
        view._clear_rest_state()
        bridge.stop()
        view._pipeline.stop()


def read(bridge, name):
    return json.loads((bridge.bridge_dir / name).read_text(encoding="utf-8"))


def full_pose():
    return PoseResult.from_keypoints([
        Keypoint(KeypointName.nose, .5, .1, .95),
        Keypoint(KeypointName.leftShoulder, .4, .3, .95),
        Keypoint(KeypointName.rightShoulder, .6, .3, .95),
        Keypoint(KeypointName.leftHip, .45, .6, .95),
        Keypoint(KeypointName.rightHip, .55, .6, .95),
        Keypoint(KeypointName.leftAnkle, .45, .9, .95),
        Keypoint(KeypointName.rightAnkle, .55, .9, .95),
    ])


def test_preview_checks_framing_without_starting_timer(training):
    view, bridge = training
    assert read(bridge, "hud.json")["voiceReady"] is False
    view._last_framing_at = 0
    view._on_voice_preview_frame(None, PoseResult.empty())
    assert "检测不到你" in read(bridge, "training_speech.json")["text"]
    assert view._started_at is None
    for _ in range(16):
        view._on_voice_preview_frame(None, full_pose())
    assert read(bridge, "hud.json")["voiceReady"] is True
    assert "开始训练" in read(bridge, "training_speech.json")["text"]
    assert view._started_at is None
    view._on_voice_preview_frame(None, PoseResult.empty())
    assert read(bridge, "hud.json")["voiceReady"] is False


def test_voice_start_continue_pause_resume_and_end(training):
    view, bridge = training
    for _ in range(16):
        view._on_voice_preview_frame(None, full_pose())
    view._on_native_event("begin", {})
    assert view._phase == "running"
    assert "热身" in read(bridge, "training_speech.json")["text"]
    view._on_native_event("voice_continue", {})
    assert view._action_name == "深蹲"
    assert "双脚" in read(bridge, "training_speech.json")["text"]
    view._on_native_event("pause", {})
    assert view._phase == "paused"
    assert "已暂停" in read(bridge, "training_speech.json")["text"]
    view._on_native_event("resume", {})
    assert view._phase == "running"
    assert "已恢复" in read(bridge, "training_speech.json")["text"]
    view._on_native_event("voice_repeat", {})
    assert "深蹲" in read(bridge, "training_speech.json")["text"]
    view._on_native_event("stop", {})
    assert view._phase == "finished"
    assert read(bridge, "hud.json")["sessionDone"]
    assert "训练已结束" in read(bridge, "training_speech.json")["text"]


def test_guide_step_also_requests_pause_when_person_is_lost(training):
    view, bridge = training
    view._on_native_event("begin", {})
    assert view._action_name == "热身"
    view._person_missing_since = time.monotonic() - 4
    view._on_frame(None, PoseResult.empty())
    assert read(bridge, "training_control.json")["type"] == "pause"
    view._on_native_event("pause", {})
    assert "持续看不到你" in read(bridge, "training_speech.json")["text"]


def test_next_action_really_skips_action_and_previous_returns(training):
    view, bridge = training
    view._on_native_event("begin", {})
    view._on_native_event("voice_continue", {})
    assert view._action_name == "深蹲"
    view._on_native_event("action_next", {})
    assert view._action_name == "拉伸"
    view._on_native_event("action_prev", {})
    assert view._action_name == "深蹲"


def test_paused_rest_does_not_count_down(training, monkeypatch):
    view, _ = training
    view._phase = "paused"
    view._resting = True
    view._rest_left = 20
    monkeypatch.setattr(view, "_schedule_rest_tick", lambda: None)
    view._on_rest_tick()
    assert view._rest_left == 20
