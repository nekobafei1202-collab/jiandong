"""Push-up strict / lenient mode behavior.

轻松模式（PushupConfig.lenient）：计数宽容——髋部不可见、浅深度（肘角 100°
触底）也能计数；乱动（肘角微幅变化）仍不计数。严格模式保持原有行为。
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timedelta

from jiandong_ai.ai.action.pushup_config import PushupConfig
from jiandong_ai.ai.action.pushup_recognizer import PushupRecognizer
from jiandong_ai.ai.pose.keypoint import Keypoint, KeypointName
from jiandong_ai.ai.pose.pose_result import PoseResult

T0 = datetime(2026, 1, 1)

LENIENT_FAST = replace(
    PushupConfig.lenient(),
    state_confirm_frames=1,
    min_state_duration_ms=0,
    min_rep_interval_ms=0,
)
STRICT_FAST = replace(
    PushupConfig(),
    state_confirm_frames=1,
    min_state_duration_ms=0,
    min_rep_interval_ms=0,
)


def _pushup_pose(
    elbow_angle: float,
    timestamp: datetime,
    *,
    hip_confidence: float = 0.0,
) -> PoseResult:
    """Side-ish push-up pose whose shoulder→elbow→wrist angle matches.

    Hips are present but unreliable by default (front camera / hips off-frame).
    """
    rad = math.radians(elbow_angle)

    def kp(name: KeypointName, x: float, y: float, confidence: float = 0.95) -> Keypoint:
        return Keypoint(name=name, x=x, y=y, confidence=confidence)

    return PoseResult.from_keypoints(
        [
            kp(KeypointName.leftShoulder, 0.3, 0.5),
            kp(KeypointName.leftElbow, 0.5, 0.5),
            kp(KeypointName.leftWrist, 0.5 - 0.2 * math.cos(rad), 0.5 - 0.2 * math.sin(rad)),
            kp(KeypointName.leftHip, 0.6, 0.5, confidence=hip_confidence),
            kp(KeypointName.leftAnkle, 0.8, 0.5, confidence=hip_confidence),
            kp(KeypointName.nose, 0.22, 0.5),
        ],
        timestamp=timestamp,
    )


# 一个浅俯卧撑周期：高位 170° → 下放到 100° 触底 → 推回高位。
# 末尾多保持两帧高位：轻松模式的 3 帧中值平滑有一帧滞后，
# 回到 lockout 需要多一帧才确认（真实视频中高位都会保持多帧）。
SHALLOW_REP = [170, 170, 170, 140, 120, 110, 100, 100, 115, 140, 165, 170, 170, 170]


def _run(config: PushupConfig, angles: list[float], *, hip_confidence: float = 0.0):
    recognizer = PushupRecognizer(config=config)
    result = None
    for i, angle in enumerate(angles):
        pose = _pushup_pose(
            angle, T0 + timedelta(milliseconds=120 * i), hip_confidence=hip_confidence
        )
        result = recognizer.recognize(pose)
    assert result is not None
    return result


def test_lenient_counts_shallow_rep_without_reliable_hips():
    result = _run(LENIENT_FAST, SHALLOW_REP)
    assert result.rep_count >= 1


def test_strict_rejects_same_sequence_when_hips_unreliable():
    result = _run(STRICT_FAST, SHALLOW_REP)
    assert result.rep_count == 0


def test_strict_rejects_shallow_depth_even_with_reliable_hips():
    result = _run(STRICT_FAST, SHALLOW_REP, hip_confidence=0.95)
    assert result.rep_count == 0


def test_lenient_does_not_count_jitter():
    # 肘角只在 170↔160 微动：ROM 不足，轻松模式也不应误计。
    jitter = [170, 160, 170, 160, 170, 160, 170, 160, 170]
    result = _run(LENIENT_FAST, jitter)
    assert result.rep_count == 0


def test_lenient_config_fields():
    config = PushupConfig.lenient()
    assert config.strict is False
    assert config.bottom_elbow_angle == 105
    assert config.minimum_confidence == 0.3
    assert config.min_effective_range_of_motion == 45
    # 12fps 桥下每次迁移 ~370ms 的确认开销是快速俯卧撑计不上的根因。
    assert config.state_confirm_frames == 1
    assert config.min_state_duration_ms == 0
    assert PushupConfig().strict is True
    assert PushupConfig().state_confirm_frames == 3
