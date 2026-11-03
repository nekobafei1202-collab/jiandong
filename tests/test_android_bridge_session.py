from __future__ import annotations

import json
import time

from jiandong_ai.ai.session.android_bridge_session import (
    AndroidBridgePoseSession,
    write_voice_flag,
)


def test_write_voice_flag(tmp_path) -> None:
    flag = tmp_path / "voice_enabled.flag"
    assert write_voice_flag(True, bridge_dir=tmp_path) == flag
    assert flag.read_text(encoding="utf-8") == "1"
    # 重复开启幂等
    write_voice_flag(True, bridge_dir=tmp_path)
    assert flag.exists()
    assert write_voice_flag(False, bridge_dir=tmp_path) == flag
    assert not flag.exists()
    # 关闭状态重复删除不报错
    write_voice_flag(False, bridge_dir=tmp_path)
    assert not flag.exists()


def _wait_until(predicate, timeout: float = 1.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not met before timeout")


def test_pose_only_bridge_and_native_events(tmp_path) -> None:
    session = AndroidBridgePoseSession(bridge_dir=tmp_path, max_infer_fps=60)
    poses = []
    events = []
    session.configure(action_name="深蹲")
    session.set_listener(lambda frame, pose: poses.append((frame, pose)))
    session.set_event_listener(lambda event, payload: events.append((event, payload)))

    assert session.start()
    assert (tmp_path / "cmd.txt").read_text(encoding="utf-8") == "preview_front\t深蹲"

    (tmp_path / "pose.json").write_text(
        json.dumps(
            {
                "frameId": 1,
                "imageWidth": 0,
                "imageHeight": 0,
                "isFrontCamera": True,
                "keypoints": [
                    {"name": "nose", "x": 0.5, "y": 0.2, "confidence": 0.9},
                    {"name": "leftShoulder", "x": 0.4, "y": 0.4, "confidence": 0.9},
                    {"name": "rightShoulder", "x": 0.6, "y": 0.4, "confidence": 0.9},
                    {"name": "leftHip", "x": 0.45, "y": 0.65, "confidence": 0.9},
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "event.json").write_text(
        json.dumps({"seq": 1, "type": "pause"}),
        encoding="utf-8",
    )
    _wait_until(lambda: len(poses) == 1 and len(events) == 1)

    assert poses[0][0] is None
    assert poses[0][1].has_person
    assert events[0][0] == "pause"

    session.publish_hud(reps=3, score=88, title="很好", subtitle="保持", unit="次")
    hud = json.loads((tmp_path / "hud.json").read_text(encoding="utf-8"))
    assert hud["reps"] == 3
    assert hud["score"] == 88

    session.publish_hud(
        reps=0,
        score=0,
        title="组间休息",
        subtitle="45",
        resting=True,
        rest_seconds=45,
        rest_label="组间休息",
        next_label="跳过休息",
        set_nav=True,
        set_nav_prev=False,
        set_nav_next=True,
        guide_only=True,
    )
    rest_hud = json.loads((tmp_path / "hud.json").read_text(encoding="utf-8"))
    assert rest_hud["resting"] is True
    assert rest_hud["restSeconds"] == 45
    assert rest_hud["restLabel"] == "组间休息"
    assert rest_hud["nextLabel"] == "跳过休息"

    session.stop()
