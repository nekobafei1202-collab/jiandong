"""Dead-bug hold scoring: in-frame time ratio + shoulder stability.

Dead bug has no reliable joint-angle gate at bridge frame rates, so the score
is the share of monitored time the practitioner stays visible, plus how still
the shoulders stay (腰部贴地的代理指标：肩胛不乱晃).
"""

from __future__ import annotations

import math
from datetime import datetime

from ..action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
)
from ..action.dead_bug_config import DeadBugConfig
from ..action.squat_config import SquatConfig
from ..pose.pose_result import PoseResult
from .action_evaluator import ActionEvaluator, EvaluationResult
from .personal_baseline import PersonalBaseline


def _ms_between(later: datetime, earlier: datetime) -> int:
    return max(0, int((later - earlier).total_seconds() * 1000))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class DeadBugEvaluator(ActionEvaluator):
    def __init__(self, config: DeadBugConfig | None = None) -> None:
        self._config = config or DeadBugConfig.defaults
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
        self._shoulder_ys: list[float] = []
        self._scale: float | None = None

    @property
    def config(self) -> DeadBugConfig:
        return self._config

    def update_config(self, value: DeadBugConfig) -> None:
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
        self._shoulder_ys.clear()
        self._scale = None

    def evaluate(
        self,
        *,
        action: ActionRecognitionResult,
        pose: PoseResult,
        baseline: PersonalBaseline | None = None,
        config: SquatConfig | None = None,
    ) -> EvaluationResult:
        if (
            action.phase == ActionPhase.no_person
            or not action.has_reliable_pose
        ):
            self._last_frame_at = None
            self._last = EvaluationResult(
                score=self._last.score,
                amplitude_score=self._last.amplitude_score,
                stability_score=self._last.stability_score,
                rhythm_score=self._last.rhythm_score,
                feedback=action.form_cue or "请调整位置，确保全身进入摄像头",
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
        self._good_ms += delta

        shoulder = pose.left_shoulder or pose.right_shoulder
        hip = pose.left_hip or pose.right_hip
        if shoulder is not None:
            self._shoulder_ys.append(shoulder.y)
            if hip is not None:
                torso = shoulder.distance_to(hip)
                if torso > 0.02:
                    self._scale = torso

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
            feedback=self._feedback(stability),
            is_correct=score >= self._config.correct_score_threshold,
            range_of_motion=None,
            movement_duration_ms=self._total_ms,
        )
        return self._last

    def _stability_score(self) -> int:
        ys = self._shoulder_ys
        if len(ys) < 2 or self._scale is None or self._scale <= 0:
            return 100
        mean = sum(ys) / len(ys)
        variance = sum((y - mean) * (y - mean) for y in ys) / len(ys)
        std = math.sqrt(variance) / self._scale
        ratio = _clamp(1 - std / self._config.stability_poor_std_dev, 0.0, 1.0)
        return int(_clamp(round(ratio * 100), 0, 100))

    def _feedback(self, stability: int) -> str:
        if stability < 60:
            return "保持腰部贴地，肩膀不要乱晃"
        return "姿势良好"
