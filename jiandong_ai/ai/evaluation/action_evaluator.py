from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..action.action_recognizer import ActionRecognitionResult
    from ..action.squat_config import SquatConfig
    from ..pose.pose_result import PoseResult
    from .personal_baseline import PersonalBaseline


@dataclass
class EvaluationResult:
    score: int
    amplitude_score: int
    stability_score: int
    rhythm_score: int
    feedback: str
    is_correct: bool = False
    knee_angle_min: float | None = None
    knee_angle_max: float | None = None
    range_of_motion: float | None = None
    movement_duration_ms: int = 0


@dataclass
class SquatEvaluationResult:
    score: int
    is_correct: bool
    feedback: str
    min_knee_angle: float | None
    max_knee_angle: float | None
    range_of_motion: float | None
    movement_duration: int
    stability_score: int
    rhythm_score: int
    range_score: int

    @property
    def knee_angle_min(self) -> float | None:
        return self.min_knee_angle

    @property
    def knee_angle_max(self) -> float | None:
        return self.max_knee_angle

    @property
    def movement_duration_ms(self) -> int:
        return self.movement_duration

    @property
    def as_evaluation(self) -> EvaluationResult:
        return EvaluationResult(
            score=self.score,
            amplitude_score=self.range_score,
            stability_score=self.stability_score,
            rhythm_score=self.rhythm_score,
            feedback=self.feedback,
            is_correct=self.is_correct,
            knee_angle_min=self.min_knee_angle,
            knee_angle_max=self.max_knee_angle,
            range_of_motion=self.range_of_motion,
            movement_duration_ms=self.movement_duration,
        )


class ActionEvaluator(ABC):
    @abstractmethod
    def evaluate(
        self,
        *,
        action: ActionRecognitionResult,
        pose: PoseResult,
        baseline: PersonalBaseline | None = None,
        config: SquatConfig | None = None,
    ) -> EvaluationResult: ...

    @abstractmethod
    def reset(self) -> None: ...
