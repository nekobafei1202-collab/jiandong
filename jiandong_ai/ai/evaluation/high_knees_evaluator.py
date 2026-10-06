"""High-knees quality scoring (height / posture / rhythm)."""

from __future__ import annotations

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
        self._prev: SquatMachineState | None = None
        self._max_lift = 0.0
        self._min_lift = 1.0
        self._started: datetime | None = None
        self._body_devs: list[float] = []

    def reset(self) -> None:
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._prev = None
        self._max_lift = 0.0
        self._min_lift = 1.0
        self._started = None
        self._body_devs.clear()

    def evaluate(
        self,
        *,
        action: ActionRecognitionResult,
        pose: PoseResult,
        baseline: PersonalBaseline | None = None,
        config: SquatConfig | None = None,
    ) -> EvaluationResult:
        lift = (action.knee_angle or 0) / 100.0
        if action.machine_state == SquatMachineState.bottom:
            if self._started is None:
                self._started = datetime.now()
            self._max_lift = max(self._max_lift, lift)
            self._min_lift = min(self._min_lift, lift)
            if action.body_line_angle is not None:
                self._body_devs.append(
                    abs(action.body_line_angle - self._config.ideal_body_line_angle)
                )

        if action.just_completed_rep:
            height = _clamp(
                100
                * (self._max_lift / max(0.01, self._config.ideal_knee_lift_ratio)),
                0,
                100,
            )
            mean_dev = (
                sum(self._body_devs) / len(self._body_devs) if self._body_devs else 0
            )
            if mean_dev <= self._config.body_line_tolerance_degrees:
                posture = 100.0
            elif mean_dev >= self._config.max_body_lean_degrees:
                posture = 40.0
            else:
                span = (
                    self._config.max_body_lean_degrees
                    - self._config.body_line_tolerance_degrees
                )
                posture = 100 - 60 * (
                    (mean_dev - self._config.body_line_tolerance_degrees) / span
                )
            duration = 0
            if self._started is not None:
                duration = int(
                    (datetime.now() - self._started).total_seconds() * 1000
                )
            ideal = self._config.ideal_movement_time_ms
            rhythm = _clamp(100 - abs(duration - ideal) / ideal * 100, 40, 100)
            score = int(
                height * self._config.height_score_weight
                + posture * self._config.posture_score_weight
                + rhythm * self._config.rhythm_score_weight
            )
            feedback = "抬膝到位" if height >= 80 else "膝盖再抬高一些"
            if posture < 70:
                feedback = "躯干保持直立，不要后仰"
            self._last = EvaluationResult(
                score=score,
                amplitude_score=int(height),
                stability_score=int(posture),
                rhythm_score=int(rhythm),
                feedback=feedback,
                is_correct=score >= self._config.correct_score_threshold,
                knee_angle_min=self._min_lift * 100,
                knee_angle_max=self._max_lift * 100,
                range_of_motion=(self._max_lift - self._min_lift) * 100,
                movement_duration_ms=duration,
            )
            self._max_lift = 0.0
            self._min_lift = 1.0
            self._started = None
            self._body_devs.clear()
        elif action.phase == ActionPhase.no_person:
            self._last = EvaluationResult(
                score=self._last.score,
                amplitude_score=self._last.amplitude_score,
                stability_score=self._last.stability_score,
                rhythm_score=self._last.rhythm_score,
                feedback="请调整位置，确保全身进入摄像头",
                is_correct=self._last.is_correct,
            )
        self._prev = action.machine_state
        return self._last
