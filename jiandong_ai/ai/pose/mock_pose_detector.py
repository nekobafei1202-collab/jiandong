from __future__ import annotations

import math
from datetime import datetime, timedelta

from .keypoint import Keypoint, KeypointName
from .pose_detector import PoseDetector
from .pose_result import PoseResult


class MockPoseDetector(PoseDetector):
    """Synthetic squat loop for offline tests / demos without a camera."""

    def __init__(self) -> None:
        self._t0 = datetime.now()
        self._phase = 0.0

    def restart_cycle(self) -> None:
        self._t0 = datetime.now()
        self._phase = 0.0

    def detect(self, frame=None, *, timestamp: datetime | None = None) -> PoseResult:
        ts = timestamp or datetime.now()
        elapsed = (ts - self._t0).total_seconds()
        # 0..1 over ~2s cycle
        cycle = (elapsed % 2.0) / 2.0
        # standing ~170 → bottom ~85 → standing
        if cycle < 0.5:
            knee = 170 - (170 - 85) * (cycle / 0.5)
        else:
            knee = 85 + (170 - 85) * ((cycle - 0.5) / 0.5)

        # Approximate 2D stick figure in normalized coords from knee angle.
        hip_y = 0.45
        # law of sines-ish placement
        shin = 0.18
        thigh = 0.18
        # place knee/ankle given hip and knee angle (simplified vertical plane)
        rad = math.radians(180 - knee)
        knee_y = hip_y + thigh * math.sin(rad * 0.5 + 0.4)
        ankle_y = knee_y + shin * 0.9
        cx = 0.5

        def kp(name: KeypointName, x: float, y: float, c: float = 0.95) -> Keypoint:
            return Keypoint(name=name, x=x, y=y, confidence=c)

        points = [
            kp(KeypointName.nose, cx, 0.18),
            kp(KeypointName.leftEye, cx - 0.02, 0.16),
            kp(KeypointName.rightEye, cx + 0.02, 0.16),
            kp(KeypointName.leftEar, cx - 0.04, 0.17),
            kp(KeypointName.rightEar, cx + 0.04, 0.17),
            kp(KeypointName.leftShoulder, cx - 0.08, 0.28),
            kp(KeypointName.rightShoulder, cx + 0.08, 0.28),
            kp(KeypointName.leftElbow, cx - 0.12, 0.38),
            kp(KeypointName.rightElbow, cx + 0.12, 0.38),
            kp(KeypointName.leftWrist, cx - 0.14, 0.46),
            kp(KeypointName.rightWrist, cx + 0.14, 0.46),
            kp(KeypointName.leftHip, cx - 0.05, hip_y),
            kp(KeypointName.rightHip, cx + 0.05, hip_y),
            kp(KeypointName.leftKnee, cx - 0.05, knee_y),
            kp(KeypointName.rightKnee, cx + 0.05, knee_y),
            kp(KeypointName.leftAnkle, cx - 0.05, ankle_y),
            kp(KeypointName.rightAnkle, cx + 0.05, ankle_y),
        ]
        return PoseResult.from_keypoints(points, timestamp=ts)
