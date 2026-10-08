"""PNG sequence demo pane for training HUD (Flet port of DemoGuidePane)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import flet as ft

from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.app.theme import HUD_SURFACE_MUTED, HUD_TEXT_SECONDARY
from jiandong_ai.widgets.course_cover import asset_src


class DemoGuidePane(ft.Container):
    APPROVED_STATUS = "validated"
    EXPECTED_PUSHUP_VERSION = "4"

    def __init__(self, *, exercise_id: str | None = None, height: float = 160) -> None:
        super().__init__(
            height=height,
            bgcolor=HUD_SURFACE_MUTED,
            border_radius=16,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            alignment=ft.Alignment.CENTER,
        )
        self._exercise_id = exercise_id
        self._frames: list[str] = []
        self._index = 0
        self._timer: threading.Timer | None = None
        # Flet 1.0 requires src= at construction time.
        self._image = ft.Image(src="", fit=ft.BoxFit.CONTAIN, expand=True)
        self._placeholder = ft.Text("演示动作加载中…", color=HUD_TEXT_SECONDARY, size=13)
        self.content = self._placeholder
        self._load_frames()

    def set_exercise(self, exercise_id: str | None) -> None:
        self._exercise_id = exercise_id
        self._stop()
        self._load_frames()

    def dispose(self) -> None:
        self._stop()

    def _stop(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _assets_root(self) -> Path:
        return Path(__file__).resolve().parents[2] / "assets"

    def _dir_for(self) -> Path | None:
        rel = ExerciseKind.demo_asset_dir(self._exercise_id)
        if not rel:
            return None
        src = asset_src(rel) or rel
        return self._assets_root() / src

    @classmethod
    def _pushup_ok(cls, manifest: dict) -> bool:
        status = str(manifest.get("status", "")).strip().lower()
        if status != cls.APPROVED_STATUS:
            return False
        ver = manifest.get("version")
        label = str(int(ver)) if isinstance(ver, float) and ver == int(ver) else str(ver).strip()
        return label == cls.EXPECTED_PUSHUP_VERSION

    def _load_frames(self) -> None:
        self._frames = []
        self._index = 0
        d = self._dir_for()
        if d is None or not d.is_dir():
            self.content = ft.Text("暂无动作演示", color=HUD_TEXT_SECONDARY, size=13)
            return
        manifest_path = d / "manifest.json"
        frames: list[str] = []
        if manifest_path.is_file():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            if "pushup_white_mannequin" in str(d) and not self._pushup_ok(data):
                self.content = ft.Text("演示包未就绪", color=HUD_TEXT_SECONDARY, size=13)
                return
            raw = data.get("frames") or data.get("files") or []
            for item in raw:
                name = item if isinstance(item, str) else (item.get("file") or item.get("name") or "")
                if name and str(name).lower().endswith(".png"):
                    frames.append(str(name))
        if not frames:
            frames = sorted(p.name for p in d.glob("*.png"))
        # Prefer Flet asset-relative paths for Image src
        rel_dir = asset_src(ExerciseKind.demo_asset_dir(self._exercise_id) or "") or ""
        self._frames = [f"{rel_dir}/{f}" for f in frames if (d / f).is_file()]
        if not self._frames:
            self.content = ft.Text("暂无动作演示", color=HUD_TEXT_SECONDARY, size=13)
            return
        self._image.src = self._frames[0]
        self.content = self._image
        self._schedule_next(max(1, int(2200 / max(len(self._frames), 1))) / 1000)

    def _schedule_next(self, interval: float) -> None:
        self._stop()

        def tick() -> None:
            if not self._frames:
                return
            self._index = (self._index + 1) % len(self._frames)
            self._image.src = self._frames[self._index]
            try:
                self._image.update()
            except Exception:
                pass
            self._schedule_next(interval)

        self._timer = threading.Timer(interval, tick)
        self._timer.daemon = True
        self._timer.start()
