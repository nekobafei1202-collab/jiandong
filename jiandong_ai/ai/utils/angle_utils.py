from __future__ import annotations

import math

from ..pose.keypoint import Keypoint
from ..pose.pose_result import BodyLineChain, LowerBodyChain, PoseResult, UpperBodyChain


class AngleUtils:
    @staticmethod
    def angle_at_vertex(a: Keypoint, vertex: Keypoint, b: Keypoint) -> float:
        ax = a.x - vertex.x
        ay = a.y - vertex.y
        bx = b.x - vertex.x
        by = b.y - vertex.y
        dot = ax * bx + ay * by
        mag_a = math.sqrt(ax * ax + ay * ay)
        mag_b = math.sqrt(bx * bx + by * by)
        if mag_a == 0 or mag_b == 0:
            return 0.0
        cos = max(-1.0, min(1.0, dot / (mag_a * mag_b)))
        return math.acos(cos) * 180 / math.pi

    @staticmethod
    def calculate_angle(a: Keypoint, b: Keypoint, c: Keypoint) -> float:
        return AngleUtils.angle_at_vertex(a, b, c)

    @staticmethod
    def knee_angle(chain: LowerBodyChain) -> float | None:
        if not chain.is_reliable:
            return None
        return AngleUtils.angle_at_vertex(chain.hip, chain.knee, chain.ankle)

    @staticmethod
    def knee_angle_from_pose(pose: PoseResult) -> float | None:
        chain = pose.preferred_lower_body
        if chain is None:
            return None
        return AngleUtils.knee_angle(chain)

    @staticmethod
    def both_knee_angles(pose: PoseResult) -> tuple[float | None, float | None]:
        from ..pose.keypoint import BodySide

        left = pose.lower_body(BodySide.left)
        right = pose.lower_body(BodySide.right)
        return (
            None if left is None else AngleUtils.knee_angle(left),
            None if right is None else AngleUtils.knee_angle(right),
        )

    @staticmethod
    def elbow_angle(chain: UpperBodyChain) -> float | None:
        if not chain.is_reliable:
            return None
        return AngleUtils.angle_at_vertex(chain.shoulder, chain.elbow, chain.wrist)

    @staticmethod
    def elbow_angle_from_pose(pose: PoseResult) -> float | None:
        chain = pose.preferred_upper_body
        if chain is None:
            return None
        return AngleUtils.elbow_angle(chain)

    @staticmethod
    def body_line_angle(chain: BodyLineChain) -> float | None:
        if not chain.is_reliable:
            return None
        return AngleUtils.angle_at_vertex(chain.shoulder, chain.hip, chain.ankle)

    @staticmethod
    def body_line_angle_from_pose(pose: PoseResult) -> float | None:
        chain = pose.preferred_body_line
        if chain is None:
            return None
        return AngleUtils.body_line_angle(chain)

    @staticmethod
    def shoulder_torso_angle(
        *, hip: Keypoint, shoulder: Keypoint, elbow: Keypoint
    ) -> float:
        return AngleUtils.angle_at_vertex(hip, shoulder, elbow)
