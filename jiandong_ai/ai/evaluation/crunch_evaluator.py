"""Crunch quality scoring, following glute_bridge_evaluator's structure.

Amplitude from the deepest torso-flexion angle reached in the rep (lower is
better), stability from hip sway, rhythm from rep duration.
"""

from __future__ import annotations

import math
from datetime import datetime

from ..action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    SquatMachineState,
)
from ..action.crunch_config import CrunchConfig
from ..action.squat_config import SquatConfig
from ..pose.pose_result import PoseResult
from .action_evaluator import ActionEvaluator, EvaluationResult
from .personal_baseline import PersonalBaseline


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> int:
    return int(math.floor(v + 0.5)) if v >= 0 else -int(math.floor(-v + 0.5))


class CrunchEvaluator(ActionEvaluator):
    def __init__(self, config: CrunchConfig | None = None) -> None:
        self._config = config or CrunchConfig.defaults
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._rep_started_at: datetime | None = None
        self._trough: float | None = None
        self._hip_xs: list[float] = []
        self._scale: float | None = None

    def reset(self) -> None:
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._clear_rep()

    def evaluate(
        self,
        *,
        action: ActionRecognitionResult,
        pose: PoseResult,
        baseline: PersonalBaseline | None = None,
        config: SquatConfig | None = None,
    ) -> EvaluationResult:
        if action.phase == ActionPhase.no_person or not action.has_reliable_pose:
            self._rep_started_at = None
            return self._hold(
                feedback=action.form_cue or "请侧对镜头仰卧，让肩、髋、膝进入画面"
            )

        working = action.machine_state in (
            SquatMachineState.down,
            SquatMachineState.bottom,
            SquatMachineState.up,
        )
        if working and self._rep_started_at is None:
            self._rep_started_at = pose.timestamp
            self._trough = action.knee_angle
            self._hip_xs.clear()
            self._scale = None
        if working:
            self._sample(action, pose)

        if action.just_completed_rep:
            return self._finish(action, pose, counted=True)

        aborted = (
            action.machine_state == SquatMachineState.standing
            and action.form_cue == "卷起高度不足"
            and self._trough is not None
        )
        if aborted:
            return self._finish(action, pose, counted=False)

        if action.machine_state == SquatMachineState.standing:
            self._clear_rep()
        return self._hold(feedback=action.form_cue or self._live(action))

    def _sample(self, action: ActionRecognitionResult, pose: PoseResult) -> None:
        angle = action.knee_angle
        if angle is not None:
            self._trough = (
                angle if self._trough is None else min(self._trough, angle)
            )
        hip = pose.left_hip or pose.right_hip
        shoulder = pose.left_shoulder or pose.right_shoulder
        if hip is None or shoulder is None:
            return
        torso = shoulder.distance_to(hip)
        if torso > 0.02:
            self._scale = torso
        self._hip_xs.append(hip.x)

    def _finish(
        self,
        action: ActionRecognitionResult,
        pose: PoseResult,
        *,
        counted: bool,
    ) -> EvaluationResult:
        trough = min(
            self._trough if self._trough is not None else 180,
            action.rep_min_knee_angle if action.rep_min_knee_angle is not None else 180,
        )
        amplitude = self._score_amplitude(trough)
        stability = self._score_stability()
        rhythm = self._score_rhythm(self._elapsed(pose.timestamp))
        score = (
            _round(
                _clamp(
                    amplitude * self._config.amplitude_score_weight
                    + stability * self._config.stability_score_weight
                    + rhythm * self._config.rhythm_score_weight,
                    0,
                    100,
                )
            )
            if counted
            else self._last.score
        )
        deep_enough = trough <= self._config.min_count_torso_angle
        self._last = EvaluationResult(
            score=score,
            amplitude_score=amplitude,
            stability_score=stability,
            rhythm_score=rhythm,
            feedback=(
                self._feedback(
                    score=score,
                    amplitude=amplitude,
                    stability=stability,
                    rhythm=rhythm,
                    deep_enough=deep_enough,
                )
                if counted
                else "卷起高度不足，肩胛要离地"
            ),
            is_correct=(
                counted
                and deep_enough
                and score >= self._config.correct_score_threshold
            ),
            knee_angle_min=trough if trough < 180 else None,
            knee_angle_max=action.rep_max_knee_angle,
            range_of_motion=action.range_of_motion,
            movement_duration_ms=self._elapsed(pose.timestamp),
        )
        self._clear_rep()
        return self._last

    def _elapsed(self, now: datetime) -> int:
        start = self._rep_started_at
        if start is None:
            return 0
        return max(0, int((now - start).total_seconds() * 1000))

    def _score_amplitude(self, trough: float) -> int:
        """trough = 本次最小躯干角；越小卷得越充分。"""
        if trough >= self._config.min_count_torso_angle:
            span = self._config.high_torso_angle - self._config.min_count_torso_angle
            t = 1.0 if span <= 0 else _clamp(
                (self._config.high_torso_angle - trough) / span, 0.0, 1.0
            )
            return _round(20 + t * 30)
        if trough <= self._config.ideal_bottom_torso_angle:
            return 100
        span = self._config.min_count_torso_angle - self._config.ideal_bottom_torso_angle
        t = 1.0 if span <= 0 else _clamp(
            (self._config.min_count_torso_angle - trough) / span, 0.0, 1.0
        )
        return _round(70 + t * 30)

    def _score_stability(self) -> int:
        if len(self._hip_xs) < 3 or self._scale is None or self._scale <= 0:
            return 80
        mean = sum(self._hip_xs) / len(self._hip_xs)
        variance = sum((x - mean) * (x - mean) for x in self._hip_xs)
        std = math.sqrt(variance / len(self._hip_xs)) / self._scale
        if std <= self._config.stability_full_score_sway:
            return 100
        if std >= self._config.stability_zero_score_sway:
            return 20
        span = (
            self._config.stability_zero_score_sway
            - self._config.stability_full_score_sway
        )
        t = _clamp((std - self._config.stability_full_score_sway) / span, 0.0, 1.0)
        return int(_clamp(_round(100 - t * 80), 0, 100))

    def _score_rhythm(self, elapsed: int) -> int:
        if elapsed <= 0:
            return 70
        if elapsed < self._config.minimum_movement_duration:
            return int(
                _clamp(
                    _round(
                        40
                        + (elapsed / self._config.minimum_movement_duration) * 40
                    ),
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

    def _live(self, action: ActionRecognitionResult) -> str:
        return {
            SquatMachineState.waiting_person: "请侧对镜头仰卧，屈膝躺好",
            SquatMachineState.standing: "用腹部发力卷起上背，不要甩头",
            SquatMachineState.down: "继续卷起，肩胛离地",
            SquatMachineState.bottom: "顶点稍停，收紧腹部",
            SquatMachineState.up: "有控制地放下",
        }[action.machine_state]

    def _feedback(
        self,
        *,
        score: int,
        amplitude: int,
        stability: int,
        rhythm: int,
        deep_enough: bool,
    ) -> str:
        if not deep_enough or (
            amplitude < 75 and amplitude <= stability and amplitude <= rhythm
        ):
            return "再卷起高一些，肩胛要离地"
        if score >= self._config.correct_score_threshold and amplitude >= 75:
            return "动作标准"
        if rhythm < 65:
            return "卷起放慢一些，感受腹部发力"
        if stability <= amplitude and stability <= rhythm and stability < 70:
            return "骨盆保持稳定，不要左右晃"
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

    def _clear_rep(self) -> None:
        self._rep_started_at = None
        self._trough = None
        self._hip_xs.clear()
        self._scale = None
