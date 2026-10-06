from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime

import numpy as np

from jiandong_ai.ai.pose.mediapipe_detector import MediaPipePoseDetector
from jiandong_ai.ai.pose.pose_result import PoseResult


class LivePoseSession:
    """OpenCV camera → MediaPipe detect with FPS throttle & busy-skip."""

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
        self._detector = MediaPipePoseDetector()
        self._cap = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._busy = False
        self._last_infer = 0.0
        self._on_frame: Callable[[np.ndarray, PoseResult], None] | None = None
        self._latest_frame: np.ndarray | None = None
        self._latest_pose = PoseResult.empty()
        self._lock = threading.Lock()

    @property
    def detector_available(self) -> bool:
        return self._detector.available

    @property
    def detector_error(self) -> str | None:
        return self._detector.init_error

    def set_listener(self, cb: Callable[[np.ndarray, PoseResult], None] | None) -> None:
        self._on_frame = cb

    def start(self) -> bool:
        if self._running:
            return True
        try:
            import cv2

            self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                self._cap = cv2.VideoCapture(self.camera_index)
            if not self._cap.isOpened():
                return False
        except Exception:
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def switch_camera(self) -> None:
        self.stop()
        self.is_front_camera = not self.is_front_camera
        # Simple toggle between 0/1 for desktop webcams.
        self.camera_index = 1 if self.camera_index == 0 else 0
        self.start()

    def pause(self) -> None:
        self._running = False

    def resume(self) -> None:
        if self._cap is None:
            self.start()
        else:
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
