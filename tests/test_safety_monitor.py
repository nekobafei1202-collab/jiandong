from __future__ import annotations

from jiandong_ai.ai.pose.keypoint import Keypoint, KeypointName
from jiandong_ai.ai.pose.pose_result import PoseResult
from jiandong_ai.ai.safety_monitor import SafetyMonitor


def _pose(
    *,
    head: bool = True,
    feet: bool = True,
    shoulder_l: float = 0.4,
    shoulder_r: float = 0.6,
    conf: float = 0.9,
) -> PoseResult:
    points = [
        Keypoint(KeypointName.leftShoulder, shoulder_l, 0.3, conf),
        Keypoint(KeypointName.rightShoulder, shoulder_r, 0.3, conf),
        Keypoint(KeypointName.leftHip, 0.45, 0.6, conf),
        Keypoint(KeypointName.rightHip, 0.55, 0.6, conf),
    ]
    if head:
        points.append(Keypoint(KeypointName.nose, 0.5, 0.1, conf))
    if feet:
        points.append(Keypoint(KeypointName.leftAnkle, 0.45, 0.95, conf))
        points.append(Keypoint(KeypointName.rightAnkle, 0.55, 0.95, conf))
    return PoseResult.from_keypoints(points)


def test_framing_no_person_fallback():
    monitor = SafetyMonitor()
    text = monitor.framing_check(PoseResult.empty(), now=0.0)
    assert "检测不到你" in text


def test_framing_timeout_hint():
    monitor = SafetyMonitor(framing_timeout=10.0)
    monitor.framing_check(PoseResult.empty(), now=0.0)
    text = monitor.framing_check(PoseResult.empty(), now=11.0)
    assert "身边的人" in text
    # 超时提示只播一次。
    assert monitor.framing_check(PoseResult.empty(), now=12.0) == "检测不到你，请站到手机正前方。"


def test_framing_missing_feet():
    monitor = SafetyMonitor()
    text = monitor.framing_check(_pose(feet=False), now=0.0)
    assert "脚部" in text


def test_framing_missing_head():
    monitor = SafetyMonitor()
    text = monitor.framing_check(_pose(head=False), now=0.0)
    assert "头部" in text


def test_framing_too_close():
    monitor = SafetyMonitor()
    text = monitor.framing_check(_pose(shoulder_l=0.1, shoulder_r=0.9), now=0.0)
    assert "后退" in text


def test_framing_passes_after_n_frames():
    monitor = SafetyMonitor(pass_frames=3)
    assert monitor.framing_check(_pose(), now=0.0) is None
    assert monitor.framing_check(_pose(), now=0.1) is None
    text = monitor.framing_check(_pose(), now=0.2)
    assert "位置很好" in text
    assert monitor.framing_passed
    # 通过后不再重复播报。
    assert monitor.framing_check(_pose(), now=0.3) is None


def test_framing_counter_resets_on_bad_frame():
    monitor = SafetyMonitor(pass_frames=3)
    monitor.framing_check(_pose(), now=0.0)
    monitor.framing_check(_pose(), now=0.1)
    monitor.framing_check(_pose(feet=False), now=0.2)  # 中断
    assert monitor.framing_check(_pose(), now=0.3) is None
    assert not monitor.framing_passed


def test_safety_edge_warning_and_cooldown():
    monitor = SafetyMonitor(cooldown_seconds=5.0)
    # 中心点移到左边缘（肩 0.02/0.22 → 中心 0.12，边界阈值内）。
    warn = monitor.safety_check(_pose(shoulder_l=0.02, shoulder_r=0.22), now=100.0)
    # 首帧无位移参考，先落一帧。
    if warn is None:
        warn = monitor.safety_check(_pose(shoulder_l=0.01, shoulder_r=0.21), now=100.1)
    assert "中间" in warn
    # 冷却期内同类警告不重复。
    again = monitor.safety_check(_pose(shoulder_l=0.02, shoulder_r=0.22), now=100.2)
    assert again is None
    # 冷却后恢复。
    later = monitor.safety_check(_pose(shoulder_l=0.01, shoulder_r=0.21), now=106.0)
    assert later is not None and "中间" in later


def test_safety_close_warning():
    monitor = SafetyMonitor()
    monitor.safety_check(_pose(), now=0.0)
    warn = monitor.safety_check(_pose(shoulder_l=0.1, shoulder_r=0.9), now=1.0)
    assert "太近" in warn


def test_safety_jump_warning():
    monitor = SafetyMonitor()
    monitor.safety_check(_pose(), now=0.0)
    warn = monitor.safety_check(_pose(shoulder_l=0.78, shoulder_r=0.98), now=0.2)
    assert "你还好吗" in warn


def test_safety_normal_pose_silent():
    monitor = SafetyMonitor()
    monitor.safety_check(_pose(), now=0.0)
    assert monitor.safety_check(_pose(), now=0.1) is None
    # 无人物不报警。
    assert monitor.safety_check(PoseResult.empty(), now=0.2) is None
