from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SquatConfig:
    standing_knee_angle: float = 155
    down_knee_angle: float = 130
    bottom_knee_angle: float = 100
    minimum_confidence: float = 0.35
    state_confirm_frames: int = 3
    min_state_duration_ms: int = 120
    minimum_movement_duration: int = 700
    maximum_movement_duration: int = 4500
    ideal_movement_time_ms: int = 1800
    min_rep_interval_ms: int = 700
    range_score_weight: float = 0.40
    stability_score_weight: float = 0.30
    rhythm_score_weight: float = 0.30
    correct_score_threshold: int = 70
    min_effective_range_of_motion: float = 45

    @property
    def confirm_frames(self) -> int:
        return self.state_confirm_frames

    @property
    def min_movement_time_ms(self) -> int:
        return self.minimum_movement_duration

    @property
    def max_movement_time_ms(self) -> int:
        return self.maximum_movement_duration


SquatConfig.defaults = SquatConfig()  # type: ignore[attr-defined]
