"""Central thresholds for high-knees (高抬腿) recognition / evaluation.

Signal: per-leg knee lift normalized by leg length.
  leg_len = ankle.y - hip.y  (y axis points down, leg_len > 0)
  lift   = (hip.y - knee.y) / leg_len + knee_rest_offset
Standing with a straight leg ⇒ lift ≈ 0; knee at hip height ⇒ lift ≈
knee_rest_offset (0.5). All size-dependent thresholds are ratios of leg /
torso length — never absolute pixel or normalized-coordinate distances.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HighKneesConfig:
    high_knee_lift_ratio: float = 0.45
    idle_knee_lift_ratio: float = 0.18
    ideal_knee_lift_ratio: float = 0.55
    knee_rest_offset: float = 0.5
    handoff_count_max_lift: float = 0.35
    min_leg_to_torso_ratio: float = 0.6
    minimum_confidence: float = 0.35
    state_confirm_frames: int = 2
    min_state_duration_ms: int = 60
    min_rep_interval_ms: int = 250
    rhythm_min_step_ms: int = 300
    rhythm_max_step_ms: int = 900
    ideal_movement_time_ms: int = 550
    minimum_movement_duration: int = 250
    maximum_movement_duration: int = 1500
    ideal_body_line_angle: float = 180
    body_line_tolerance_degrees: float = 12
    max_body_lean_degrees: float = 30
    height_score_weight: float = 0.45
    posture_score_weight: float = 0.30
    rhythm_score_weight: float = 0.25
    correct_score_threshold: int = 70
    min_effective_lift_range: float = 0.20

    @property
    def confirm_frames(self) -> int:
        return self.state_confirm_frames

    @property
    def min_movement_time_ms(self) -> int:
        return self.minimum_movement_duration

    @property
    def max_movement_time_ms(self) -> int:
        return self.maximum_movement_duration


HighKneesConfig.defaults = HighKneesConfig()  # type: ignore[attr-defined]
