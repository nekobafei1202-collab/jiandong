"""Central thresholds for reverse-lunge recognition / evaluation.

Same family as SquatConfig, but single-leg: the primary signal is the
front-leg knee angle, plus a normalized hip-drop check (hip↔ankle span
relative to the standing baseline, so no absolute pixel distances).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReverseLungeConfig:
    standing_knee_angle: float = 155
    down_knee_angle: float = 130
    bottom_knee_angle: float = 100
    minimum_confidence: float = 0.35
    state_confirm_frames: int = 3
    min_state_duration_ms: int = 120
    minimum_movement_duration: int = 1000
    maximum_movement_duration: int = 4000
    ideal_movement_time_ms: int = 2200
    min_rep_interval_ms: int = 700
    min_effective_range_of_motion: float = 45
    min_hip_drop_ratio: float = 0.15
    good_hip_drop_ratio: float = 0.30
    torso_upright_lean_angle: float = 20
    torso_bad_lean_angle: float = 45
    max_hip_sway_ratio: float = 0.12
    bad_hip_sway_ratio: float = 0.35
    depth_score_weight: float = 0.35
    posture_score_weight: float = 0.25
    stability_score_weight: float = 0.20
    rhythm_score_weight: float = 0.20
    correct_score_threshold: int = 70

    @property
    def confirm_frames(self) -> int:
        return self.state_confirm_frames

    @property
    def min_movement_time_ms(self) -> int:
        return self.minimum_movement_duration

    @property
    def max_movement_time_ms(self) -> int:
        return self.maximum_movement_duration


ReverseLungeConfig.defaults = ReverseLungeConfig()  # type: ignore[attr-defined]
