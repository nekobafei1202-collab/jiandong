"""Pose Landmarker → COCO-17 mapping helper (shared contract).

Android native code should emit JSON matching this schema so Python
`PoseResult.from_keypoints` can consume it without branching.
"""

from __future__ import annotations

COCO17_NAMES = (
    "nose",
    "leftEye",
    "rightEye",
    "leftEar",
    "rightEar",
    "leftShoulder",
    "rightShoulder",
    "leftElbow",
    "rightElbow",
    "leftWrist",
    "rightWrist",
    "leftHip",
    "rightHip",
    "leftKnee",
    "rightKnee",
    "leftAnkle",
    "rightAnkle",
)

# MediaPipe BlazePose 33 → COCO-17 name index into landmark list
MEDIAPIPE_TO_COCO17 = {
    0: "nose",
    2: "leftEye",
    5: "rightEye",
    7: "leftEar",
    8: "rightEar",
    11: "leftShoulder",
    12: "rightShoulder",
    13: "leftElbow",
    14: "rightElbow",
    15: "leftWrist",
    16: "rightWrist",
    23: "leftHip",
    24: "rightHip",
    25: "leftKnee",
    26: "rightKnee",
    27: "leftAnkle",
    28: "rightAnkle",
}


def landmarks_to_coco17_payload(
    landmarks: list[dict],
    *,
    image_width: float = 0,
    image_height: float = 0,
    is_front_camera: bool = False,
    rotation_degrees: int = 0,
) -> dict:
    """Convert MediaPipe landmark dicts `{x,y,visibility}` to bridge JSON."""
    keypoints = []
    for idx, name in MEDIAPIPE_TO_COCO17.items():
        if idx >= len(landmarks):
            continue
        lm = landmarks[idx]
        keypoints.append(
            {
                "name": name,
                "x": float(lm.get("x", 0)),
                "y": float(lm.get("y", 0)),
                "confidence": float(lm.get("visibility", lm.get("confidence", 0))),
            }
        )
    return {
        "imageWidth": image_width,
        "imageHeight": image_height,
        "isFrontCamera": is_front_camera,
        "rotationDegrees": rotation_degrees,
        "keypoints": keypoints,
    }
