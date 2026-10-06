"""Central thresholds for plank (平板支撑) recognition / evaluation.

Plank is a hold-monitoring action (no rep cycles). All decisions use the
shoulder→hip→ankle body line. Because a plain interior joint angle can
never exceed 180°, the recognizer works with a *signed* body-line angle:
hip below the shoulder–ankle line (y 轴向下 = 靠近地面) keeps the interior
angle (塌腰 side, < 180°); hip above the line maps to 360° − interior
(翘臀 side, > 180°). Good range is therefore [good_min, good_max] = 165~195°.

All thresholds are angles or times — scale-free by construction.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlankConfig:
    good_min_body_line_angle: float = 165
    good_max_body_line_angle: float = 195
    ideal_body_line_angle: float = 180
    target_hold_ms: int = 30000
    minimum_confidence: float = 0.35
    state_confirm_frames: int = 3
    min_state_duration_ms: int = 150
    min_rep_interval_ms: int = 1000
    good_ratio_score_weight: float = 0.70
    stability_score_weight: float = 0.30
    stability_poor_std_dev: float = 8
    correct_score_threshold: int = 70

    def is_good_angle(self, signed_angle: float) -> bool:
        return (
            signed_angle >= self.good_min_body_line_angle
            and signed_angle <= self.good_max_body_line_angle
        )


PlankConfig.defaults = PlankConfig()  # type: ignore[attr-defined]
