"""轻松模式计数修复的行为锁定（真实视频诊断驱动，见
jiandong_ai/scripts/diagnose_pushup_count.py）：

1. 快节奏俯卧撑（~1.2s/次，模拟 12fps 桥）：旧的 confirm_frames=3 结构性
   超时计不上，修复后的 lenient() 默认配置能逐次计上。
2. 肩线滞回兜底：侧拍/半侧拍把 2D 肘角压扁（全周期 178→144°），肘角
   状态机永远不离开 standing；肩点 y 的滞回往复作为替代深度信号计数。
3. 兜底只在肘角状态机未介入时计数，正常俯卧撑不会重复计。
4. 严格模式行为不变。
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

# lenient() 现在自带 confirm_frames=1 / min_state_duration=0；
# 测试帧瞬间到达，需关掉基于墙钟的最小计数间隔。
LENIENT = replace(PushupConfig.lenient(), min_rep_interval_ms=0)
LENIENT_OLD_TIMING = replace(
    PushupConfig.lenient(),
    state_confirm_frames=3,
    min_state_duration_ms=0,
    min_rep_interval_ms=0,
)
STRICT_FAST = replace(
    PushupConfig(),
    state_confirm_frames=1,
    min_state_duration_ms=0,
    min_rep_interval_ms=0,
)


def _pose(
    elbow_angle: float,
    timestamp: datetime,
    *,
    y_offset: float = 0.0,
    hip_confidence: float = 0.0,
) -> PoseResult:
    rad = math.radians(elbow_angle)

    def kp(
        name: KeypointName, x: float, y: float, confidence: float = 0.95
    ) -> Keypoint:
        return Keypoint(name=name, x=x, y=y + y_offset, confidence=confidence)

    return PoseResult.from_keypoints(
        [
            kp(KeypointName.leftShoulder, 0.3, 0.5),
            kp(KeypointName.leftElbow, 0.5, 0.5),
            kp(
                KeypointName.leftWrist,
                0.5 - 0.2 * math.cos(rad),
                0.5 - 0.2 * math.sin(rad),
            ),
            kp(KeypointName.leftHip, 0.6, 0.5, confidence=hip_confidence),
            kp(KeypointName.leftAnkle, 0.8, 0.5, confidence=hip_confidence),
            kp(KeypointName.nose, 0.22, 0.5),
        ],
        timestamp=timestamp,
    )


def _run(config: PushupConfig, frames: list[tuple[float, float]]):
    recognizer = PushupRecognizer(config=config)
    result = None
    for i, (angle, y_offset) in enumerate(frames):
        result = recognizer.recognize(
            _pose(angle, T0 + timedelta(milliseconds=83 * i), y_offset=y_offset)
        )
    assert result is not None
    return result


# 快节奏标准俯卧撑：1 次 12 帧（12fps 下 ~1 秒），高位只停 2 帧，
# 底部保持 2-3 帧（与真实 12fps 视频一致，中值平滑需要底部有保持）。
FAST_REP = [170, 170, 150, 130, 110, 98, 100, 110, 130, 155, 170, 170]


def _flat(angles: list[float]) -> list[tuple[float, float]]:
    return [(a, 0.0) for a in angles]


def test_lenient_counts_fast_tempo_reps():
    result = _run(LENIENT, _flat(FAST_REP * 3))
    assert result.rep_count == 3


def test_old_confirm_timing_misses_fast_tempo_reps():
    # 修复前的确认节奏：每个相位只有 1-2 帧，迁移永远确认不上。
    result = _run(LENIENT_OLD_TIMING, _flat(FAST_REP * 3))
    assert result.rep_count == 0


# 肘角被拍摄角度压扁的俯卧撑：肘角全程 ≥150°（状态机离不开 standing），
# 但肩点 y 随身体起伏 ~0.10（归一化）。
FORESHORTENED_REP = [
    (160, 0.0),
    (160, 0.0),
    (158, 0.03),
    (155, 0.06),
    (152, 0.09),
    (150, 0.10),
    (150, 0.10),
    (153, 0.07),
    (156, 0.04),
    (159, 0.01),
    (160, 0.0),
    (160, 0.0),
]


def test_lenient_shoulder_fallback_counts_foreshortened_reps():
    result = _run(LENIENT, FORESHORTENED_REP * 3)
    assert result.rep_count == 3


def test_shoulder_fallback_ignores_small_bobbing():
    bobbing = [(160, dy) for dy in [0.0, 0.03, 0.0, 0.03, 0.0, 0.03, 0.0]]
    result = _run(LENIENT, bobbing)
    assert result.rep_count == 0


def test_shoulder_fallback_does_not_double_count_normal_reps():
    # 正常俯卧撑：肘角状态机已计数，肩线兜底不得再计一次。
    frames = [
        (a, dy)
        for a, dy in zip(
            FAST_REP * 2,
            [0.0, 0.0, 0.03, 0.05, 0.08, 0.1, 0.09, 0.06, 0.03, 0.01, 0.0, 0.0] * 2,
        )
    ]
    result = _run(LENIENT, frames)
    assert result.rep_count == 2


def test_strict_ignores_shoulder_only_movement():
    result = _run(STRICT_FAST, FORESHORTENED_REP * 3, )
    assert result.rep_count == 0
