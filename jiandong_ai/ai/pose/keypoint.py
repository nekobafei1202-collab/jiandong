from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


class KeypointName(str, Enum):
    nose = "nose"
    leftEye = "leftEye"
    rightEye = "rightEye"
    leftEar = "leftEar"
    rightEar = "rightEar"
    leftShoulder = "leftShoulder"
    rightShoulder = "rightShoulder"
    leftElbow = "leftElbow"
    rightElbow = "rightElbow"
    leftWrist = "leftWrist"
    rightWrist = "rightWrist"
    leftHip = "leftHip"
    rightHip = "rightHip"
    leftKnee = "leftKnee"
    rightKnee = "rightKnee"
    leftAnkle = "leftAnkle"
    rightAnkle = "rightAnkle"


K_COCO_KEYPOINT_COUNT = 17


class BodySide(str, Enum):
    left = "left"
    right = "right"


@dataclass(frozen=True)
class Keypoint:
    name: KeypointName
    x: float
    y: float
    confidence: float

    DEFAULT_MIN_CONFIDENCE = 0.35

    def is_reliable(self, min_confidence: float = DEFAULT_MIN_CONFIDENCE) -> bool:
        return self.confidence >= min_confidence

    def distance_to(self, other: Keypoint) -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "x": self.x,
            "y": self.y,
            "confidence": self.confidence,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Keypoint:
        raw = data.get("name", "nose")
        try:
            name = KeypointName(raw)
        except ValueError:
            name = KeypointName.nose
        return cls(
            name=name,
            x=float(data["x"]),
            y=float(data["y"]),
            confidence=float(data["confidence"]),
        )

    def copy_with(
        self,
        *,
        name: KeypointName | None = None,
        x: float | None = None,
        y: float | None = None,
        confidence: float | None = None,
    ) -> Keypoint:
        return Keypoint(
            name=name or self.name,
            x=self.x if x is None else x,
            y=self.y if y is None else y,
            confidence=self.confidence if confidence is None else confidence,
        )


POSE_SKELETON_EDGES: list[tuple[KeypointName, KeypointName]] = [
    (KeypointName.leftEar, KeypointName.leftEye),
    (KeypointName.leftEye, KeypointName.nose),
    (KeypointName.nose, KeypointName.rightEye),
    (KeypointName.rightEye, KeypointName.rightEar),
    (KeypointName.leftShoulder, KeypointName.rightShoulder),
    (KeypointName.leftShoulder, KeypointName.leftElbow),
    (KeypointName.leftElbow, KeypointName.leftWrist),
    (KeypointName.rightShoulder, KeypointName.rightElbow),
    (KeypointName.rightElbow, KeypointName.rightWrist),
    (KeypointName.leftShoulder, KeypointName.leftHip),
    (KeypointName.rightShoulder, KeypointName.rightHip),
    (KeypointName.leftHip, KeypointName.rightHip),
    (KeypointName.leftHip, KeypointName.leftKnee),
    (KeypointName.leftKnee, KeypointName.leftAnkle),
    (KeypointName.rightHip, KeypointName.rightKnee),
    (KeypointName.rightKnee, KeypointName.rightAnkle),
]
