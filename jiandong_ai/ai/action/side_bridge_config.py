"""Central thresholds for side bridge (侧桥) hold monitoring.

Hold action (no rep cycles): the signed shoulder→hip→ankle body line decides
whether the pose counts. Same signed convention as plank: hip below the
shoulder–ankle line keeps the interior angle (髋下沉 side, < 180°); hip above
maps to 360° − interior. Side bridge tolerance is deliberately loose
(150~210°) — this is a timer, not a rep counter.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SideBridgeConfig:
    good_min_body_line_angle: float = 150
    good_max_body_line_angle: float = 210
    ideal_body_line_angle: float = 180
    target_hold_ms: int = 30000
    minimum_confidence: float = 0.3
    state_confirm_frames: int = 2
    min_state_duration_ms: int = 100
    min_rep_interval_ms: int = 1000
    good_ratio_score_weight: float = 0.70
    stability_score_weight: float = 0.30
    stability_poor_std_dev: float = 10
    correct_score_threshold: int = 70

    def is_good_angle(self, signed_angle: float) -> bool:
        return (
            signed_angle >= self.good_min_body_line_angle
            and signed_angle <= self.good_max_body_line_angle
        )


SideBridgeConfig.defaults = SideBridgeConfig()  # type: ignore[attr-defined]
