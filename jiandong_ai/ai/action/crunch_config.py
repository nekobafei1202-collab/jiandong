"""Central thresholds for crunch (卷腹) recognition / evaluation.

Primary signal: torso flexion angle shoulder→hip→knee (side view, lying
supine). Measured on real footage (scripts/diagnose_crunch_count.py,
mixkit 4591 home sit-up + 36015 crunch):

- Flat baseline is ~123-170°, NOT 160-180°: with knees bent the hip angle
  never opens fully. 4591 lies "flat" at 125-130° — a ≥140° flat threshold
  can never be reached, which was the main reason real videos never counted.
- Curled bottom reaches ~28-55° on full-depth reps; shallow crunches bottom
  around ~100-110° and should NOT count (卷起高度不足).
- Phone bridge is ~12fps: confirm stays at 1 frame, debounce comes from a
  3-frame median on the torso angle (same lesson as pushup lenient mode).

Thresholds: flat ≥118 (below the 123 noise floor of measured flat, above the
108 curling trigger), curling ≤108, curled ≤95 (hysteresis +8 → exit ≥103).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CrunchConfig:
    high_torso_angle: float = 118
    down_torso_angle: float = 108
    bottom_torso_angle: float = 95
    bottom_hysteresis: float = 8
    min_count_torso_angle: float = 100
    ideal_bottom_torso_angle: float = 75
    minimum_confidence: float = 0.3
    state_confirm_frames: int = 1
    min_state_duration_ms: int = 0
    min_rep_interval_ms: int = 600
    min_effective_range_of_motion: float = 20
    minimum_movement_duration: int = 600
    maximum_movement_duration: int = 3000
    ideal_movement_time_ms: int = 1500
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


CrunchConfig.defaults = CrunchConfig()  # type: ignore[attr-defined]
