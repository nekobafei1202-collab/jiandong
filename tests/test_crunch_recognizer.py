"""Crunch (卷腹) recognizer: torso-flexion state machine on synthetic angles.

信号是肩-髋-膝夹角：躺平 ~160°，标准卷腹触底 ~110°（约 45° 屈曲）。
合成帧序列验证：完整卷起计上数；卷起不足不计；小幅微动不计。
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from jiandong_ai.ai.action.crunch_config import CrunchConfig
from jiandong_ai.ai.action.crunch_recognizer import CrunchRecognizer
from jiandong_ai.ai.pose.keypoint import Keypoint, KeypointName
from jiandong_ai.ai.pose.pose_result import PoseResult

T0 = datetime(2026, 1, 1)


def _crunch_pose(torso_angle: float, timestamp: datetime) -> PoseResult:
    """Side-view supine pose whose shoulder→hip→knee angle matches.

    Hip at (0.5, 0.5), knee to the right; shoulder sweeps from lying flat
    (left of hip, ~160°) toward a standard crunch (~110°) as the torso curls.
    """
    rad = math.radians(torso_angle)

    def kp(name: KeypointName, x: float, y: float, confidence: float = 0.95) -> Keypoint:
        return Keypoint(name=name, x=x, y=y, confidence=confidence)

    return PoseResult.from_keypoints(
        [
            kp(
                KeypointName.leftShoulder,
                0.5 + 0.25 * math.cos(rad),
                0.5 - 0.25 * math.sin(rad),
            ),
            kp(KeypointName.leftHip, 0.5, 0.5),
            kp(KeypointName.leftKnee, 0.7, 0.5),
        ],
        timestamp=timestamp,
    )


def _run(angles: list[float], config: CrunchConfig | None = None):
    recognizer = CrunchRecognizer(config=config)
    result = None
    for i, angle in enumerate(angles):
        result = recognizer.recognize(
            _crunch_pose(angle, T0 + timedelta(milliseconds=100 * i))
        )
    assert result is not None
    return result


# 一个完整卷腹周期，数值取实测轨迹形态（mixkit 4591 居家仰卧起坐）：
# 屈膝躺平基线只有 ~127°（不是理想的 160°），深深坐起到 ~45°。
FULL_REP = [127, 128, 124, 118, 110, 95, 60, 45, 50, 70, 95, 115, 125, 127]

# 大开角版本（腿伸直躺平 ~160°）也必须能计。
WIDE_REP = [160, 160, 150, 130, 110, 90, 78, 78, 90, 110, 130, 150, 160, 160]


def test_counts_full_reps():
    result = _run(FULL_REP * 3)
    assert result.rep_count == 3


def test_counts_wide_angle_reps():
    result = _run(WIDE_REP * 3)
    assert result.rep_count == 3


def test_shallow_curl_not_counted():
    # 只卷到 ~105°（未到 95° 触底阈值）：回到躺平时提示卷起高度不足，不计数。
    shallow = [127, 127, 118, 112, 107, 105, 107, 112, 120, 127, 127]
    result = _run(shallow)
    assert result.rep_count == 0
    assert result.form_cue == "卷起高度不足"


def test_jitter_not_counted():
    # 躺平基线附近小幅抖动（呼吸/手持）不得触发周期。
    jitter = [127, 124, 130, 125, 128, 124, 129, 126, 127]
    result = _run(jitter)
    assert result.rep_count == 0


def test_low_confidence_pose_rejected():
    recognizer = CrunchRecognizer()
    pose = PoseResult.from_keypoints(
        [
            Keypoint(name=KeypointName.leftShoulder, x=0.3, y=0.4, confidence=0.2),
            Keypoint(name=KeypointName.leftHip, x=0.5, y=0.5, confidence=0.2),
            Keypoint(name=KeypointName.leftKnee, x=0.7, y=0.5, confidence=0.2),
        ],
        timestamp=T0,
    )
    result = recognizer.recognize(pose)
    assert not result.has_reliable_pose
    assert result.form_cue is not None


def test_single_side_is_enough():
    # 只给一侧（左）关键点即可识别——右侧遮挡不应阻塞计数。
    result = _run(FULL_REP)
    assert result.rep_count == 1
