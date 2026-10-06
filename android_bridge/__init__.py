"""Android bridge package — COCO-17 contract shared with native Pose Landmarker."""

from .coco17_contract import COCO17_NAMES, MEDIAPIPE_TO_COCO17, landmarks_to_coco17_payload

__all__ = [
    "COCO17_NAMES",
    "MEDIAPIPE_TO_COCO17",
    "landmarks_to_coco17_payload",
]
