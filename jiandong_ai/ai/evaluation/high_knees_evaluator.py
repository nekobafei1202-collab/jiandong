"""High-knees quality scoring (height / posture / rhythm).

Mirrors lib/ai/evaluation/high_knees_evaluator.dart formula by formula:
height piecewise floored at idleKneeLiftRatio (20..100), posture floored
at 20, three-segment rhythm, highEnough gate and feedback copy.
"""

from __future__ import annotations

import math
from datetime import datetime

from ..action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    SquatMachineState,
)
from ..action.high_knees_config import HighKneesConfig
from ..action.squat_config import SquatConfig
from ..pose.pose_result import PoseResult
from .action_evaluator import ActionEvaluator, EvaluationResult
from .personal_baseline import PersonalBaseline


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> int:
    # Dart's num.round() rounds half away from zero.
    return int(math.floor(v + 0.5)) if v >= 0 else -int(math.floor(-v + 0.5))


class HighKneesEvaluator(ActionEvaluator):
    def __init__(self, config: HighKneesConfig | None = None) -> None:
        self._config = config or HighKneesConfig.defaults
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._step_started_at: datetime | None = None
        self._max_lift = 0.0
        self._body_lines: list[float] = []

    def reset(self) -> None:
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._clear_step()

    def evaluate(
        self,
        *,
        action: ActionRecognitionResult,
        pose: PoseResult,
        baseline: PersonalBaseline | None = None,
        config: SquatConfig | None = None,
    ) -> EvaluationResult:
        if action.phase == ActionPhase.no_person or not action.has_reliable_pose:
            self._step_started_at = None
            return self._hold(feedback="请调整位置，确保全身进入摄像头")

        lifting = action.machine_state in (
            SquatMachineState.bottom,
            SquatMachineState.up,
        )
        if lifting and self._step_started_at is None:
            self._step_started_at = pose.timestamp
            self._max_lift = 0
            self._body_lines.clear()

        lift = self._lift_of(action)
        if lift is not None and lifting:
            self._max_lift = max(self._max_lift, lift)
        line = action.body_line_angle
        if line is not None and lifting:
            self._body_lines.append(line)

        if not action.just_completed_rep:
            if action.machine_state == SquatMachineState.standing:
                self._clear_step()
            return self._hold(feedback=self._live(action, lift))

        peak = max(self._max_lift, lift or 0)
        height = self._score_height(peak)
        posture = self._score_posture(action.body_line_angle)
        duration = self._elapsed(pose.timestamp)
        rhythm = self._score_rhythm(duration)
        score = _round(
            _clamp(
                height * self._config.height_score_weight
                + posture * self._config.posture_score_weight
                + rhythm * self._config.rhythm_score_weight,
                0,
                100,
            )
        )
        high_enough = peak >= self._config.high_knee_lift_ratio

        self._last = EvaluationResult(
            score=score,
            amplitude_score=height,
            stability_score=posture,
            rhythm_score=rhythm,
            feedback=self._feedback(
                score=score,
                height=height,
                posture=posture,
                rhythm=rhythm,
                high_enough=high_enough,
            ),
            is_correct=score >= self._config.correct_score_threshold and high_enough,
            knee_angle_min=action.rep_min_knee_angle,
            knee_angle_max=peak * 100,
            range_of_motion=action.range_of_motion,
            movement_duration_ms=duration,
        )
        self._clear_step()
        return self._last

    def _lift_of(self, action: ActionRecognitionResult) -> float | None:
        raw = (
            action.rep_max_knee_angle
            if action.rep_max_knee_angle is not None
            else action.knee_angle
        )
        if raw is None:
            return None
        return raw / 100

    def _elapsed(self, now: datetime) -> int:
        start = self._step_started_at
        if start is None:
            return 0
        return max(0, int((now - start).total_seconds() * 1000))

    def _score_height(self, lift: float) -> int:
        ideal = self._config.ideal_knee_lift_ratio
        floor = self._config.idle_knee_lift_ratio
        if lift >= ideal:
            return 100
        if lift <= floor:
            return 20
        t = _clamp((lift - floor) / (ideal - floor), 0.0, 1.0)
        return int(_clamp(_round(20 + t * 80), 0, 100))

    def _score_posture(self, body_line: float | None) -> int:
        if body_line is None and not self._body_lines:
            return 70
        samples = list(self._body_lines)
        if body_line is not None:
            samples.append(body_line)
        mean = sum(samples) / len(samples)
        dev = abs(self._config.ideal_body_line_angle - mean)
        if dev <= self._config.body_line_tolerance_degrees:
            return 100
        if dev >= self._config.max_body_lean_degrees:
            return 20
        span = self._config.max_body_lean_degrees - self._config.body_line_tolerance_degrees
        t = _clamp((dev - self._config.body_line_tolerance_degrees) / span, 0.0, 1.0)
        return int(_clamp(_round(100 - t * 80), 0, 100))

    def _score_rhythm(self, elapsed: int) -> int:
        if elapsed <= 0:
            return 70
        if elapsed < self._config.minimum_movement_duration:
            return int(
                _clamp(
                    _round(40 + (elapsed / self._config.minimum_movement_duration) * 40),
                    0,
                    100,
                )
            )
        if elapsed > self._config.maximum_movement_duration:
            over = (elapsed - self._config.maximum_movement_duration) / (
                self._config.ideal_movement_time_ms
            )
            return int(_clamp(_round(85 - over * 35), 25, 100))
        dist = abs(elapsed - self._config.ideal_movement_time_ms) / (
            self._config.ideal_movement_time_ms
        )
        return int(_clamp(_round(100 - dist * 40), 0, 100))

    def _live(self, action: ActionRecognitionResult, lift: float | None) -> str:
        cue = action.form_cue
        if cue:
            return cue
        if action.machine_state in (
            SquatMachineState.waiting_person,
            SquatMachineState.standing,
        ):
            return "双脚落地后把膝盖抬向髋部"
        if action.machine_state == SquatMachineState.bottom:
            if lift is not None and lift < self._config.ideal_knee_lift_ratio:
                return "膝盖再抬高一些"
            return "保持躯干直立"
        return "轻快落地，准备下一次抬腿"

    def _feedback(
        self,
        *,
        score: int,
        height: int,
        posture: int,
        rhythm: int,
        high_enough: bool,
    ) -> str:
        if not high_enough or (height <= posture and height <= rhythm and height < 75):
            return "膝盖再抬高一些"
        if score >= self._config.correct_score_threshold and posture >= 75:
            return "动作标准"
        if posture <= height and posture <= rhythm:
            return "身体保持直立，不要后仰"
        if rhythm < 65:
            return "步频放稳一些"
        return "动作标准"

    def _hold(self, *, feedback: str) -> EvaluationResult:
        self._last = EvaluationResult(
            score=self._last.score,
            amplitude_score=self._last.amplitude_score,
            stability_score=self._last.stability_score,
            rhythm_score=self._last.rhythm_score,
            feedback=feedback,
            is_correct=self._last.is_correct,
            knee_angle_min=self._last.knee_angle_min,
            knee_angle_max=self._last.knee_angle_max,
            range_of_motion=self._last.range_of_motion,
            movement_duration_ms=self._last.movement_duration_ms,
        )
        return self._last

    def _clear_step(self) -> None:
        self._step_started_at = None
        self._max_lift = 0
        self._body_lines.clear()
