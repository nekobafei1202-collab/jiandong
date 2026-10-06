"""One frame sample inside a push-up cycle, for trajectory / evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PushupFrameData:
    timestamp: datetime
    left_elbow_angle: float | None = None
    right_elbow_angle: float | None = None
    primary_elbow_angle: float | None = None
    body_line_angle: float | None = None
    elbow_flare_angle: float | None = None
    shoulder_torso_angle: float | None = None
    shoulder_y: float | None = None
    hip_y: float | None = None
    ankle_y: float | None = None
    hip_offset: float | None = None
    neck_reach: bool = False
    shrugged: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "leftElbowAngle": self.left_elbow_angle,
            "rightElbowAngle": self.right_elbow_angle,
            "primaryElbowAngle": self.primary_elbow_angle,
            "bodyLineAngle": self.body_line_angle,
            "elbowFlareAngle": self.elbow_flare_angle,
            "shoulderTorsoAngle": self.shoulder_torso_angle,
            "shoulderY": self.shoulder_y,
            "hipY": self.hip_y,
            "ankleY": self.ankle_y,
            "hipOffset": self.hip_offset,
            "neckReach": self.neck_reach,
            "shrugged": self.shrugged,
        }


@dataclass(frozen=True)
class PushupRepTrajectory:
    """Trajectory of one push-up attempt (HIGH → … → HIGH)."""

    frames: list[PushupFrameData]
    completed: bool
    min_elbow_angle: float | None
    max_elbow_angle: float | None
    range_of_motion: float | None
    movement_duration_ms: int
    min_body_line_angle: float | None = None
    abort_reason: str | None = None

    @property
    def is_empty(self) -> bool:
        return len(self.frames) == 0
