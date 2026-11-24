from __future__ import annotations

from datetime import datetime

from .keypoint import Keypoint
from .pose_detector import PoseDetector
from .pose_result import PoseResult

class BridgePoseDetector(PoseDetector):
    """Consumes COCO-17 JSON payloads from Android native bridge."""

    def detect(self, frame, *, timestamp: datetime | None = None) -> PoseResult:
        if not isinstance(frame, dict):
            return PoseResult.empty(timestamp=timestamp)
        raw = frame.get("keypoints") or []
        points = [Keypoint.from_json(dict(p)) for p in raw if isinstance(p, dict)]
        return PoseResult.from_keypoints(
            points,
            timestamp=timestamp,
            image_width=float(frame.get("imageWidth") or 0),
            image_height=float(frame.get("imageHeight") or 0),
            is_front_camera=bool(frame.get("isFrontCamera", False)),
            rotation_degrees=int(frame.get("rotationDegrees") or 0),
        )
