from __future__ import annotations

import base64
import io
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw

from jiandong_ai.ai.pose.keypoint import POSE_SKELETON_EDGES, KeypointName
from jiandong_ai.ai.pose.pose_result import PoseResult
from jiandong_ai.app.theme import HUD_CYAN


def draw_pose_overlay(
    frame_bgr: np.ndarray,
    pose: PoseResult,
    *,
    line_color: tuple[int, int, int] = (230, 225, 92),  # BGR ≈ cyan
    point_color: tuple[int, int, int] = (98, 214, 94),
) -> np.ndarray:
    import cv2

    out = frame_bgr.copy()
    h, w = out.shape[:2]

    def xy(name: KeypointName) -> tuple[int, int] | None:
        kp = pose.keypoints.get(name)
        if kp is None or not kp.is_reliable():
            return None
        if pose.is_normalized:
            return int(kp.x * w), int(kp.y * h)
        return int(kp.x), int(kp.y)

    for a, b in POSE_SKELETON_EDGES:
        pa, pb = xy(a), xy(b)
        if pa and pb:
            cv2.line(out, pa, pb, line_color, 2, cv2.LINE_AA)
    for name in KeypointName:
        p = xy(name)
        if p:
            cv2.circle(out, p, 4, point_color, -1, cv2.LINE_AA)
    return out


def frame_to_base64_jpg(frame_bgr: np.ndarray, quality: int = 75) -> str:
    import cv2

    ok, buf = cv2.imencode(".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("ascii")


def placeholder_image(width: int = 480, height: int = 640, text: str = "等待摄像头…") -> str:
    img = Image.new("RGB", (width, height), (7, 10, 15))
    draw = ImageDraw.Draw(img)
    draw.text((width // 2 - 60, height // 2), text, fill=(168, 176, 188))
    bio = io.BytesIO()
    img.save(bio, format="JPEG", quality=80)
    return base64.b64encode(bio.getvalue()).decode("ascii")
