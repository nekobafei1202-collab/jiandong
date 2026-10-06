"""Central thresholds for jumping-jack recognition / evaluation.

Keep all magic numbers here — never scatter them in logic or UI.
All size-related thresholds are normalized by shoulder width
(never raw pixels / absolute normalized distances).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JumpingJackConfig:
    apart_leg_ratio: float = 1.4
    together_leg_ratio: float = 0.9
    full_leg_spread_ratio: float = 1.8
    arm_down_shoulder_margin: float = 0.05
    full_arm_raise_ratio: float = 0.8
    min_shoulder_width: float = 0.04
    minimum_confidence: float = 0.35
    state_confirm_frames: int = 3
    min_state_duration_ms: int = 120
    min_rep_interval_ms: int = 700
    min_cycle_duration_ms: int = 700
    max_cycle_duration_ms: int = 1500
    range_score_weight: float = 0.40
    stability_score_weight: float = 0.30
    rhythm_score_weight: float = 0.30
    correct_score_threshold: int = 70

    @property
    def confirm_frames(self) -> int:
        return self.state_confirm_frames

    @property
    def minimum_movement_duration(self) -> int:
        return self.min_cycle_duration_ms

    @property
    def maximum_movement_duration(self) -> int:
        return self.max_cycle_duration_ms


JumpingJackConfig.defaults = JumpingJackConfig()  # type: ignore[attr-defined]
