"""Central thresholds for push-up recognition / evaluation.

Coach keyframes (demo mannequin v4 is FINAL / status validated):
- High plank elbow ≈ 165–175° (lockout 180°)
- Mid down ≈ 90–120° (mannequin 103°)
- Bottom ≈ 70–90° (mannequin 78°, chest near hand height)
- Shoulder–hip–ankle collinear ±15° (no 塌腰 / 撅臀)
- Upper-arm to torso 45–60°, hard abort above 70° (飞肘)
- Shoulder and hip descend together; toes stay; no elbow-only cheat

Must keypoints: shoulder, elbow, wrist, hip.
Prefer: nose/ear (neck), ankle/knee (body line).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PushupConfig:
    high_elbow_angle: float = 165
    down_elbow_angle: float = 120
    bottom_elbow_angle: float = 90
    ideal_high_elbow_angle: float = 180
    ideal_mid_elbow_angle: float = 103
    ideal_bottom_elbow_angle: float = 78
    body_line_tolerance_degrees: float = 15
    ideal_body_line_angle: float = 180
    ideal_flare_min_degrees: float = 45
    ideal_flare_max_degrees: float = 60
    max_elbow_flare_degrees: float = 70
    collapsed_shoulder_angle: float = 35
    neck_reach_y: float = 0.14
    shrug_ear_distance: float = 0.08
    min_hip_travel: float = 0.02
    min_hip_travel_ratio: float = 0.35
    minimum_confidence: float = 0.35
    state_confirm_frames: int = 3
    min_state_duration_ms: int = 120
    minimum_movement_duration: int = 600
    maximum_movement_duration: int = 4000
    ideal_movement_time_ms: int = 1400
    min_rep_interval_ms: int = 500
    range_score_weight: float = 0.40
    alignment_score_weight: float = 0.30
    rhythm_score_weight: float = 0.30
    correct_score_threshold: int = 70
    min_effective_range_of_motion: float = 70

    @property
    def min_body_line_angle(self) -> float:
        """Body-line floor matching ±body_line_tolerance_degrees."""
        return self.ideal_body_line_angle - self.body_line_tolerance_degrees

    @property
    def confirm_frames(self) -> int:
        return self.state_confirm_frames

    @property
    def min_movement_time_ms(self) -> int:
        return self.minimum_movement_duration

    @property
    def max_movement_time_ms(self) -> int:
        return self.maximum_movement_duration

    @property
    def stability_score_weight(self) -> float:
        return self.alignment_score_weight


PushupConfig.defaults = PushupConfig()  # type: ignore[attr-defined]
