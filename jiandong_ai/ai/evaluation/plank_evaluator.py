"""Session-based plank quality: good-hold time ratio + line stability."""

from __future__ import annotations

import math
from datetime import datetime

from ..action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
)
from ..action.plank_config import PlankConfig
from ..action.squat_config import SquatConfig
from ..pose.pose_result import PoseResult
from .action_evaluator import ActionEvaluator, EvaluationResult
from .personal_baseline import PersonalBaseline


def _ms_between(later: datetime, earlier: datetime) -> int:
    return max(0, int((later - earlier).total_seconds() * 1000))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class PlankEvaluator(ActionEvaluator):
    def __init__(self, config: PlankConfig | None = None) -> None:
        self._config = config or PlankConfig.defaults
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._good_ms = 0
        self._total_ms = 0
        self._last_frame_at: datetime | None = None
        self._angles: list[float] = []
        self._sag_frames = 0
        self._pike_frames = 0

    @property
    def config(self) -> PlankConfig:
        return self._config

    def update_config(self, value: PlankConfig) -> None:
        self._config = value

    @property
    def last_result(self) -> EvaluationResult:
        return self._last

    def reset(self) -> None:
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._good_ms = 0
        self._total_ms = 0
        self._last_frame_at = None
        self._angles.clear()
        self._sag_frames = 0
        self._pike_frames = 0

    def evaluate(
        self,
        *,
        action: ActionRecognitionResult,
        pose: PoseResult,
        baseline: PersonalBaseline | None = None,
        config: SquatConfig | None = None,
    ) -> EvaluationResult:
        angle = action.body_line_angle
        if (
            action.phase == ActionPhase.no_person
            or not action.has_reliable_pose
            or angle is None
        ):
            self._last_frame_at = None
            self._last = EvaluationResult(
                score=self._last.score,
                amplitude_score=self._last.amplitude_score,
                stability_score=self._last.stability_score,
                rhythm_score=self._last.rhythm_score,
                feedback="请调整位置，确保全身进入摄像头",
                is_correct=self._last.is_correct,
                knee_angle_min=self._last.knee_angle_min,
                knee_angle_max=self._last.knee_angle_max,
                range_of_motion=self._last.range_of_motion,
                movement_duration_ms=self._total_ms,
            )
            return self._last

        now = pose.timestamp
        last = self._last_frame_at
        delta = 0 if last is None else _ms_between(now, last)
        self._last_frame_at = now
        self._total_ms += delta

        self._angles.append(angle)
        if self._config.is_good_angle(angle):
            self._good_ms += delta
        elif angle < self._config.good_min_body_line_angle:
            self._sag_frames += 1
        else:
            self._pike_frames += 1

        good_ratio = self._good_ms / self._total_ms if self._total_ms > 0 else 0.0
        stability = self._stability_score()
        ratio_score = int(_clamp(round(good_ratio * 100), 0, 100))
        score = int(
            _clamp(
                round(
                    ratio_score * self._config.good_ratio_score_weight
                    + stability * self._config.stability_score_weight
                ),
                0,
                100,
            )
        )

        self._last = EvaluationResult(
            score=score,
            amplitude_score=ratio_score,
            stability_score=stability,
            rhythm_score=0,
            feedback=self._feedback(action),
            is_correct=score >= self._config.correct_score_threshold,
            knee_angle_min=min(self._angles),
            knee_angle_max=max(self._angles),
            range_of_motion=None,
            movement_duration_ms=self._total_ms,
        )
        return self._last

    def _stability_score(self) -> int:
        if len(self._angles) < 2:
            return 100
        mean = sum(self._angles) / len(self._angles)
        variance = sum((b - mean) * (b - mean) for b in self._angles) / len(
            self._angles
        )
        std_dev = math.sqrt(variance)
        ratio = _clamp(1 - std_dev / self._config.stability_poor_std_dev, 0.0, 1.0)
        return int(_clamp(round(ratio * 100), 0, 100))

    def _feedback(self, action: ActionRecognitionResult) -> str:
        live = action.form_cue
        if live:
            return live
        if self._sag_frames == 0 and self._pike_frames == 0:
            return "姿势良好"
        return "塌腰" if self._sag_frames >= self._pike_frames else "翘臀"
