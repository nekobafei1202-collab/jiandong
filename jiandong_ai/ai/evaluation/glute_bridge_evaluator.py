"""Glute-bridge quality scoring.

Mirrors lib/ai/evaluation/glute_bridge_evaluator.dart formula by formula:
amplitude piecewise (with hyperextension penalty), hip-sway stability,
three-segment rhythm, isCorrect gate and feedback copy.
"""

from __future__ import annotations

import math
from datetime import datetime

from ..action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    SquatMachineState,
)
from ..action.glute_bridge_config import GluteBridgeConfig
from ..action.squat_config import SquatConfig
from ..pose.pose_result import PoseResult
from .action_evaluator import ActionEvaluator, EvaluationResult
from .personal_baseline import PersonalBaseline


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _round(v: float) -> int:
    # Dart's num.round() rounds half away from zero.
    return int(math.floor(v + 0.5)) if v >= 0 else -int(math.floor(-v + 0.5))


class GluteBridgeEvaluator(ActionEvaluator):
    def __init__(self, config: GluteBridgeConfig | None = None) -> None:
        self._config = config or GluteBridgeConfig.defaults
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._rep_started_at: datetime | None = None
        self._peak: float | None = None
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
                feedback=action.form_cue or "请侧对镜头，让肩、髋、膝进入画面"
            )

        working = action.machine_state in (
            SquatMachineState.down,
            SquatMachineState.bottom,
            SquatMachineState.up,
        )
        if working and self._rep_started_at is None:
            self._rep_started_at = pose.timestamp
            self._peak = action.knee_angle
            self._hip_xs.clear()
            self._scale = None
        if working:
            self._sample(action, pose)

        if action.just_completed_rep:
            return self._finish(action, pose, counted=True)

        aborted = (
            action.machine_state == SquatMachineState.standing
            and action.form_cue == "顶髋高度不足"
            and self._peak is not None
        )
        if aborted:
            return self._finish(action, pose, counted=False)

        if action.machine_state == SquatMachineState.standing:
            self._clear_rep()
        return self._hold(feedback=action.form_cue or self._live(action))

    def _sample(self, action: ActionRecognitionResult, pose: PoseResult) -> None:
        angle = action.knee_angle
        if angle is not None:
            self._peak = angle if self._peak is None else max(self._peak, angle)
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
        peak = max(self._peak or 0, action.rep_max_knee_angle or 0)
        amplitude = self._score_amplitude(peak)
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
        overarched = peak >= self._config.max_healthy_hip_angle
        high_enough = peak >= self._config.min_count_hip_angle
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
                    overarched=overarched,
                    high_enough=high_enough,
                )
                if counted
                else "顶髋高度不足"
            ),
            is_correct=(
                counted
                and not overarched
                and score >= self._config.correct_score_threshold
                and high_enough
            ),
            knee_angle_min=action.rep_min_knee_angle,
            knee_angle_max=peak if peak > 0 else None,
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

    def _score_amplitude(self, peak: float) -> int:
        if peak <= 0:
            return 30
        if peak < self._config.min_count_hip_angle:
            t = _clamp(peak / self._config.min_count_hip_angle, 0.0, 1.0)
            return _round(20 + t * 30)
        if peak <= self._config.ideal_top_hip_angle:
            span = self._config.ideal_top_hip_angle - self._config.min_count_hip_angle
            t = 1.0 if span <= 0 else _clamp(
                (peak - self._config.min_count_hip_angle) / span, 0.0, 1.0
            )
            return int(_clamp(_round(70 + t * 30), 0, 100))
        if peak <= self._config.max_healthy_hip_angle:
            return 100
        if peak >= self._config.hyperextension_limit_angle:
            return 25
        span = self._config.hyperextension_limit_angle - self._config.max_healthy_hip_angle
        t = 1.0 if span <= 0 else _clamp(
            (peak - self._config.max_healthy_hip_angle) / span, 0.0, 1.0
        )
        return int(_clamp(_round(100 - t * 75), 0, 100))

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
        span = self._config.stability_zero_score_sway - self._config.stability_full_score_sway
        t = _clamp((std - self._config.stability_full_score_sway) / span, 0.0, 1.0)
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

    def _live(self, action: ActionRecognitionResult) -> str:
        return {
            SquatMachineState.waiting_person: "请侧对镜头仰卧，肩背贴地",
            SquatMachineState.standing: "靠臀部把髋顶起，不要用腰代偿",
            SquatMachineState.down: "继续顶髋，臀肌发力",
            SquatMachineState.bottom: "顶点稍停，腰不要拱起",
            SquatMachineState.up: "有控制地放下",
        }[action.machine_state]

    def _feedback(
        self,
        *,
        score: int,
        amplitude: int,
        stability: int,
        rhythm: int,
        overarched: bool,
        high_enough: bool,
    ) -> str:
        if overarched:
            return "不要用腰过度顶起"
        if (
            not high_enough
            or (amplitude < 75 and amplitude <= stability and amplitude <= rhythm)
        ):
            return "再把髋部顶高一点"
        if score >= self._config.correct_score_threshold and amplitude >= 75:
            return "动作标准"
        if stability <= amplitude and stability <= rhythm and stability < 70:
            return "髋部保持稳定，不要左右晃"
        if rhythm < 65:
            return "下落时放慢一些"
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
        self._peak = None
        self._hip_xs.clear()
        self._scale = None
