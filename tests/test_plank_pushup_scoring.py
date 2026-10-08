"""Spot-check numeric parity for plank and push-up evaluators.

Mirrors the scenarios in D:/app/test/plank_recognizer_test.dart and
D:/app/test/pushup_evaluator_test.dart.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from jiandong_ai.ai.action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    SquatMachineState,
)
from jiandong_ai.ai.action.plank_config import PlankConfig
from jiandong_ai.ai.action.plank_recognizer import PlankRecognizer
from jiandong_ai.ai.evaluation.plank_evaluator import PlankEvaluator
from jiandong_ai.ai.evaluation.pushup_evaluator import PushupEvaluator
from jiandong_ai.ai.pose.keypoint import Keypoint, KeypointName
from jiandong_ai.ai.pose.pose_result import PoseResult

T0 = datetime(2026, 1, 1)

FAST_PLANK = PlankConfig(
    state_confirm_frames=1,
    min_state_duration_ms=0,
    min_rep_interval_ms=0,
)


def _plank_pose(
    signed_angle: float, timestamp: datetime, confidence: float = 0.95
) -> PoseResult:
    """Side-view plank pose whose signed shoulder→hip→ankle angle matches.

    ≤180° = 塌腰 side (hip below the line), >180° = 翘臀 side.
    """
    interior = signed_angle if signed_angle <= 180 else 360 - signed_angle
    half_rad = math.radians(interior / 2)
    d = 0.2 / math.tan(half_rad)
    hip_y = 0.5 + d if signed_angle <= 180 else 0.5 - d

    def kp(name: KeypointName, x: float, y: float) -> Keypoint:
        return Keypoint(name=name, x=x, y=y, confidence=confidence)

    return PoseResult.from_keypoints(
        [
            kp(KeypointName.leftShoulder, 0.3, 0.5),
            kp(KeypointName.leftHip, 0.5, hip_y),
            kp(KeypointName.leftAnkle, 0.7, 0.5),
            kp(KeypointName.nose, 0.22, 0.5),
        ],
        timestamp=timestamp,
    )


def _run_plank_session(signed_angle: float):
    recognizer = PlankRecognizer(config=FAST_PLANK)
    evaluator = PlankEvaluator()
    result = None
    for i in range(21):
        pose = _plank_pose(signed_angle, T0 + timedelta(seconds=i))
        action = recognizer.recognize(pose)
        result = evaluator.evaluate(action=action, pose=pose)
    return result


def test_plank_evaluator_scores_good_session_far_above_sagging():
    good = _run_plank_session(178)
    bad = _run_plank_session(150)

    # Good hold every frame → ratio 100, no sway → stability 100 → score 100.
    assert good.score >= 85
    assert good.feedback == "姿势良好"
    assert good.is_correct is True

    # Never in the good range → ratio 0; steady line → stability 100;
    # score = round(0*0.7 + 100*0.3) = 30.
    assert bad.score <= 45
    assert bad.feedback == "塌腰"
    assert bad.is_correct is False

    assert good.score - bad.score >= 40


def _pushup_action(
    *,
    phase: ActionPhase,
    machine_state: SquatMachineState,
    elbow: float | None,
    rep_count: int = 0,
    done: bool = False,
) -> ActionRecognitionResult:
    return ActionRecognitionResult(
        phase=phase,
        machine_state=machine_state,
        rep_count=rep_count,
        knee_angle=elbow,
        elbow_angle=elbow,
        just_completed_rep=done,
        has_reliable_pose=True,
    )


def _run_pushup(bottom: float):
    evaluator = PushupEvaluator()
    evaluator.evaluate(
        action=_pushup_action(
            phase=ActionPhase.standing,
            machine_state=SquatMachineState.standing,
            elbow=175,
        ),
        pose=PoseResult.empty(),
    )
    evaluator.evaluate(
        action=_pushup_action(
            phase=ActionPhase.squatting,
            machine_state=SquatMachineState.down,
            elbow=bottom,
        ),
        pose=PoseResult.empty(),
    )
    return evaluator.evaluate(
        action=_pushup_action(
            phase=ActionPhase.completed_rep,
            machine_state=SquatMachineState.standing,
            elbow=175,
            rep_count=1,
            done=True,
        ),
        pose=PoseResult.empty(),
    )


def test_pushup_deep_rep_scores_higher_amplitude_than_shallow():
    deep = _run_pushup(bottom=78)
    shallow = _run_pushup(bottom=130)

    # Deep: min 78 ≤ bottom 90 → depth 100; rom 97 ≥ 70 → rom 100 → 100.
    assert deep.amplitude_score == 100
    # Shallow: depth round(20 + (165-130)/(165-90)*80) = 57;
    # rom 45 → round(20 + 45/70*80) = 71; total round(57*.55 + 71*.45) = 63.
    assert shallow.amplitude_score == 63
    assert deep.amplitude_score > shallow.amplitude_score
