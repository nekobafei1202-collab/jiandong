"""Golden scoring tests mirroring D:/app/test/more_action_scoring_test.dart.

Expected values are derived from the Dart evaluator formulas with default
configs, so a faithful Python port must reproduce them exactly.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from jiandong_ai.ai.action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    SquatMachineState,
)
from jiandong_ai.ai.evaluation.glute_bridge_evaluator import GluteBridgeEvaluator
from jiandong_ai.ai.evaluation.high_knees_evaluator import HighKneesEvaluator
from jiandong_ai.ai.pose.pose_result import PoseResult

T0 = datetime(2026, 3, 1)


def _at(time: datetime) -> PoseResult:
    return PoseResult.empty(timestamp=time)


def _frame(
    *,
    state: SquatMachineState,
    done: bool = False,
    knee: float | None = None,
    body_line: float | None = None,
    leg: float | None = None,
    arm: float | None = None,
    cue: str | None = None,
) -> ActionRecognitionResult:
    return ActionRecognitionResult(
        phase=ActionPhase.completed_rep if done else ActionPhase.standing,
        machine_state=state,
        rep_count=1 if done else 0,
        knee_angle=knee,
        rep_max_knee_angle=knee,
        just_completed_rep=done,
        has_reliable_pose=True,
        body_line_angle=body_line,
        leg_spread_ratio=leg,
        arm_raise_ratio=arm,
        form_cue=cue,
    )


def test_glute_bridge_evaluator_penalizes_lumbar_hyperextension():
    evaluator = GluteBridgeEvaluator()
    modest = evaluator.evaluate(
        action=_frame(state=SquatMachineState.standing, done=True, knee=170),
        pose=_at(T0),
    )
    evaluator.reset()
    over = evaluator.evaluate(
        action=_frame(state=SquatMachineState.standing, done=True, knee=192),
        pose=_at(T0),
    )
    assert over.score < modest.score
    assert over.feedback == "不要用腰过度顶起"
    assert over.is_correct is False
    assert modest.feedback != "不要用腰过度顶起"

    # Dart formulas with default config:
    # peak 170 → amplitude 70 + (170-150)/(175-150)*30 = 94
    # peak 192 → amplitude 100 - (192-185)/(195-185)*75 = 48 (round of 47.5)
    # no samples → stability 80; no start time → rhythm 70
    assert modest.amplitude_score == 94
    assert modest.stability_score == 80
    assert modest.rhythm_score == 70
    assert modest.score == round(94 * 0.4 + 80 * 0.3 + 70 * 0.3)  # 83
    assert over.amplitude_score == 48
    assert over.score == round(48 * 0.4 + 80 * 0.3 + 70 * 0.3)  # 64


def test_glute_bridge_evaluator_scores_standard_rep_high():
    evaluator = GluteBridgeEvaluator()
    result = evaluator.evaluate(
        action=_frame(state=SquatMachineState.standing, done=True, knee=180),
        pose=_at(T0),
    )
    # 180° is between idealTop 175 and maxHealthy 185 → amplitude 100
    assert result.amplitude_score == 100
    assert result.score == round(100 * 0.4 + 80 * 0.3 + 70 * 0.3)  # 85
    assert result.is_correct is True
    assert result.feedback == "动作标准"

    # Below the count threshold the amplitude lands in the 20..50 band.
    evaluator.reset()
    low = evaluator.evaluate(
        action=_frame(state=SquatMachineState.standing, done=True, knee=120),
        pose=_at(T0),
    )
    # 120 < minCount 150 → 20 + (120/150)*30 = 44
    assert low.amplitude_score == 44
    assert low.is_correct is False
    assert low.feedback == "再把髋部顶高一点"


def test_high_knees_evaluator_asks_for_more_height_when_knee_stays_low():
    evaluator = HighKneesEvaluator()
    start = T0
    evaluator.evaluate(
        action=_frame(state=SquatMachineState.bottom, knee=30, body_line=180),
        pose=_at(start),
    )
    low = evaluator.evaluate(
        action=_frame(
            state=SquatMachineState.standing, done=True, knee=30, body_line=180
        ),
        pose=_at(start + timedelta(milliseconds=500)),
    )
    assert low.feedback == "膝盖再抬高一些"
    assert low.is_correct is False
    # lift 0.30 → height 20 + (0.30-0.18)/(0.55-0.18)*80 = 46
    # bodyLine 180 → posture 100; 500ms → rhythm 100 - |500-550|/550*40 = 96
    assert low.amplitude_score == 46
    assert low.stability_score == 100
    assert low.rhythm_score == 96
    assert low.score == round(46 * 0.45 + 100 * 0.30 + 96 * 0.25)  # 75

    evaluator.reset()
    evaluator.evaluate(
        action=_frame(state=SquatMachineState.bottom, knee=58, body_line=178),
        pose=_at(start),
    )
    high = evaluator.evaluate(
        action=_frame(
            state=SquatMachineState.standing, done=True, knee=58, body_line=178
        ),
        pose=_at(start + timedelta(milliseconds=550)),
    )
    assert high.score > low.score
    assert high.feedback == "动作标准"
    assert high.is_correct is True
    # lift 0.58 ≥ ideal 0.55 → height 100; dev 2° → posture 100; 550ms → 100
    assert high.amplitude_score == 100
    assert high.rhythm_score == 100
    assert high.score == 100


def _score_rep_with_duration(evaluator: HighKneesEvaluator, duration_ms: int):
    evaluator.evaluate(
        action=_frame(state=SquatMachineState.bottom, knee=58, body_line=178),
        pose=_at(T0),
    )
    return evaluator.evaluate(
        action=_frame(
            state=SquatMachineState.standing, done=True, knee=58, body_line=178
        ),
        pose=_at(T0 + timedelta(milliseconds=duration_ms)),
    )


def test_high_knees_evaluator_rhythm_three_segments():
    evaluator = HighKneesEvaluator()

    # Too fast: 100ms < min 250 → 40 + (100/250)*40 = 56
    fast = _score_rep_with_duration(evaluator, 100)
    assert fast.rhythm_score == 56

    # Ideal: 550ms → dist 0 → 100
    evaluator.reset()
    ideal = _score_rep_with_duration(evaluator, 550)
    assert ideal.rhythm_score == 100

    # Slow but in range: 1000ms → 100 - (|1000-550|/550)*40 = 67
    evaluator.reset()
    slow = _score_rep_with_duration(evaluator, 1000)
    assert slow.rhythm_score == 67

    # Too slow: 2000ms > max 1500 → 85 - ((2000-1500)/550)*35 = 53
    evaluator.reset()
    dragging = _score_rep_with_duration(evaluator, 2000)
    assert dragging.rhythm_score == 53


def test_high_knees_evaluator_height_piecewise_bounds():
    evaluator = HighKneesEvaluator()

    # Lift at/below idle floor → height floor of 20 (isCorrect gate fails too)
    evaluator.evaluate(
        action=_frame(state=SquatMachineState.bottom, knee=10, body_line=180),
        pose=_at(T0),
    )
    floored = evaluator.evaluate(
        action=_frame(
            state=SquatMachineState.standing, done=True, knee=10, body_line=180
        ),
        pose=_at(T0 + timedelta(milliseconds=550)),
    )
    assert floored.amplitude_score == 20
    assert floored.is_correct is False

    # Posture: mean bodyLine dev ≥ maxLean 30° → posture floor of 20
    evaluator.reset()
    evaluator.evaluate(
        action=_frame(state=SquatMachineState.bottom, knee=58, body_line=140),
        pose=_at(T0),
    )
    leaning = evaluator.evaluate(
        action=_frame(
            state=SquatMachineState.standing, done=True, knee=58, body_line=140
        ),
        pose=_at(T0 + timedelta(milliseconds=550)),
    )
    assert leaning.stability_score == 20
    assert leaning.feedback == "身体保持直立，不要后仰"
    # Dart gates isCorrect on score + highEnough only; 76 ≥ 70 still passes.
    assert leaning.score == round(100 * 0.45 + 20 * 0.30 + 100 * 0.25)  # 76
    assert leaning.is_correct is True
