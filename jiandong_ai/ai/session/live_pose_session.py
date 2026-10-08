"""OpenCV camera → RTMPose (preferred) / MediaPipe detect with FPS throttle."""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime

import numpy as np

from jiandong_ai.ai.pose.pose_result import PoseResult
from jiandong_ai.ai.pose.rtmpose_detector import RtmPoseDetector


def _make_detector():
    det = RtmPoseDetector()
    if det.available:
        return det
    try:
        from jiandong_ai.ai.pose.mediapipe_detector import MediaPipePoseDetector

        fallback = MediaPipePoseDetector()
        if fallback.available:
            return fallback
        # Prefer showing RTMPose error if both fail.
        if det.init_error:
            return det
        return fallback
    except Exception:
        return det


class LivePoseSession:
    """Desktop webcam session. Android uses AndroidBridgePoseSession instead."""

    def __init__(
        self,
        *,
        camera_index: int = 0,
        max_infer_fps: float = 12.0,
        is_front_camera: bool = True,
    ) -> None:
        self.camera_index = camera_index
        self.max_infer_fps = max_infer_fps
        self.is_front_camera = is_front_camera
        self._detector = _make_detector()
        self._cap = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._paused = False
        self._busy = False
        self._last_infer = 0.0
        self._on_frame: Callable[[np.ndarray, PoseResult], None] | None = None
        self._latest_frame: np.ndarray | None = None
        self._latest_pose = PoseResult.empty()
        self._lock = threading.Lock()

    @property
    def detector_available(self) -> bool:
        return bool(getattr(self._detector, "available", False))

    @property
    def detector_error(self) -> str | None:
        return getattr(self._detector, "init_error", None)

    def set_listener(self, cb: Callable[[np.ndarray, PoseResult], None] | None) -> None:
        self._on_frame = cb

    def start(self) -> bool:
        if self._running and not self._paused:
            return True
        try:
            import cv2

            if self._cap is None or not self._cap.isOpened():
                # CAP_DSHOW is Windows-only; other platforms use default backend.
                if sys.platform.startswith("win"):
                    self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                    if not self._cap.isOpened():
                        self._cap = cv2.VideoCapture(self.camera_index)
                else:
                    self._cap = cv2.VideoCapture(self.camera_index)
                if not self._cap.isOpened():
                    return False
        except Exception:
            return False
        self._paused = False
        self._running = True
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        self._paused = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def switch_camera(self) -> None:
        was = self._running and not self._paused
        self.stop()
        self.is_front_camera = not self.is_front_camera
        self.camera_index = 1 if self.camera_index == 0 else 0
        if was:
            self.start()

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        if self._cap is None:
            self.start()
        else:
            self._paused = False
            self._running = True
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()

    def latest(self) -> tuple[np.ndarray | None, PoseResult]:
        with self._lock:
            return self._latest_frame, self._latest_pose

    def _loop(self) -> None:
        import cv2

        min_interval = 1.0 / max(1.0, self.max_infer_fps)
        while self._running and self._cap is not None:
            if self._paused:
                time.sleep(0.05)
                continue
            ok, frame = self._cap.read()
            if not ok or frame is None:
                time.sleep(0.03)
                continue
            if self.is_front_camera:
                frame = cv2.flip(frame, 1)

            now = time.time()
            pose = self._latest_pose
            if not self._busy and (now - self._last_infer) >= min_interval:
                self._busy = True
                self._last_infer = now
                try:
                    pose = self._detector.detect(
                        frame,
                        timestamp=datetime.now(),
                        is_front_camera=self.is_front_camera,
                    )
                finally:
                    self._busy = False

            with self._lock:
                self._latest_frame = frame
                self._latest_pose = pose

            cb = self._on_frame
            if cb is not None:
                try:
                    cb(frame, pose)
                except Exception:
                    pass
            time.sleep(0.001)
