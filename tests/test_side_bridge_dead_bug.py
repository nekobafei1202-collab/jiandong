"""Side bridge (侧桥) / dead bug (死虫式) hold timers + ExerciseKind wiring.

侧桥：身体线（肩-髋-踝带符号角度）在 150~210° 宽松范围内累计计时；
姿势崩（如下沉到 120°）暂停计时并提示"髋部不要下沉"。
死虫式：肩+髋+至少一侧手腕/脚踝可见即计时，缺关键点暂停。
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from jiandong_ai.ai.action.dead_bug_recognizer import DeadBugRecognizer
from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.ai.action.side_bridge_recognizer import SideBridgeRecognizer
from jiandong_ai.ai.pose.keypoint import Keypoint, KeypointName
from jiandong_ai.ai.pose.pose_result import PoseResult

T0 = datetime(2026, 1, 1)


def _side_bridge_pose(hip_drop: float, timestamp: datetime) -> PoseResult:
    """Side-lying pose: shoulder (0.3,0.4), ankle (0.7,0.4), hip (0.5, 0.4+drop).

    hip_drop=0 → 身体成线（带符号角度 180°）；drop≈0.1155 → 下沉到 120°。
    """
    def kp(name: KeypointName, x: float, y: float, confidence: float = 0.95) -> Keypoint:
        return Keypoint(name=name, x=x, y=y, confidence=confidence)

    return PoseResult.from_keypoints(
        [
            kp(KeypointName.leftShoulder, 0.3, 0.4),
            kp(KeypointName.leftHip, 0.5, 0.4 + hip_drop),
            kp(KeypointName.leftAnkle, 0.7, 0.4),
        ],
        timestamp=timestamp,
    )


def _dead_bug_pose(timestamp: datetime, *, with_limbs: bool = True) -> PoseResult:
    def kp(name: KeypointName, x: float, y: float, confidence: float = 0.95) -> Keypoint:
        return Keypoint(name=name, x=x, y=y, confidence=confidence)

    points = [
        kp(KeypointName.leftShoulder, 0.3, 0.5),
        kp(KeypointName.leftHip, 0.6, 0.5),
    ]
    if with_limbs:
        points.append(kp(KeypointName.leftWrist, 0.3, 0.3))
        points.append(kp(KeypointName.leftAnkle, 0.8, 0.4))
    return PoseResult.from_keypoints(points, timestamp=timestamp)


def test_side_bridge_accumulates_hold_time_when_straight():
    recognizer = SideBridgeRecognizer()
    result = None
    for i in range(10):
        result = recognizer.recognize(
            _side_bridge_pose(0.0, T0 + timedelta(milliseconds=100 * i))
        )
    assert result is not None
    assert result.has_reliable_pose
    assert result.machine_state.name == "standing"
    assert recognizer.current_hold_ms >= 800
    assert result.form_cue is None


def test_side_bridge_pauses_when_hips_sag():
    recognizer = SideBridgeRecognizer()
    for i in range(6):
        recognizer.recognize(
            _side_bridge_pose(0.0, T0 + timedelta(milliseconds=100 * i))
        )
    assert recognizer.current_hold_ms > 0

    result = None
    for i in range(6, 12):
        result = recognizer.recognize(
            # 髋部下沉：signed body line ≈ 120°，低于 150° 下限。
            _side_bridge_pose(0.1155, T0 + timedelta(milliseconds=100 * i))
        )
    assert result is not None
    assert recognizer.current_hold_ms == 0
    assert result.form_cue == "髋部不要下沉"

    # 姿势恢复后重新计时。
    for i in range(12, 18):
        result = recognizer.recognize(
            _side_bridge_pose(0.0, T0 + timedelta(milliseconds=100 * i))
        )
    assert result is not None
    assert recognizer.current_hold_ms > 0
    assert result.form_cue is None


def test_dead_bug_times_when_visible():
    recognizer = DeadBugRecognizer()
    result = None
    for i in range(10):
        result = recognizer.recognize(
            _dead_bug_pose(T0 + timedelta(milliseconds=100 * i))
        )
    assert result is not None
    assert result.has_reliable_pose
    assert recognizer.current_hold_ms >= 800


def test_dead_bug_pauses_when_limbs_missing():
    recognizer = DeadBugRecognizer()
    for i in range(5):
        recognizer.recognize(
            _dead_bug_pose(T0 + timedelta(milliseconds=100 * i))
        )
    assert recognizer.current_hold_ms > 0

    result = None
    for i in range(5, 10):
        result = recognizer.recognize(
            _dead_bug_pose(
                T0 + timedelta(milliseconds=100 * i), with_limbs=False
            )
        )
    assert result is not None
    assert not result.has_reliable_pose
    assert recognizer.current_hold_ms == 0
    assert result.form_cue is not None


def test_exercise_kind_new_actions():
    assert ExerciseKind.supports_auto_detect("卷腹")
    assert ExerciseKind.supports_auto_detect("crunch")
    assert ExerciseKind.supports_auto_detect("侧桥")
    assert ExerciseKind.supports_auto_detect("side_plank")
    assert ExerciseKind.supports_auto_detect("死虫式")
    assert ExerciseKind.supports_auto_detect("deadbug")
    assert not ExerciseKind.is_manual_complete("侧桥")
    assert not ExerciseKind.is_manual_complete("死虫式")

    assert ExerciseKind.normalize("卷腹") == ExerciseKind.crunch
    assert ExerciseKind.normalize("侧平板") == ExerciseKind.side_bridge
    assert ExerciseKind.normalize("dead_bug") == ExerciseKind.dead_bug
    assert ExerciseKind.display_name("side_bridge") == "侧桥"
    assert ExerciseKind.display_name("死虫式") == "死虫式"

    assert ExerciseKind.rest_seconds("侧桥") == 45
    assert ExerciseKind.rest_seconds("死虫式") == 30
    assert ExerciseKind.rest_seconds("卷腹") == 60


def test_muscle_map_new_actions():
    from jiandong_ai.widgets.muscle_map import activation_for_actions

    side = activation_for_actions(["侧桥"])
    assert side["OBLIQUES"] == 3 and side["CORE"] == 3
    bug = activation_for_actions(["死虫式"])
    assert bug["CORE"] == 3 and bug["SHOULDERS_FRONT"] == 1
