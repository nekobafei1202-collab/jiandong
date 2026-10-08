"""RTMPose detector via rtmlib Wholebody — Good-GYM lightweight ONNX pair."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np

from .keypoint import Keypoint, KeypointName
from .pose_detector import PoseDetector
from .pose_result import PoseResult

# COCO-17 order matches Good-GYM / rtmlib body keypoints.
_COCO17_ORDER: tuple[KeypointName, ...] = (
    KeypointName.nose,
    KeypointName.leftEye,
    KeypointName.rightEye,
    KeypointName.leftEar,
    KeypointName.rightEar,
    KeypointName.leftShoulder,
    KeypointName.rightShoulder,
    KeypointName.leftElbow,
    KeypointName.rightElbow,
    KeypointName.leftWrist,
    KeypointName.rightWrist,
    KeypointName.leftHip,
    KeypointName.rightHip,
    KeypointName.leftKnee,
    KeypointName.rightKnee,
    KeypointName.leftAnkle,
    KeypointName.rightAnkle,
)

DET_NAME = "yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx"
POSE_NAME = "rtmpose-t_simcc-body7_pt-body7_420e-256x192-026a1439_20230504.onnx"


def _default_models_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "models"


class RtmPoseDetector(PoseDetector):
    """Desktop detector: YOLOX-nano + RTMPose-t (onnxruntime / rtmlib)."""

    def __init__(
        self,
        *,
        models_dir: str | Path | None = None,
        conf_threshold: float = 0.5,
        backend: str = "onnxruntime",
        device: str = "cpu",
    ) -> None:
        self._wholebody = None
        self._init_error: str | None = None
        self._conf_threshold = conf_threshold
        root = Path(models_dir) if models_dir else _default_models_dir()
        det = root / DET_NAME
        pose = root / POSE_NAME
        try:
            if not det.exists() or not pose.exists():
                raise FileNotFoundError(
                    f"RTMPose ONNX missing under {root}. "
                    "Run: python -m jiandong_ai.scripts.download_rtmpose_models"
                )
            from rtmlib import Wholebody

            self._wholebody = Wholebody(
                det=str(det),
                det_input_size=(416, 416),
                pose=str(pose),
                pose_input_size=(192, 256),
                backend=backend,
                device=device,
            )
        except Exception as exc:  # noqa: BLE001
            self._init_error = str(exc)
            self._wholebody = None

    @property
    def available(self) -> bool:
        return self._wholebody is not None

    @property
    def init_error(self) -> str | None:
        return self._init_error

    def detect(
        self,
        frame,
        *,
        timestamp: datetime | None = None,
        is_front_camera: bool = False,
    ) -> PoseResult:
        if self._wholebody is None or frame is None:
            return PoseResult.empty(timestamp=timestamp)
        if not isinstance(frame, np.ndarray):
            return PoseResult.empty(timestamp=timestamp)

        h, w = frame.shape[:2]
        work = frame
        scale = 1.0
        if w > 640 or h > 640:
            scale = min(640 / w, 640 / h)
            import cv2

            work = cv2.resize(frame, (int(w * scale), int(h * scale)))

        try:
            detected, scores = self._wholebody(work)
        except Exception:
            return PoseResult.empty(timestamp=timestamp)

        if detected is None or len(detected) == 0:
            return PoseResult.empty(timestamp=timestamp)

        kps = np.asarray(detected[0], dtype=np.float32)  # (17, 2)
        conf = (
            np.asarray(scores[0], dtype=np.float32)
            if scores is not None
            else np.ones(len(kps), dtype=np.float32)
        )
        if scale != 1.0:
            kps = kps / scale

        points: list[Keypoint] = []
        for i, name in enumerate(_COCO17_ORDER):
            if i >= len(kps):
                break
            c = float(conf[i]) if i < len(conf) else 0.0
            if c < self._conf_threshold:
                continue
            points.append(
                Keypoint(
                    name=name,
                    x=float(kps[i, 0]),
                    y=float(kps[i, 1]),
                    confidence=c,
                )
            )
        return PoseResult.from_keypoints(
            points,
            timestamp=timestamp,
            image_width=float(w),
            image_height=float(h),
            is_front_camera=is_front_camera,
        )

    def close(self) -> None:
        self._wholebody = None
