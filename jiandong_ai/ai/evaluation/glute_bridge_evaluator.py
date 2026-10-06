"""Glute-bridge quality scoring."""

from __future__ import annotations

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
        self._min_angle: float | None = None
        self._max_angle: float | None = None
        self._started: datetime | None = None

    def reset(self) -> None:
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._min_angle = None
        self._max_angle = None
        self._started = None

    def evaluate(
        self,
        *,
        action: ActionRecognitionResult,
        pose: PoseResult,
        baseline: PersonalBaseline | None = None,
        config: SquatConfig | None = None,
    ) -> EvaluationResult:
        angle = action.knee_angle  # hip extension angle stored here
        if angle is not None and action.has_reliable_pose:
            self._min_angle = (
                angle if self._min_angle is None else min(self._min_angle, angle)
            )
            self._max_angle = (
                angle if self._max_angle is None else max(self._max_angle, angle)
            )
            if self._started is None and action.machine_state != SquatMachineState.waiting_person:
                self._started = datetime.now()

        if action.just_completed_rep:
            top = self._max_angle or angle or 0
            # Higher hip angle ≈ better extension toward 180
            ideal = getattr(self._config, "ideal_top_hip_angle", 170)
            amplitude = _clamp(100 * (top / max(1.0, ideal)), 0, 100)
            duration = 0
            if self._started is not None:
                duration = int((datetime.now() - self._started).total_seconds() * 1000)
            ideal_ms = getattr(self._config, "ideal_movement_time_ms", 1800)
            rhythm = _clamp(100 - abs(duration - ideal_ms) / ideal_ms * 100, 40, 100)
            stability = 85.0
            w_r = getattr(
                self._config,
                "amplitude_score_weight",
                getattr(self._config, "range_score_weight", 0.4),
            )
            w_s = getattr(self._config, "stability_score_weight", 0.3)
            w_t = getattr(self._config, "rhythm_score_weight", 0.3)
            score = int(amplitude * w_r + stability * w_s + rhythm * w_t)
            feedback = "顶髋到位" if amplitude >= 80 else "继续顶髋，臀肌发力"
            thresh = getattr(self._config, "correct_score_threshold", 70)
            self._last = EvaluationResult(
                score=score,
                amplitude_score=int(amplitude),
                stability_score=int(stability),
                rhythm_score=int(rhythm),
                feedback=feedback,
                is_correct=score >= thresh,
                knee_angle_min=self._min_angle,
                knee_angle_max=self._max_angle,
                range_of_motion=(
                    None
                    if self._min_angle is None or self._max_angle is None
                    else self._max_angle - self._min_angle
                ),
                movement_duration_ms=duration,
            )
            self._min_angle = None
            self._max_angle = None
            self._started = None
        elif action.phase == ActionPhase.no_person:
            self._last = EvaluationResult(
                score=self._last.score,
                amplitude_score=self._last.amplitude_score,
                stability_score=self._last.stability_score,
                rhythm_score=self._last.rhythm_score,
                feedback="请侧对镜头，让肩、髋、膝进入画面",
                is_correct=self._last.is_correct,
            )
        elif action.form_cue:
            self._last = EvaluationResult(
                score=self._last.score,
                amplitude_score=self._last.amplitude_score,
                stability_score=self._last.stability_score,
                rhythm_score=self._last.rhythm_score,
                feedback=action.form_cue,
                is_correct=self._last.is_correct,
            )
        return self._last
