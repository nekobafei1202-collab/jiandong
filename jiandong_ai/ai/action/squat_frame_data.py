"""One frame sample inside a squat cycle, for trajectory / future adaptation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SquatFrameData:
    timestamp: datetime
    left_knee_angle: float | None
    right_knee_angle: float | None
    hip_y: float | None
    knee_y: float | None
    ankle_y: float | None
    primary_knee_angle: float | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "leftKneeAngle": self.left_knee_angle,
            "rightKneeAngle": self.right_knee_angle,
            "hipY": self.hip_y,
            "kneeY": self.knee_y,
            "ankleY": self.ankle_y,
            "primaryKneeAngle": self.primary_knee_angle,
        }


@dataclass(frozen=True)
class SquatRepTrajectory:
    """Trajectory of one squat attempt (STANDING → … → STANDING)."""

    frames: list[SquatFrameData]
    completed: bool
    min_knee_angle: float | None
    max_knee_angle: float | None
    range_of_motion: float | None
    movement_duration_ms: int

    @property
    def is_empty(self) -> bool:
        return len(self.frames) == 0
