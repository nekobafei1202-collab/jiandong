"""Central thresholds for glute bridge (臀桥) recognition / evaluation.

Keep all magic numbers here — never scatter them in UI.

Primary signal: hip angle shoulder→hip→knee (side view, lying supine).
Flat on the floor ≈ 100~130°, full hip extension ≥ 160°.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GluteBridgeConfig:
    down_hip_angle: float = 140
    top_hip_angle: float = 160
    top_hysteresis: float = 8
    down_exit_hysteresis: float = 5
    min_count_hip_angle: float = 150
    ideal_top_hip_angle: float = 175
    max_healthy_hip_angle: float = 185
    hyperextension_limit_angle: float = 195
    minimum_confidence: float = 0.35
    state_confirm_frames: int = 3
    min_state_duration_ms: int = 120
    min_rep_interval_ms: int = 700
    min_effective_range_of_motion: float = 25
    minimum_movement_duration: int = 800
    maximum_movement_duration: int = 3000
    ideal_movement_time_ms: int = 1800
    amplitude_score_weight: float = 0.40
    stability_score_weight: float = 0.30
    rhythm_score_weight: float = 0.30
    correct_score_threshold: int = 70
    stability_full_score_sway: float = 0.03
    stability_zero_score_sway: float = 0.15

    @property
    def confirm_frames(self) -> int:
        return self.state_confirm_frames

    @property
    def min_movement_time_ms(self) -> int:
        return self.minimum_movement_duration

    @property
    def max_movement_time_ms(self) -> int:
        return self.maximum_movement_duration


GluteBridgeConfig.defaults = GluteBridgeConfig()  # type: ignore[attr-defined]
