"""Central thresholds for dead bug (死虫式) hold monitoring.

Dead bug is an alternating-reach core drill; counting limbs is unreliable at
bridge frame rates, so it is a hold action: the set completes by keeping the
pose visible. Visibility gate (spec): shoulder + hip + at least one wrist or
ankle at minimum confidence. Deliberately lenient — a timer, not a counter.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeadBugConfig:
    target_hold_ms: int = 30000
    minimum_confidence: float = 0.3
    state_confirm_frames: int = 2
    min_state_duration_ms: int = 100
    min_rep_interval_ms: int = 1000
    good_ratio_score_weight: float = 0.70
    stability_score_weight: float = 0.30
    stability_poor_std_dev: float = 0.06
    correct_score_threshold: int = 70


DeadBugConfig.defaults = DeadBugConfig()  # type: ignore[attr-defined]
