"""Pose-only bridge for the native CameraX + MediaPipe training activity."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from jiandong_ai.ai.pose.mediapipe_detector import BridgePoseDetector
from jiandong_ai.ai.pose.pose_result import PoseResult

_bridge = BridgePoseDetector()


def _default_bridge_dir() -> Path:
    # Must match PoseCameraBridge.kt (external files first, then internal).
    candidates = (
        Path("/storage/emulated/0/Android/data/com.flet.jiandong_ai/files/jiandong_pose"),
        Path("/sdcard/Android/data/com.flet.jiandong_ai/files/jiandong_pose"),
        Path("/data/user/0/com.flet.jiandong_ai/files/jiandong_pose"),
        Path("/data/data/com.flet.jiandong_ai/files/jiandong_pose"),
        Path.home() / "jiandong_pose",
    )
    for candidate in candidates:
        parent = candidate.parent
        try:
            if parent.exists() or candidate.exists():
                candidate.mkdir(parents=True, exist_ok=True)
                return candidate
        except OSError:
            continue
    # Last resort — still prefer the shared external path.
    preferred = candidates[0]
    try:
        preferred.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return preferred


class AndroidBridgePoseSession:
    """Poll stable COCO-17 JSON; pixels stay in the native camera activity."""

    def __init__(
        self,
        *,
        bridge_dir: str | Path | None = None,
        max_infer_fps: float = 12.0,
        is_front_camera: bool = True,
    ) -> None:
        self.bridge_dir = Path(bridge_dir) if bridge_dir else _default_bridge_dir()
        self.max_infer_fps = max_infer_fps
        self.is_front_camera = is_front_camera
        self._thread: threading.Thread | None = None
        self._running = False
        self._paused = False
        self._on_frame: Callable[[object | None, PoseResult], None] | None = None
        self._on_event: Callable[[str, dict], None] | None = None
        self._latest_frame = None
        self._latest_pose = PoseResult.empty()
        self._lock = threading.Lock()
        self._init_error: str | None = None
        self._available = True
        self._action_name = "\u6df1\u8e72"
        self._last_frame_id = -1
        self._last_event_seq = -1

    native_preview = True

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def detector_available(self) -> bool:
        return self._available

    @property
    def detector_error(self) -> str | None:
        return self._init_error

    def set_listener(self, cb: Callable[[object | None, PoseResult], None] | None) -> None:
        self._on_frame = cb

    def set_event_listener(self, cb: Callable[[str, dict], None] | None) -> None:
        self._on_event = cb

    def configure(self, *, action_name: str) -> None:
        self._action_name = action_name or "\u6df1\u8e72"

    def _write_cmd(self, cmd: str) -> None:
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_write_text(self.bridge_dir / "cmd.txt", cmd)

    @staticmethod
    def _atomic_write_text(path: Path, value: str) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(value, encoding="utf-8")
        tmp.replace(path)

    def start(self) -> bool:
        """Open native preview activity; pose counting starts after native「开始拍摄」."""
        try:
            self.bridge_dir.mkdir(parents=True, exist_ok=True)
            event_path = self.bridge_dir / "event.json"
            event_path.unlink(missing_ok=True)
            # Clear any stale sessionDone flag from a previous session.
            (self.bridge_dir / "hud.json").unlink(missing_ok=True)
            self._last_event_seq = -1
            self._last_frame_id = -1
            command = "preview_front" if self.is_front_camera else "preview_back"
            self._write_cmd(f"{command}\t{self._action_name}")
        except Exception as exc:  # noqa: BLE001
            self._init_error = str(exc)
            return False
        # Event loop on; pose frames ignored until begin (native emits no pose yet).
        self._paused = False
        self._running = True
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        self._paused = False
        try:
            self._write_cmd("stop")
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None

    def switch_camera(self) -> None:
        was = self._running and not self._paused
        self.stop()
        self.is_front_camera = not self.is_front_camera
        if was:
            self.start()

    def pause(self) -> None:
        self._paused = True
        try:
            self._write_cmd("pause")
        except Exception:
            pass

    def resume(self) -> None:
        self._paused = False
        self._running = True
        try:
            self._write_cmd("resume_front" if self.is_front_camera else "resume_back")
        except Exception:
            pass
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def latest(self) -> tuple[None, PoseResult]:
        with self._lock:
            return self._latest_frame, self._latest_pose

    def publish_hud(
        self,
        *,
        reps: int,
        score: int,
        title: str,
        subtitle: str,
        unit: str = "\u6b21",
        action: str | None = None,
        set_nav: bool | None = None,
        set_nav_prev: bool | None = None,
        set_nav_next: bool | None = None,
        prev_label: str | None = None,
        next_label: str | None = None,
        guide_only: bool | None = None,
        set_index: int | None = None,
        set_total: int | None = None,
        resting: bool | None = None,
        rest_seconds: int | None = None,
        rest_label: str | None = None,
        rep_target: int | None = None,
        session_done: bool | None = None,
    ) -> None:
        payload = {
            "reps": int(reps),
            "score": int(score),
            "title": str(title or ""),
            "subtitle": str(subtitle or ""),
            "unit": str(unit),
            "timestampMs": int(time.time() * 1000),
        }
        if rep_target is not None:
            payload["repTarget"] = int(rep_target)
        if action is not None:
            payload["action"] = str(action)
        if set_nav is not None:
            payload["setNav"] = bool(set_nav)
        if set_nav_prev is not None:
            payload["setNavPrev"] = bool(set_nav_prev)
        if set_nav_next is not None:
            payload["setNavNext"] = bool(set_nav_next)
        if prev_label is not None:
            payload["prevLabel"] = str(prev_label)
        if next_label is not None:
            payload["nextLabel"] = str(next_label)
        if guide_only is not None:
            payload["guideOnly"] = bool(guide_only)
        if set_index is not None:
            payload["setIndex"] = int(set_index)
        if set_total is not None:
            payload["setTotal"] = int(set_total)
        if resting is not None:
            payload["resting"] = bool(resting)
        if rest_seconds is not None:
            payload["restSeconds"] = int(rest_seconds)
        if rest_label is not None:
            payload["restLabel"] = str(rest_label)
        if session_done is not None:
            payload["sessionDone"] = bool(session_done)
        try:
            self.bridge_dir.mkdir(parents=True, exist_ok=True)
            self._atomic_write_text(
                self.bridge_dir / "hud.json",
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception:
            pass

    def _loop(self) -> None:
        min_interval = 1.0 / max(1.0, self.max_infer_fps)
        last = 0.0
        json_path = self.bridge_dir / "pose.json"
        event_path = self.bridge_dir / "event.json"
        while self._running:
            # Always poll native UI events (back/close/stop) even while paused.
            self._poll_event(event_path)
            if self._paused:
                time.sleep(0.05)
                continue
            now = time.time()
            if now - last < min_interval:
                time.sleep(0.01)
                continue
            last = now
            pose = None
            if json_path.exists():
                try:
                    payload = json.loads(json_path.read_text(encoding="utf-8"))
                    frame_id = int(payload.get("frameId", -1))
                    if frame_id == self._last_frame_id:
                        time.sleep(0.01)
                        continue
                    self._last_frame_id = frame_id
                    payload["isFrontCamera"] = self.is_front_camera
                    pose = _bridge.detect(payload, timestamp=datetime.now())
                except Exception:
                    pose = None
            if pose is None:
                time.sleep(0.02)
                continue

            with self._lock:
                self._latest_pose = pose
            cb = self._on_frame
            if cb is not None:
                try:
                    cb(None, pose)
                except Exception:
                    pass

    def _poll_event(self, event_path: Path) -> None:
        if not event_path.exists():
            return
        try:
            payload = json.loads(event_path.read_text(encoding="utf-8"))
            seq = int(payload.get("seq", -1))
            if seq == self._last_event_seq:
                return
            self._last_event_seq = seq
            event = str(payload.get("type", ""))
            if event == "switch":
                self.is_front_camera = bool(payload.get("front", self.is_front_camera))
            cb = self._on_event
            if event and cb is not None:
                cb(event, payload)
        except Exception:
            pass


def is_android_runtime() -> bool:
    try:
        import flet as ft
        from flet.controls.context import context

        page = context.page
        plat = getattr(page, "platform", None)
        if plat is None:
            return False
        name = str(plat).lower()
        return "android" in name
    except Exception:
        return False


def create_pose_session(*, is_front_camera: bool = True):
    if is_android_runtime():
        return AndroidBridgePoseSession(is_front_camera=is_front_camera)
    from jiandong_ai.ai.session.live_pose_session import LivePoseSession

    return LivePoseSession(is_front_camera=is_front_camera)
