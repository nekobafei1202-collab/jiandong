from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from .keypoint import BodySide, Keypoint, KeypointName


@dataclass(frozen=True)
class LowerBodyChain:
    side: BodySide
    hip: Keypoint
    knee: Keypoint
    ankle: Keypoint

    @property
    def is_reliable(self) -> bool:
        return (
            self.hip.is_reliable()
            and self.knee.is_reliable()
            and self.ankle.is_reliable()
        )


@dataclass(frozen=True)
class UpperBodyChain:
    side: BodySide
    shoulder: Keypoint
    elbow: Keypoint
    wrist: Keypoint

    @property
    def is_reliable(self) -> bool:
        return (
            self.shoulder.is_reliable()
            and self.elbow.is_reliable()
            and self.wrist.is_reliable()
        )


@dataclass(frozen=True)
class BodyLineChain:
    side: BodySide
    shoulder: Keypoint
    hip: Keypoint
    ankle: Keypoint

    @property
    def is_reliable(self) -> bool:
        return (
            self.shoulder.is_reliable()
            and self.hip.is_reliable()
            and self.ankle.is_reliable()
        )


@dataclass
class PoseResult:
    keypoints: dict[KeypointName, Keypoint] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    image_width: float = 0
    image_height: float = 0
    has_person: bool = False
    confidence: float = 0
    rotation_degrees: int = 0
    is_front_camera: bool = False

    @classmethod
    def empty(cls, timestamp: datetime | None = None) -> PoseResult:
        return cls(
            keypoints={},
            timestamp=timestamp or datetime.now(),
            has_person=False,
            confidence=0,
        )

    @classmethod
    def from_keypoints(
        cls,
        points: Iterable[Keypoint],
        *,
        timestamp: datetime | None = None,
        image_width: float = 0,
        image_height: float = 0,
        person_confidence_threshold: float = Keypoint.DEFAULT_MIN_CONFIDENCE,
        rotation_degrees: int = 0,
        is_front_camera: bool = False,
    ) -> PoseResult:
        mapping = {p.name: p for p in points}
        values = list(mapping.values())
        avg = (
            sum(p.confidence for p in values) / len(values) if values else 0.0
        )
        reliable_count = sum(
            1 for p in values if p.is_reliable(person_confidence_threshold)
        )
        return cls(
            keypoints=mapping,
            timestamp=timestamp or datetime.now(),
            image_width=image_width,
            image_height=image_height,
            has_person=reliable_count >= 4,
            confidence=avg,
            rotation_degrees=rotation_degrees,
            is_front_camera=is_front_camera,
        )

    @property
    def detected(self) -> bool:
        return self.has_person

    @property
    def is_normalized(self) -> bool:
        return self.image_width <= 0 or self.image_height <= 0

    @property
    def keypoint_count(self) -> int:
        return len(self.keypoints)

    def __getitem__(self, name: KeypointName) -> Keypoint | None:
        return self.keypoints.get(name)

    @property
    def nose(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.nose)

    @property
    def left_eye(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.leftEye)

    @property
    def right_eye(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.rightEye)

    @property
    def left_ear(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.leftEar)

    @property
    def right_ear(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.rightEar)

    @property
    def left_shoulder(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.leftShoulder)

    @property
    def right_shoulder(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.rightShoulder)

    @property
    def left_elbow(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.leftElbow)

    @property
    def right_elbow(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.rightElbow)

    @property
    def left_wrist(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.leftWrist)

    @property
    def right_wrist(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.rightWrist)

    @property
    def left_hip(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.leftHip)

    @property
    def right_hip(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.rightHip)

    @property
    def left_knee(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.leftKnee)

    @property
    def right_knee(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.rightKnee)

    @property
    def left_ankle(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.leftAnkle)

    @property
    def right_ankle(self) -> Keypoint | None:
        return self.keypoints.get(KeypointName.rightAnkle)

    def lower_body(self, side: BodySide) -> LowerBodyChain | None:
        if side == BodySide.left:
            hip, knee, ankle = self.left_hip, self.left_knee, self.left_ankle
            if hip is None or knee is None or ankle is None:
                return None
            return LowerBodyChain(BodySide.left, hip, knee, ankle)
        hip, knee, ankle = self.right_hip, self.right_knee, self.right_ankle
        if hip is None or knee is None or ankle is None:
            return None
        return LowerBodyChain(BodySide.right, hip, knee, ankle)

    def upper_body(self, side: BodySide) -> UpperBodyChain | None:
        if side == BodySide.left:
            shoulder, elbow, wrist = (
                self.left_shoulder,
                self.left_elbow,
                self.left_wrist,
            )
            if shoulder is None or elbow is None or wrist is None:
                return None
            return UpperBodyChain(BodySide.left, shoulder, elbow, wrist)
        shoulder, elbow, wrist = (
            self.right_shoulder,
            self.right_elbow,
            self.right_wrist,
        )
        if shoulder is None or elbow is None or wrist is None:
            return None
        return UpperBodyChain(BodySide.right, shoulder, elbow, wrist)

    @property
    def preferred_upper_body(self) -> UpperBodyChain | None:
        left = self.upper_body(BodySide.left)
        right = self.upper_body(BodySide.right)
        if left and left.is_reliable and right and right.is_reliable:
            left_score = (
                left.shoulder.confidence
                + left.elbow.confidence
                + left.wrist.confidence
            )
            right_score = (
                right.shoulder.confidence
                + right.elbow.confidence
                + right.wrist.confidence
            )
            return left if left_score >= right_score else right
        if left and left.is_reliable:
            return left
        if right and right.is_reliable:
            return right
        return left or right

    def body_line(self, side: BodySide) -> BodyLineChain | None:
        if side == BodySide.left:
            shoulder, hip, ankle = (
                self.left_shoulder,
                self.left_hip,
                self.left_ankle,
            )
            if shoulder is None or hip is None or ankle is None:
                return None
            return BodyLineChain(BodySide.left, shoulder, hip, ankle)
        shoulder, hip, ankle = (
            self.right_shoulder,
            self.right_hip,
            self.right_ankle,
        )
        if shoulder is None or hip is None or ankle is None:
            return None
        return BodyLineChain(BodySide.right, shoulder, hip, ankle)

    @property
    def preferred_body_line(self) -> BodyLineChain | None:
        left = self.body_line(BodySide.left)
        right = self.body_line(BodySide.right)
        if left and left.is_reliable and right and right.is_reliable:
            left_score = (
                left.shoulder.confidence
                + left.hip.confidence
                + left.ankle.confidence
            )
            right_score = (
                right.shoulder.confidence
                + right.hip.confidence
                + right.ankle.confidence
            )
            return left if left_score >= right_score else right
        if left and left.is_reliable:
            return left
        if right and right.is_reliable:
            return right
        return left or right

    @property
    def preferred_lower_body(self) -> LowerBodyChain | None:
        left = self.lower_body(BodySide.left)
        right = self.lower_body(BodySide.right)
        if left and left.is_reliable and right and right.is_reliable:
            left_score = (
                left.hip.confidence + left.knee.confidence + left.ankle.confidence
            )
            right_score = (
                right.hip.confidence
                + right.knee.confidence
                + right.ankle.confidence
            )
            return left if left_score >= right_score else right
        if left and left.is_reliable:
            return left
        if right and right.is_reliable:
            return right
        return left or right

    @property
    def has_reliable_lower_body(self) -> bool:
        chain = self.preferred_lower_body
        return chain is not None and chain.is_reliable

    @property
    def average_confidence(self) -> float:
        return self.confidence

    @property
    def reliable_keypoints(self) -> list[Keypoint]:
        return [p for p in self.keypoints.values() if p.is_reliable()]

    def to_json(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "imageWidth": self.image_width,
            "imageHeight": self.image_height,
            "hasPerson": self.has_person,
            "detected": self.detected,
            "confidence": self.confidence,
            "keypoints": [p.to_json() for p in self.keypoints.values()],
        }
