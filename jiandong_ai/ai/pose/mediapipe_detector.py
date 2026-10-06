from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np

from .keypoint import Keypoint, KeypointName
from .pose_detector import PoseDetector
from .pose_result import PoseResult

# MediaPipe Pose landmark indices → COCO-17
_MP_TO_COCO: dict[int, KeypointName] = {
    0: KeypointName.nose,
    2: KeypointName.leftEye,
    5: KeypointName.rightEye,
    7: KeypointName.leftEar,
    8: KeypointName.rightEar,
    11: KeypointName.leftShoulder,
    12: KeypointName.rightShoulder,
    13: KeypointName.leftElbow,
    14: KeypointName.rightElbow,
    15: KeypointName.leftWrist,
    16: KeypointName.rightWrist,
    23: KeypointName.leftHip,
    24: KeypointName.rightHip,
    25: KeypointName.leftKnee,
    26: KeypointName.rightKnee,
    27: KeypointName.leftAnkle,
    28: KeypointName.rightAnkle,
}


def _default_model_path() -> Path:
    return Path(__file__).resolve().parents[3] / "models" / "pose_landmarker_lite.task"


class MediaPipePoseDetector(PoseDetector):
    """Windows / desktop detector using MediaPipe Tasks PoseLandmarker."""

    def __init__(self, *, model_path: str | Path | None = None) -> None:
        self._landmarker = None
        self._mp_image_cls = None
        self._init_error: str | None = None
        path = Path(model_path) if model_path else _default_model_path()
        try:
            from mediapipe.tasks.python import vision
            from mediapipe.tasks.python.core import base_options as bo
            import mediapipe as mp

            if not path.exists():
                raise FileNotFoundError(
                    f"Pose model missing: {path}. "
                    "Download pose_landmarker_lite.task into models/."
                )
            options = vision.PoseLandmarkerOptions(
                base_options=bo.BaseOptions(model_asset_path=str(path)),
                running_mode=vision.RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._landmarker = vision.PoseLandmarker.create_from_options(options)
            self._mp_image_cls = mp.Image
            self._mp_image_format = mp.ImageFormat.SRGB
            self._ts_ms = 0
        except Exception as exc:  # noqa: BLE001
            self._init_error = str(exc)

    @property
    def available(self) -> bool:
        return self._landmarker is not None

    @property
    def init_error(self) -> str | None:
        return self._init_error

    def detect(
        self,
        frame: np.ndarray,
        *,
        timestamp: datetime | None = None,
        is_front_camera: bool = True,
    ) -> PoseResult:
        if self._landmarker is None or self._mp_image_cls is None:
            return PoseResult.empty(timestamp=timestamp)

        import cv2

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = self._mp_image_cls(image_format=self._mp_image_format, data=rgb)
        self._ts_ms += 33  # ~30fps monotonic timestamps for VIDEO mode
        result = self._landmarker.detect_for_video(mp_image, self._ts_ms)
        if not result.pose_landmarks:
            return PoseResult.empty(timestamp=timestamp)

        lms = result.pose_landmarks[0]
        points: list[Keypoint] = []
        for idx, name in _MP_TO_COCO.items():
            if idx >= len(lms):
                continue
            lm = lms[idx]
            conf = float(getattr(lm, "visibility", getattr(lm, "presence", 0.0)) or 0.0)
            if conf == 0.0:
                conf = float(getattr(lm, "presence", 0.9) or 0.9)
            points.append(
                Keypoint(
                    name=name,
                    x=float(lm.x),
                    y=float(lm.y),
                    confidence=conf,
                )
            )
        return PoseResult.from_keypoints(
            points,
            timestamp=timestamp,
            image_width=0,
            image_height=0,
            is_front_camera=is_front_camera,
        )

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None


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
