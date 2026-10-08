from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image, ImageDraw

from jiandong_ai.ai.pose.keypoint import POSE_SKELETON_EDGES, KeypointName
from jiandong_ai.ai.pose.pose_result import PoseResult

# Default placeholder caption (Chinese via escapes).
_PLACEHOLDER_TEXT = "\u7b49\u5f85\u6444\u50cf\u5934\u2026"


def draw_pose_overlay(
    frame_bgr: np.ndarray,
    pose: PoseResult,
    *,
    # Flutter PoseOverlay cyan bones (BGR).
    line_color: tuple[int, int, int] = (230, 225, 92),
    point_color: tuple[int, int, int] = (230, 225, 92),
    vignette: bool = True,
) -> np.ndarray:
    """Draw COCO-17 skeleton on a BGR frame, optionally with a light vignette.

    Uses PIL so Android (no OpenCV wheel) can still render the live preview.
    """
    out = frame_bgr.copy()
    h, w = out.shape[:2]

    def xy(name: KeypointName) -> tuple[int, int] | None:
        kp = pose.keypoints.get(name)
        if kp is None or not kp.is_reliable():
            return None
        if pose.is_normalized:
            return int(kp.x * w), int(kp.y * h)
        return int(kp.x), int(kp.y)

    # BGR -> RGB for PIL drawing, then back.
    rgb = out[:, :, ::-1].copy()
    img = Image.fromarray(rgb)
    draw = ImageDraw.Draw(img)
    line_rgb = (line_color[2], line_color[1], line_color[0])
    point_rgb = (point_color[2], point_color[1], point_color[0])
    for a, b in POSE_SKELETON_EDGES:
        pa, pb = xy(a), xy(b)
        if pa and pb:
            draw.line([pa, pb], fill=line_rgb, width=2)
    for name in KeypointName:
        p = xy(name)
        if p:
            x, y = p
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=point_rgb, outline=(255, 255, 255))
    out = np.asarray(img)[:, :, ::-1].copy()

    if vignette and h > 0 and w > 0:
        yy, xx = np.ogrid[:h, :w]
        cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
        ry = max(cy, 1.0)
        rx = max(cx, 1.0)
        dist = np.sqrt(((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2)
        factor = np.clip(1.0 - 0.28 * np.clip(dist - 0.55, 0, None) / 0.45, 0.72, 1.0)
        out = (out.astype(np.float32) * factor[..., None]).astype(np.uint8)

    return out


def frame_to_base64_jpg(frame_bgr: np.ndarray, quality: int = 75) -> str:
    """Encode BGR ndarray as JPEG base64 — PIL path (Android-safe, no cv2)."""
    if frame_bgr is None or frame_bgr.size == 0:
        return ""
    rgb = frame_bgr[:, :, ::-1] if frame_bgr.ndim == 3 else frame_bgr
    img = Image.fromarray(np.ascontiguousarray(rgb))
    bio = io.BytesIO()
    img.save(bio, format="JPEG", quality=int(quality))
    return base64.b64encode(bio.getvalue()).decode("ascii")


def b64_to_src(b64: str) -> str:
    """Flet 1.0 Image uses src= data URI, not src_base64."""
    if not b64:
        return ""
    if b64.startswith("data:"):
        return b64
    return f"data:image/jpeg;base64,{b64}"


def frame_to_image_src(frame_bgr: np.ndarray, quality: int = 75) -> str:
    return b64_to_src(frame_to_base64_jpg(frame_bgr, quality=quality))


def placeholder_image(
    width: int = 480,
    height: int = 640,
    text: str | None = None,
) -> str:
    """Return a JPEG data URI suitable for ft.Image(src=...)."""
    label = _PLACEHOLDER_TEXT if text is None else text
    img = Image.new("RGB", (width, height), (7, 10, 15))
    if label:
        draw = ImageDraw.Draw(img)
        tw = max(8, len(label) * 7)
        draw.text((max(8, width // 2 - tw // 2), height // 2 - 8), label, fill=(168, 176, 188))
    bio = io.BytesIO()
    img.save(bio, format="JPEG", quality=80)
    return b64_to_src(base64.b64encode(bio.getvalue()).decode("ascii"))
