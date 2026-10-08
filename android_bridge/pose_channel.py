"""Flet-facing helper to ingest Android bridge pose JSON."""

from __future__ import annotations

from datetime import datetime

from jiandong_ai.ai.pose.mediapipe_detector import BridgePoseDetector
from jiandong_ai.ai.pose.pose_result import PoseResult


_bridge = BridgePoseDetector()


def pose_from_bridge_payload(payload: dict) -> PoseResult:
    """Convert native bridge COCO-17 JSON (RTMPose ORT) into PoseResult."""
    return _bridge.detect(payload, timestamp=datetime.now())
