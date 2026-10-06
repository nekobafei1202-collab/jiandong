from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonalBaseline:
    standing_angle: float = 165
    squat_angle: float = 90
    range_of_motion: float = 75
    movement_speed: float = 1.0
    stability: float = 1.0


PersonalBaseline.defaults = PersonalBaseline()  # type: ignore[attr-defined]
