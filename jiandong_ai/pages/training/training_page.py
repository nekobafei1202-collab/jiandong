from __future__ import annotations

import math
import threading
import time
from datetime import datetime

import flet as ft

from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.ai.action.pushup_config import PushupConfig
from jiandong_ai.ai.session.android_bridge_session import create_pose_session
from jiandong_ai.ai.session.course_action_queue import CourseActionQueue
from jiandong_ai.ai.session.training_pipeline import TrainingPipeline
from jiandong_ai.app.theme import HUD_CANVAS
from jiandong_ai.models import RecordAction, TrainingRecord
from jiandong_ai.services.action_guide_catalog import ActionGuideCatalog
from jiandong_ai.services.mock_service import MockService
from jiandong_ai.widgets.muscle_map import write_muscle_svgs
from jiandong_ai.widgets.pose_overlay import draw_pose_overlay, frame_to_image_src, placeholder_image
from jiandong_ai.widgets.safe_area import safe_area
from jiandong_ai.widgets.training_hud import (
    build_bottom_controls,
    build_correction_banner,
    build_demo_window,
    build_effort_pill,
    build_finished_summary,
    build_posture_ring,
    build_rep_counter,
    build_rest_countdown,
    build_session_summary_text,
    build_set_nav,
    build_top_bar,
)

# Chinese UI strings via escapes (avoid encoding corruption on Windows tooling).
_SQUAT = "\u6df1\u8e72"
_ENGINE_TITLE = "\u59ff\u6001\u5f15\u64ce\u672a\u5c31\u7eea"
_ENGINE_HINT = "\u8bf7\u5b89\u88c5 RTMPose / onnxruntime\uff08desktop\uff09"
_CAM_TITLE = "\u6444\u50cf\u5934\u5f02\u5e38"
_CAM_HINT = "\u65e0\u6cd5\u6253\u5f00\u6444\u50cf\u5934\uff0c\u8bf7\u68c0\u67e5\u8bbe\u5907\u6743\u9650"
_TARGET_REPS = 10
_SETS_PER_ACTION = 4
_LABEL_PREV_SET = "\u4e0a\u4e00\u7ec4"
_LABEL_NEXT_SET = "\u4e0b\u4e00\u7ec4"
_LABEL_PREV_ACT = "\u4e0a\u4e00\u4e2a"
_LABEL_NEXT_ACT = "\u4e0b\u4e00\u4e2a"
_LABEL_SKIP_REST = "\u8df3\u8fc7\u4f11\u606f"
_LABEL_FINISH = "\u5b8c\u6210"
_REST_LABEL_SET = "\u7ec4\u95f4\u4f11\u606f"
_REST_LABEL_ACTION = "\u52a8\u4f5c\u5207\u6362"
_ENDED = "\u8bad\u7ec3\u5df2\u7ed3\u675f"


def plan_rest_after_set(
    *,
    action_name: str,
    set_index: int,
    sets_per_action: int = _SETS_PER_ACTION,
    next_action: str | None,
) -> tuple[str, int] | None:
    """Return (after, seconds) for rest, or None to proceed immediately.

    after is ``next_set`` (more sets remain) or ``advance`` (inter-action).
    """
    if ExerciseKind.is_guide_only(action_name):
        return None
    seconds = ExerciseKind.rest_seconds(action_name)
    if seconds <= 0:
        return None
    if set_index < sets_per_action:
        return ("next_set", seconds)
    if next_action is None or ExerciseKind.is_guide_only(next_action):
        return None
    return ("advance", seconds)


def compute_nav_mode(
    *,
    guide_only: bool,
    set_index: int,
    sets_per_action: int = _SETS_PER_ACTION,
    has_previous: bool,
    has_next: bool = True,
) -> dict:
    """Labels + behavior flags for bottom set/action navigation."""
    if guide_only:
        return {
            "prev_label": _LABEL_PREV_ACT,
            "next_label": _LABEL_NEXT_ACT,
            "prev_is_action": True,
            "next_is_action": True,
            "can_prev": has_previous,
            "can_next": True,
        }
    if set_index <= 1:
        return {
            "prev_label": _LABEL_PREV_ACT,
            "next_label": _LABEL_NEXT_SET,
            "prev_is_action": True,
            "next_is_action": False,
            "can_prev": has_previous,
            "can_next": True,
        }
    if set_index >= sets_per_action:
        return {
            "prev_label": _LABEL_PREV_SET,
            # Last set of the last action: the next button finishes the session.
            "next_label": _LABEL_NEXT_ACT if has_next else _LABEL_FINISH,
            "prev_is_action": False,
            "next_is_action": True,
            "can_prev": True,
            "can_next": True,
        }
    return {
        "prev_label": _LABEL_PREV_SET,
        "next_label": _LABEL_NEXT_SET,
        "prev_is_action": False,
        "next_is_action": False,
        "can_prev": True,
        "can_next": True,
    }
_SHARE_SOON = "\u5206\u4eab\u529f\u80fd\u5373\u5c06\u5f00\u653e"
_DOWNLOAD_SOON = "\u4e0b\u8f7d\u529f\u80fd\u5373\u5c06\u5f00\u653e"
_TODAY_PLAN = "\u4eca\u65e5\u8ba1\u5212"
_SESSION_FALLBACK = "\u8bad\u7ec3"
_GUIDE_TITLE = "\u5f15\u5bfc\u52a8\u4f5c"
_GUIDE_HINT = "\u6309\u63d0\u793a\u5b8c\u6210\uff0c\u65e0\u9700\u8ba1\u6570\u4e0e\u8bc4\u5206\uff1b\u5b8c\u6210\u540e\u70b9\u300c\u7ee7\u7eed\u300d\u3002"


class TrainingView(ft.Container):
    """Fullscreen camera Stack: preview + vignette + HUD + finished summary."""

    def __init__(self, page: ft.Page, *, on_close=None) -> None:
        super().__init__(expand=True, bgcolor=HUD_CANVAS, padding=0)
        self._host = page
        self.on_close = on_close
        self._svc = MockService.instance()
        self._queue = CourseActionQueue.from_args(action_name=_SQUAT)
        self._action_name = self._queue.current
        self._session_title = _SESSION_FALLBACK
        self._pipeline = TrainingPipeline(exercise_id="squat")
        self._session = create_pose_session()
        if hasattr(self._session, "set_event_listener"):
            self._session.set_event_listener(self._on_native_event)
        self._last_ui = 0.0
        self._started_at: datetime | None = None
        self._finished_at: datetime | None = None
        self._phase = "idle"  # idle | running | paused | finished
        self._show_demo = True
        self._elapsed = 0
        self._elapsed_anchor = 0.0
        self._elapsed_base = 0
        self._display_reps = 0
        self._avg_quality = 0
        self._calories = 0
        self._set_index = 1
        self._completed_set_reps: list[int] = []
        self._completed_set_scores: list[int] = []
        self._session_sets_completed = 0
        self._record_saved = False
        self._record_id: str | None = None
        self._saving = False
        self._booting = False
        self._cam_error: str | None = None
        self._resting = False
        self._rest_left = 0
        self._rest_after: str | None = None
        self._rest_label = ""
        self._rest_manual = False
        self._rest_timer: threading.Timer | None = None

        self._preview = ft.Image(
            # Native camera path: plain dark placeholder — any text here would
            # flash as a "black page" before the native activity opens.
            src=placeholder_image(text="" if self._uses_native_preview() else None),
            fit=ft.BoxFit.COVER,
            expand=True,
        )
        self._hud_layer = ft.Container(expand=True)
        self._summary_layer = ft.Container(expand=True, visible=False, bgcolor=HUD_CANVAS)
        self._vignette = ft.Container(
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_CENTER,
                end=ft.Alignment.BOTTOM_CENTER,
                colors=["#66000000", "#00000000", "#00000000", "#99000000"],
                stops=[0.0, 0.22, 0.55, 1.0],
            ),
        )

        # Camera + vignette stay edge-to-edge; HUD / summary avoid status bar & home indicator.
        # SafeArea requires its direct content to remain visible. Keep one
        # always-visible Stack and toggle only its grandchildren.
        self._safe_layers = ft.Stack(
            [self._hud_layer, self._summary_layer],
            expand=True,
        )
        self._hud_safe = safe_area(self._safe_layers)
        self.content = ft.Stack(
            [
                ft.Container(expand=True, bgcolor=HUD_CANVAS, content=self._preview),
                self._vignette,
                self._hud_safe,
            ],
            expand=True,
        )
        # Android: avoid painting the old Flet training HUD at construct time.
        if self._uses_native_preview():
            self._quiet_native_host()
        else:
            self._rebuild_hud()

    def _safe_update(self) -> None:
        try:
            # Guard: view may not be mounted yet when set_action is deferred.
            if getattr(self, "page", None) is None and getattr(self, "_host", None) is None:
                return
            self.update()
        except Exception:
            pass

    def set_action(
        self,
        action: str | None = None,
        *,
        actions: list[str] | None = None,
        action_index: int = 0,
        session_title: str | None = None,
    ) -> None:
        if self._phase in {"running", "paused", "preview"}:
            self._stop_session(save=False, finish=False)
        self.prepare_native_entry(
            actions=actions,
            action=action,
            action_index=action_index,
            session_title=session_title,
        )
        if self._uses_native_preview():
            self.launch_native_preview()
        else:
            self._apply_queue_action(reset_preview=True)

    def prepare_native_entry(
        self,
        *,
        actions: list[str] | None = None,
        action: str | None = None,
        action_index: int = 0,
        session_title: str | None = None,
    ) -> None:
        """Prepare today's queue without painting Flet HUD (avoids black flash)."""
        if self._phase in {"running", "paused", "preview"}:
            self._session.set_listener(None)
            self._session.stop()
            self._pipeline.stop()
        self._queue = CourseActionQueue.from_args(
            actions=actions,
            action_name=action or _SQUAT,
            action_index=action_index,
        )
        self._action_name = self._queue.current
        self._session_title = (session_title or "").strip() or self._default_session_title()
        if hasattr(self._session, "configure"):
            self._session.configure(action_name=self._action_name)
        self._phase = "idle"
        self._record_saved = False
        self._show_demo = not ExerciseKind.is_guide_only(self._action_name)
        self._cam_error = None
        self._booting = False
        self._session_sets_completed = 0
        self._reset_set_progress()
        self._sync_pipeline_for_action(start_if_running=False)

    def _uses_native_preview(self) -> bool:
        return bool(getattr(self._session, "native_preview", False))

    def _quiet_native_host(self) -> None:
        """Hide Flet chrome under the native activity without forcing a black flash update."""
        self._vignette.visible = False
        self._hud_layer.visible = False
        self._summary_layer.visible = False

    def launch_native_preview(self) -> bool:
        """Open native camera preview; counting waits for native「开始拍摄」."""
        if not self._uses_native_preview():
            return False
        if not self._session.detector_available:
            return False
        if self._phase in {"preview", "running", "paused"}:
            return True
        self._cam_error = None
        if hasattr(self._session, "configure"):
            self._session.configure(action_name=self._action_name)
        if not self._session.start():
            self._cam_error = _CAM_HINT
            self._phase = "idle"
            return False
        self._quiet_native_host()
        self._phase = "preview"
        self._started_at = None
        self._elapsed_base = 0
        self._elapsed = 0
        self._display_reps = 0
        self._avg_quality = 0
        self._record_saved = False
        self._session_sets_completed = 0
        self._reset_set_progress()
        self._publish_native_queue_state()
        return True

    def _default_session_title(self) -> str:
        if self._queue.is_multi:
            return _TODAY_PLAN if self._queue.total > 1 else _SESSION_FALLBACK
        return ExerciseKind.display_name(self._action_name)

    def _guide_coach_copy(self) -> tuple[str, str]:
        guide = ActionGuideCatalog.for_name(self._action_name)
        title = _GUIDE_TITLE if ExerciseKind.is_guide_only(self._action_name) else guide.name
        subtitle = guide.summary or _GUIDE_HINT
        return title, subtitle

    def _sync_pipeline_for_action(self, *, start_if_running: bool) -> None:
        if ExerciseKind.supports_auto_detect(self._action_name):
            self._pipeline.switch_exercise(ExerciseKind.normalize(self._action_name))
            self._apply_pushup_mode()
            if start_if_running and self._phase in {"running", "paused"}:
                self._pipeline.start()
                if self._phase == "paused":
                    self._pipeline.pause()
        else:
            self._pipeline.stop()

    def _apply_pushup_mode(self) -> None:
        """从全局设置读取严格/轻松模式并热更新俯卧撑配置。"""
        strict = self._svc.get_strict_mode()
        self._pipeline.update_pushup_config(
            PushupConfig() if strict else PushupConfig.lenient()
        )

    def _reset_set_progress(self) -> None:
        self._set_index = 1
        self._completed_set_reps = []
        self._completed_set_scores = []

    def _sets_per_current(self) -> int:
        if ExerciseKind.is_guide_only(self._action_name):
            return 0
        return _SETS_PER_ACTION

    def _reset_pipeline_for_next_set(self) -> None:
        if ExerciseKind.supports_auto_detect(self._action_name):
            self._pipeline.start()
            if self._phase == "paused":
                self._pipeline.pause()

    def _apply_queue_action(self, *, reset_preview: bool = False) -> None:
        self._clear_rest_state()
        self._action_name = self._queue.current
        if hasattr(self._session, "configure"):
            self._session.configure(action_name=self._action_name)
        self._record_saved = False
        self._show_demo = not ExerciseKind.is_guide_only(self._action_name)
        self._reset_set_progress()
        self._cam_error = None
        if reset_preview:
            self._preview.src = placeholder_image()
        if self._uses_native_preview():
            native_open = getattr(self._session, "is_running", False)
            if native_open:
                # Native page stays open: keep counting (running) or stay in
                # preview — only the action label/demo need to switch.
                if self._phase not in {"running", "paused"}:
                    self._phase = "preview"
            else:
                self._phase = "idle"
            live = self._phase in {"running", "paused"}
            self._sync_pipeline_for_action(start_if_running=live)
            if live:
                if ExerciseKind.supports_auto_detect(self._action_name):
                    self._session.set_listener(self._on_frame)
                else:
                    self._session.set_listener(None)
            # Push the new queue state so the native label/demo switch at once —
            # also covers auto-advance while the native page stays open.
            if live and (
                ExerciseKind.is_guide_only(self._action_name)
                or ExerciseKind.is_manual_complete(self._action_name)
            ):
                self._publish_guide_hud()
            else:
                self._publish_native_queue_state()
            if self._session.detector_available and not native_open:
                self.launch_native_preview()
            return
        was_live = self._phase in {"running", "paused"}
        if not was_live:
            self._phase = "idle"
        self._sync_pipeline_for_action(start_if_running=was_live)
        if was_live and ExerciseKind.supports_auto_detect(self._action_name):
            self._session.set_listener(self._on_frame)
        else:
            self._session.set_listener(None)
        self._rebuild_hud()
        self._safe_update()

    def _nav_mode(self) -> dict:
        return compute_nav_mode(
            guide_only=ExerciseKind.is_guide_only(self._action_name),
            set_index=self._set_index,
            sets_per_action=_SETS_PER_ACTION,
            has_previous=self._queue.has_previous,
            has_next=self._queue.has_next,
        )

    def _hud_set_kwargs(self) -> dict:
        guide = ExerciseKind.is_guide_only(self._action_name)
        live = self._phase in {"running", "paused"}
        mode = self._nav_mode()
        if self._resting:
            return {
                "set_index": self._set_index,
                "set_total": _SETS_PER_ACTION,
                "guide_only": True,
                "set_nav": True,
                "set_nav_prev": False,
                "set_nav_next": True,
                "prev_label": mode["prev_label"],
                "next_label": _LABEL_SKIP_REST,
                "resting": True,
                "rest_seconds": self._rest_left,
                "rest_label": self._rest_label,
            }
        base = {
            "resting": False,
            "rest_seconds": 0,
            "rest_label": "",
        }
        if guide:
            return {
                **base,
                "set_index": 0,
                "set_total": 0,
                "guide_only": True,
                "set_nav": live,
                "set_nav_prev": live and mode["can_prev"],
                "set_nav_next": live and mode["can_next"],
                "prev_label": mode["prev_label"],
                "next_label": mode["next_label"],
            }
        return {
            **base,
            # HUD "组 N/M" = current set / target sets.
            "set_index": self._set_index,
            "set_total": _SETS_PER_ACTION,
            "guide_only": False,
            "set_nav": live,
            "set_nav_prev": live and mode["can_prev"],
            "set_nav_next": live and mode["can_next"],
            "prev_label": mode["prev_label"],
            "next_label": mode["next_label"],
        }

    def _publish_native_queue_state(self) -> None:
        if not self._uses_native_preview() or not hasattr(self._session, "publish_hud"):
            return
        name = ExerciseKind.display_name(self._action_name)
        guide = ExerciseKind.is_guide_only(self._action_name)
        title, subtitle = (
            self._guide_coach_copy() if guide else ("准备开始", f"下一个动作：{name}")
        )
        self._session.publish_hud(
            reps=0,
            score=0,
            title=title,
            subtitle=subtitle,
            action=self._action_name,
            **self._hud_set_kwargs(),
        )

    def _publish_guide_hud(self) -> None:
        if not self._uses_native_preview() or not hasattr(self._session, "publish_hud"):
            return
        # No coach copy on guide steps — metrics/banner hidden on native side.
        self._session.publish_hud(
            reps=0,
            score=0,
            title="",
            subtitle="",
            action=self._action_name,
            **self._hud_set_kwargs(),
        )

    def on_show(self) -> None:
        # After a summary, re-enter training → native preview (not sticky summary).
        if self._phase == "finished":
            self._phase = "idle"
            self._summary_layer.visible = False
            self._cam_error = None
            if self._uses_native_preview():
                self.launch_native_preview()
                return
        if not self._session.detector_available and self._phase == "idle":
            self._rebuild_hud(
                coach_title=_ENGINE_TITLE,
                coach_subtitle=self._session.detector_error or _ENGINE_HINT,
            )
            self._safe_update()
            return
        if self._uses_native_preview() and self._phase in {"preview", "running", "paused"}:
            self._quiet_native_host()
            return
        if self._uses_native_preview() and self._phase == "idle" and self._session.detector_available:
            self.launch_native_preview()
            return
        self._rebuild_hud()
        self._safe_update()

    def _begin_after_native_start(self) -> None:
        """Native user tapped「开始拍摄」— start pipeline/timer only now."""
        if self._phase not in {"preview", "idle"}:
            return
        self._started_at = datetime.now()
        self._elapsed_base = 0
        self._elapsed_anchor = time.time()
        self._elapsed = 0
        self._display_reps = 0
        self._avg_quality = 0
        self._record_saved = False
        self._reset_set_progress()
        self._phase = "running"
        if ExerciseKind.supports_auto_detect(self._action_name):
            self._pipeline.start()
            self._session.set_listener(self._on_frame)
        else:
            self._pipeline.stop()
            self._session.set_listener(None)
            self._publish_guide_hud()
        self._quiet_native_host()

    def _start_session(self) -> None:
        """Desktop / manual start. Android uses launch_native_preview + begin event."""
        if self._uses_native_preview():
            self.launch_native_preview()
            return
        self._booting = True
        self._cam_error = None
        self._rebuild_hud()
        self._safe_update()
        if hasattr(self._session, "configure"):
            self._session.configure(action_name=self._action_name)
        if not self._session.start():
            self._booting = False
            self._cam_error = _CAM_HINT
            self._vignette.visible = True
            self._rebuild_hud(coach_title=_CAM_TITLE, coach_subtitle=_CAM_HINT)
            self._safe_update()
            return
        self._booting = False
        self._started_at = datetime.now()
        self._elapsed_base = 0
        self._elapsed_anchor = time.time()
        self._elapsed = 0
        self._display_reps = 0
        self._avg_quality = 0
        self._record_saved = False
        self._reset_set_progress()
        self._phase = "running"
        if ExerciseKind.supports_auto_detect(self._action_name):
            self._pipeline.start()
            self._session.set_listener(self._on_frame)
            self._rebuild_hud()
        else:
            self._pipeline.stop()
            self._session.set_listener(None)
            self._rebuild_hud()
        self._safe_update()

    def _pause_session(self) -> None:
        if self._phase != "running":
            return
        self._elapsed_base = self._current_elapsed()
        if ExerciseKind.supports_auto_detect(self._action_name):
            self._pipeline.pause()
        if hasattr(self._session, "pause"):
            self._session.pause()
        self._session.set_listener(None)
        self._phase = "paused"
        if self._uses_native_preview():
            if self._resting:
                self._publish_rest_hud()
            elif ExerciseKind.is_guide_only(self._action_name):
                self._publish_guide_hud()
            self._quiet_native_host()
        else:
            self._rebuild_hud()
            self._safe_update()

    def _resume_session(self) -> None:
        if self._phase != "paused":
            return
        self._elapsed_anchor = time.time()
        if hasattr(self._session, "resume"):
            self._session.resume()
        self._phase = "running"
        if self._resting:
            if self._uses_native_preview():
                self._publish_rest_hud()
                self._quiet_native_host()
            else:
                self._rebuild_hud()
                self._safe_update()
            return
        if ExerciseKind.supports_auto_detect(self._action_name):
            self._pipeline.resume()
            self._session.set_listener(self._on_frame)
        else:
            self._session.set_listener(None)
            if self._uses_native_preview():
                self._publish_guide_hud()
        if self._uses_native_preview():
            self._quiet_native_host()
        else:
            self._rebuild_hud()
            self._safe_update()

    def _live_set_reps(self) -> int:
        if ExerciseKind.is_guide_only(self._action_name):
            return 0
        if self._pipeline.completes_by_hold:
            # A finished hold counts as 1; in-progress shows seconds on HUD only.
            if self._pipeline.action.just_completed_rep or (
                self._pipeline.action.rep_count or 0
            ) > 0:
                return int(self._pipeline.action.rep_count or 0)
            return 0
        return int(self._pipeline.action.rep_count or 0)

    def _live_set_score(self) -> int | None:
        score = self._pipeline.evaluation.score or self._avg_quality or None
        if score is not None and score <= 0:
            return None
        return score

    def _current_action_snapshot(self) -> tuple[int, int | None]:
        if ExerciseKind.is_guide_only(self._action_name):
            return 0, None
        total_reps = sum(self._completed_set_reps) + self._live_set_reps()
        scores = list(self._completed_set_scores)
        live = self._live_set_score()
        if live is not None:
            scores.append(live)
        avg = round(sum(scores) / len(scores)) if scores else None
        return total_reps, avg

    def _seal_current_set(self) -> None:
        reps = self._live_set_reps()
        score = self._live_set_score()
        self._completed_set_reps.append(reps)
        if score is not None:
            self._completed_set_scores.append(score)
        self._session_sets_completed += 1

    def _rep_target(self) -> int:
        if self._pipeline.completes_by_hold:
            return max(1, int(self._pipeline.hold_target_ms / 1000))
        return _TARGET_REPS

    def _set_coach_copy(self) -> tuple[str, str, str]:
        hold = self._pipeline.completes_by_hold
        if hold:
            target = self._rep_target()
            subtitle = f"目标 {target} 秒，继续保持"
            unit = "\u79d2"
        else:
            subtitle = f"目标 {_TARGET_REPS} 次，继续保持"
            unit = "\u6b21"
        return f"第 {self._set_index} 组", subtitle, unit

    def _refresh_after_set_change(self) -> None:
        title, subtitle, unit = self._set_coach_copy()
        if self._uses_native_preview():
            self._session.publish_hud(
                reps=0,
                score=0,
                title=title,
                subtitle=subtitle,
                unit=unit,
                action=self._action_name,
                rep_target=self._rep_target(),
                **self._hud_set_kwargs(),
            )
        else:
            self._rebuild_hud(
                coach_title=title,
                coach_subtitle=subtitle,
                reps=0,
                score=0,
            )
            self._safe_update()

    def _set_previous(self) -> None:
        if ExerciseKind.is_guide_only(self._action_name):
            return
        if self._phase not in {"running", "paused"}:
            return
        if self._set_index <= 1:
            return
        n_reps = len(self._completed_set_reps)
        n_scores = len(self._completed_set_scores)
        if self._completed_set_reps:
            self._completed_set_reps.pop()
            if n_scores == n_reps and self._completed_set_scores:
                self._completed_set_scores.pop()
        self._session_sets_completed = max(0, self._session_sets_completed - 1)
        self._set_index -= 1
        self._reset_pipeline_for_next_set()
        self._refresh_after_set_change()

    def _deduct_sets_for_popped(self, popped) -> None:
        if popped is None or ExerciseKind.is_guide_only(popped.action_name):
            return
        if popped.reps <= 0:
            return
        deduct = max(
            1,
            min(_SETS_PER_ACTION, (popped.reps + _TARGET_REPS - 1) // _TARGET_REPS),
        )
        self._session_sets_completed = max(0, self._session_sets_completed - deduct)

    def _goto_previous_action(self) -> None:
        """Leave current action and reopen the previous queue action."""
        if self._phase not in {"running", "paused"}:
            return
        if not self._queue.has_previous:
            return
        self._clear_rest_state()
        prev_name = ExerciseKind.display_name(
            self._queue.actions[self._queue.index - 1]
        )
        has_work = bool(self._completed_set_reps) or self._live_set_reps() > 0
        if has_work and not self._queue.current_visit_recorded:
            self._flush_current_to_queue()
        else:
            last = self._queue.peek_last_completed()
            if last is not None and last.action_name == prev_name:
                popped = self._queue.pop_last_completed()
                self._deduct_sets_for_popped(popped)
        if not self._queue.previous():
            return
        self._apply_queue_action(reset_preview=True)

    def _on_nav_previous(self) -> None:
        if self._resting:
            return
        mode = self._nav_mode()
        if mode["prev_is_action"]:
            self._goto_previous_action()
        else:
            self._set_previous()

    def _on_nav_next(self) -> None:
        if self._resting:
            self._skip_rest()
            return
        self._complete_set_or_advance(manual=True)

    def _cancel_rest_timer(self) -> None:
        timer = self._rest_timer
        self._rest_timer = None
        if timer is not None:
            timer.cancel()

    def _clear_rest_state(self) -> None:
        self._cancel_rest_timer()
        self._resting = False
        self._rest_left = 0
        self._rest_after = None
        self._rest_label = ""
        self._rest_manual = False

    def _publish_rest_hud(self) -> None:
        if self._uses_native_preview() and hasattr(self._session, "publish_hud"):
            self._session.publish_hud(
                reps=0,
                score=0,
                title=self._rest_label,
                subtitle=str(self._rest_left),
                action=self._action_name,
                **self._hud_set_kwargs(),
            )
            return
        self._rebuild_hud(
            coach_title=self._rest_label,
            coach_subtitle=str(self._rest_left),
            reps=0,
            score=0,
        )
        self._safe_update()

    def _schedule_rest_tick(self) -> None:
        self._cancel_rest_timer()
        if not self._resting:
            return
        self._rest_timer = threading.Timer(1.0, self._on_rest_tick)
        self._rest_timer.daemon = True
        self._rest_timer.start()

    def _on_rest_tick(self) -> None:
        def apply() -> None:
            if not self._resting:
                return
            self._rest_left -= 1
            if self._rest_left <= 0:
                self._finish_rest()
                return
            self._publish_rest_hud()
            self._schedule_rest_tick()

        try:
            self._host.run_thread(apply)
        except Exception:
            apply()

    def _enter_rest(self, *, after: str, seconds: int, manual: bool) -> None:
        self._cancel_rest_timer()
        self._resting = True
        self._rest_left = max(1, int(seconds))
        self._rest_after = after
        self._rest_manual = manual
        self._rest_label = (
            _REST_LABEL_SET if after == "next_set" else _REST_LABEL_ACTION
        )
        if ExerciseKind.supports_auto_detect(self._action_name):
            self._pipeline.pause()
        self._session.set_listener(None)
        self._publish_rest_hud()
        self._schedule_rest_tick()

    def _finish_rest(self) -> None:
        if not self._resting:
            return
        after = self._rest_after
        manual = self._rest_manual
        self._clear_rest_state()
        if after == "next_set":
            self._set_index += 1
            self._reset_pipeline_for_next_set()
            if self._phase == "running" and ExerciseKind.supports_auto_detect(
                self._action_name
            ):
                self._pipeline.resume()
                self._session.set_listener(self._on_frame)
            self._refresh_after_set_change()
            return
        # Clear live counters so snapshot is only sealed sets (no double-count).
        self._reset_pipeline_for_next_set()
        self._advance_or_finish(manual=manual)

    def _skip_rest(self) -> None:
        self._cancel_rest_timer()
        self._finish_rest()

    def _complete_set_or_advance(self, *, manual: bool) -> None:
        if self._resting:
            return
        if ExerciseKind.is_guide_only(self._action_name):
            self._advance_or_finish(manual=manual)
            return
        self._seal_current_set()
        next_action = (
            self._queue.actions[self._queue.index + 1]
            if self._queue.has_next
            else None
        )
        planned = plan_rest_after_set(
            action_name=self._action_name,
            set_index=self._set_index,
            sets_per_action=_SETS_PER_ACTION,
            next_action=next_action,
        )
        if planned is not None:
            after, seconds = planned
            self._enter_rest(after=after, seconds=seconds, manual=manual)
            return
        if self._set_index < _SETS_PER_ACTION:
            self._set_index += 1
            self._reset_pipeline_for_next_set()
            self._refresh_after_set_change()
            return
        # Clear live counters so snapshot is only sealed sets (no double-count).
        self._reset_pipeline_for_next_set()
        self._advance_or_finish(manual=manual)

    def _flush_current_to_queue(self) -> None:
        if self._queue.current_visit_recorded:
            return
        # Count an in-progress set toward session totals if it has work.
        if (
            not ExerciseKind.is_guide_only(self._action_name)
            and self._live_set_reps() > 0
        ):
            self._session_sets_completed += 1
        reps, score = self._current_action_snapshot()
        self._queue.record_current_only(
            reps=reps,
            avg_score=score,
            manual=ExerciseKind.is_manual_complete(self._action_name),
        )

    def _stop_session(self, *, save: bool, finish: bool = True) -> None:
        self._clear_rest_state()
        self._session.set_listener(None)
        self._session.stop()
        if save and self._started_at is not None:
            self._flush_current_to_queue()
        self._pipeline.stop()
        self._elapsed = self._current_elapsed()
        self._display_reps = self._queue.total_reps
        self._avg_quality = self._queue.average_score or 0
        self._calories = max(1, self._elapsed // 15) * 4
        self._finished_at = datetime.now()
        self._preview.src = placeholder_image(text=_ENDED)
        self._vignette.visible = True
        if finish:
            self._phase = "finished"
            if self._uses_native_preview() and hasattr(self._session, "publish_hud"):
                # Tell the native activity the session is done so it closes
                # itself and reveals the summary page underneath.
                self._session.publish_hud(
                    reps=0, score=0, title="", subtitle="", session_done=True
                )
            self._rebuild_summary()
        else:
            self._phase = "idle"
            if self._uses_native_preview():
                self._quiet_native_host()
            else:
                self._rebuild_hud()
        if save and self._started_at is not None and not self._record_saved:
            self._persist_record()
        self._safe_update()

    def _persist_record(self) -> None:
        if self._record_saved or self._started_at is None:
            return
        self._flush_current_to_queue()
        self._display_reps = self._queue.total_reps
        self._avg_quality = self._queue.average_score or 0
        self._saving = True
        self._rebuild_summary()
        self._safe_update()
        minutes = max(1, int(self._elapsed // 60) or 1)
        for item in self._queue.completed:
            self._svc.mark_plan_done(item.action_name)
        self._svc.mark_plan_done(self._action_name)
        actions = tuple(
            RecordAction(
                action_name=item.action_name,
                reps=item.reps,
                avg_score=item.avg_score,
                feedback=None,
            )
            for item in self._queue.completed
        )
        record_id = f"r_{int(time.time() * 1000)}"
        self._svc.add_training_record(
            TrainingRecord(
                id=record_id,
                exercise_name=self._session_title or self._default_session_title(),
                duration=minutes,
                score=self._avg_quality,
                date=datetime.now().isoformat(),
                calories=self._calories,
                total_reps=self._display_reps,
                actions=actions,
            )
        )
        self._record_id = record_id
        self._record_saved = True
        self._saving = False
        self._rebuild_summary()
        self._safe_update()

    def _advance_or_finish(self, *, manual: bool) -> None:
        self._svc.mark_plan_done(self._action_name)
        reps, score = self._current_action_snapshot()
        advanced = self._queue.complete_current_and_advance(
            reps=reps, avg_score=score, manual=manual
        )
        if advanced:
            if not self._uses_native_preview():
                self._session.set_listener(None)
                self._session.stop()
                self._pipeline.stop()
            # Native: keep the bridge session/pipeline alive — the page stays
            # open and the new action starts counting seamlessly.
            self._apply_queue_action(reset_preview=True)
            return
        self._stop_session(save=True, finish=True)

    def _manual_complete(self) -> None:
        self._complete_set_or_advance(manual=True)

    def _confirm_end_and_finish(self) -> None:
        dlg = ft.AlertDialog(
            title=ft.Text("结束训练？"),
            content=ft.Text("结束后可查看训练总结，并可选择保存记录。"),
            actions=[
                ft.TextButton("取消", on_click=lambda e: self._close_dlg()),
                ft.TextButton("结束", on_click=self._confirm_end),
            ],
        )
        self._open_dlg(dlg)

    def _confirm_end(self, _: ft.ControlEvent | None = None) -> None:
        self._close_dlg()
        if self._phase in {"running", "paused"}:
            self._stop_session(save=True, finish=True)

    def _queue_previous(self) -> None:
        if self._phase in {"running", "paused"}:
            return
        if self._queue.previous():
            self._apply_queue_action(reset_preview=True)

    def _queue_next(self) -> None:
        if self._phase in {"running", "paused"}:
            return
        if self._queue.has_next and self._queue.go_to(self._queue.index + 1):
            self._apply_queue_action(reset_preview=True)

    def _pick_action(self) -> None:
        if not self._queue.is_multi:
            return
        options = [
            ft.TextButton(
                self._queue.actions[i],
                on_click=lambda e, idx=i: self._pick_index(idx),
            )
            for i in range(self._queue.total)
        ]
        dlg = ft.AlertDialog(
            title=ft.Text("选择动作"),
            content=ft.Column(options, tight=True, scroll=ft.ScrollMode.AUTO, height=240),
            actions=[ft.TextButton("关闭", on_click=lambda e: self._close_dlg())],
        )
        self._open_dlg(dlg)

    def _pick_index(self, idx: int) -> None:
        self._close_dlg()
        if self._queue.go_to(idx):
            self._apply_queue_action(reset_preview=True)

    def _open_dlg(self, dlg: ft.AlertDialog) -> None:
        self._dlg = dlg
        self._host.show_dialog(dlg)

    def _close_dlg(self) -> None:
        dlg = getattr(self, "_dlg", None)
        if dlg is not None:
            self._dlg = None
            dlg.open = False
            try:
                dlg.update()
            except Exception:
                pass

    @staticmethod
    def _coach_is_warning(title: str | None, subtitle: str | None) -> bool:
        text = f"{title or ''}{subtitle or ''}"
        good = ("很好", "不错", "完美", "标准", "保持", "完成")
        return not any(g in text for g in good)

    def _switch_cam(self) -> None:
        was = self._phase == "running"
        self._session.switch_camera()
        if was:
            self._session.set_listener(self._on_frame)

    def _close(self) -> None:
        if self._phase in {"running", "paused", "preview"}:
            self._stop_session(save=False, finish=False)
        elif self._phase == "finished":
            self._phase = "idle"
            self._summary_layer.visible = False
        if self.on_close:
            self.on_close()

    def _current_elapsed(self) -> int:
        if self._phase == "running":
            return self._elapsed_base + int(time.time() - self._elapsed_anchor)
        if self._phase == "paused":
            return self._elapsed_base
        if self._phase == "finished":
            return self._elapsed
        return 0

    def _on_frame(self, frame, pose) -> None:
        if self._phase != "running" or self._resting:
            return
        coach = self._pipeline.process_pose(pose)
        score = self._pipeline.evaluation.score or 0
        reps = self._pipeline.action.rep_count
        self._elapsed = self._current_elapsed()
        if score > 0:
            self._avg_quality = score

        # Goal reached → complete current set (or advance after 4 sets).
        if self._pipeline.action.just_completed_rep and not ExerciseKind.is_manual_complete(
            self._action_name
        ):
            goal_reached = self._pipeline.completes_by_hold or reps >= _TARGET_REPS
            if goal_reached:
                def advance() -> None:
                    if self._phase == "running":
                        self._complete_set_or_advance(manual=False)

                if self._host:
                    try:
                        self._host.run_thread(advance)
                        return
                    except Exception:
                        pass
                advance()
                return

        # Android owns preview, skeleton and HUD. Only publish compact metrics.
        if getattr(self._session, "native_preview", False):
            hold = self._pipeline.completes_by_hold
            display_reps = (
                int(self._pipeline.hold_elapsed_ms / 1000) if hold else reps
            )
            self._session.publish_hud(
                reps=display_reps,
                score=score,
                title=coach.status_text,
                subtitle=coach.message,
                unit="\u79d2" if hold else "\u6b21",
                action=self._action_name,
                rep_target=self._rep_target(),
                **self._hud_set_kwargs(),
            )
            return

        try:
            overlay = draw_pose_overlay(frame, pose, vignette=True)
        except Exception:
            overlay = frame
        try:
            src = frame_to_image_src(overlay, quality=70)
        except Exception:
            return
        if not src:
            return
        now = time.time()
        if now - self._last_ui < 0.08:
            return
        self._last_ui = now
        def apply() -> None:
            self._preview.src = src
            self._rebuild_hud(
                coach_title=coach.status_text,
                coach_subtitle=coach.message,
                reps=reps,
                score=score,
            )
            self._safe_update()

        if self._host:
            try:
                self._host.run_thread(apply)
            except Exception:
                apply()

    def _on_native_event(self, event: str, payload: dict) -> None:
        def apply() -> None:
            if event == "begin" and self._phase in {"preview", "idle"}:
                self._begin_after_native_start()
            elif event == "pause" and self._phase == "running":
                self._elapsed_base = self._current_elapsed()
                if ExerciseKind.supports_auto_detect(self._action_name):
                    self._pipeline.pause()
                self._phase = "paused"
                if self._resting:
                    self._publish_rest_hud()
                elif ExerciseKind.is_guide_only(self._action_name):
                    self._publish_guide_hud()
            elif event == "resume" and self._phase == "paused":
                self._elapsed_anchor = time.time()
                self._phase = "running"
                if self._resting:
                    # Stay paused on pipeline until rest ends.
                    self._publish_rest_hud()
                elif ExerciseKind.supports_auto_detect(self._action_name):
                    self._pipeline.resume()
                    self._session.set_listener(self._on_frame)
                else:
                    self._session.set_listener(None)
                    self._publish_guide_hud()
            elif event == "queue_next":
                # 「下一组」/「下一个」/「跳过休息」depending on state.
                if self._resting or self._phase in {"running", "paused"}:
                    self._on_nav_next()
            elif event == "queue_prev":
                # 「上一组」or「上一个」depending on nav mode.
                if self._phase in {"running", "paused"} and not self._resting:
                    self._on_nav_previous()
            elif event == "stop" and self._phase in {"running", "paused", "preview"}:
                self._stop_session(save=True, finish=True)
            elif event == "close" and self._phase in {"running", "paused", "preview"}:
                self._stop_session(save=False, finish=False)
                if self.on_close:
                    self.on_close()

        try:
            self._host.run_thread(apply)
        except Exception:
            apply()

    def _rebuild_hud(
        self,
        *,
        coach_title: str | None = None,
        coach_subtitle: str | None = None,
        reps: int | None = None,
        score: int | None = None,
    ) -> None:
        if self._phase == "finished":
            self._vignette.visible = True
            self._hud_safe.visible = True
            self._hud_layer.visible = False
            self._summary_layer.visible = True
            return

        # Android native owns the live HUD — never paint the old Flet training chrome.
        if (
            self._uses_native_preview()
            and self._phase in {"preview", "running", "paused"}
            and self._cam_error is None
        ):
            self._quiet_native_host()
            return

        self._vignette.visible = True
        self._hud_safe.visible = True
        self._hud_layer.visible = True
        self._summary_layer.visible = False
        c = self._pipeline.coach
        title = coach_title if coach_title is not None else c.status_text
        subtitle = coach_subtitle if coach_subtitle is not None else c.message
        hold = self._pipeline.completes_by_hold
        if hold:
            rep_count = int(self._pipeline.hold_elapsed_ms / 1000)
            unit = "\u79d2"
            effort_done = rep_count
            effort_target = max(1, int(self._pipeline.hold_target_ms / 1000))
        else:
            rep_count = reps if reps is not None else self._pipeline.action.rep_count
            unit = "\u6b21"
            effort_done = rep_count
            effort_target = _TARGET_REPS
        is_guide = ExerciseKind.is_guide_only(self._action_name)
        is_manual = ExerciseKind.is_manual_complete(self._action_name)
        live_score = score if score is not None else (self._pipeline.evaluation.score or 0)
        has_score = (
            (not is_guide)
            and (not self._resting)
            and live_score > 0
            and self._phase in {"running", "paused"}
        )
        ai_active = self._phase == "running" and not is_manual and not self._resting
        recording = self._phase in {"running", "paused"}
        # Display current set / target (e.g. 1/4 … 4/4).
        set_index = self._set_index
        set_total = self._sets_per_current() or None
        mid: list[ft.Control] = []
        if self._resting:
            mid.append(
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=build_rest_countdown(
                        seconds=self._rest_left,
                        label=self._rest_label,
                    ),
                )
            )
        # Guide-only (热身/拉伸): hide sets/reps/score metrics entirely.
        elif self._phase != "idle" and not is_guide:
            if self._show_demo:
                try:
                    demo = build_demo_window(
                        on_close=self._hide_demo,
                        exercise_id=self._action_name,
                    )
                except Exception:
                    demo = ft.Container(width=8)
            else:
                demo = ft.Container(width=8)
            mid.append(
                ft.Row(
                    [
                        demo,
                        ft.Container(
                            expand=True,
                            padding=ft.Padding.only(top=4),
                            content=build_rep_counter(
                                set_index=set_index,
                                set_total=set_total,
                                rep_count=rep_count,
                                rep_target=effort_target,
                                unit=unit,
                            ),
                            alignment=ft.Alignment.CENTER,
                        ),
                        build_posture_ring(
                            score=live_score or self._avg_quality,
                            has_score=has_score,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            )
            if self._phase in {"running", "paused"}:
                mid.append(ft.Container(height=12))
                mid.append(
                    ft.Row(
                        [build_effort_pill(completed=effort_done, target=effort_target)],
                        alignment=ft.MainAxisAlignment.CENTER,
                    )
                )

        bottom_phase = self._phase if self._phase in {"idle", "running", "paused"} else "idle"
        # Guide-only / rest: no coach/评价 banner (unless camera/boot error).
        show_banner = (
            self._cam_error is not None
            or self._booting
            or (
                (not is_guide)
                and (not self._resting)
                and (
                    self._phase != "idle"
                    or coach_title is not None
                    or (not self._session.detector_available)
                )
            )
        )
        banner_title = title or ""
        banner_sub = subtitle
        if self._cam_error:
            banner_title = _CAM_TITLE
            banner_sub = self._cam_error
        elif self._booting:
            banner_title = "\u6b63\u5728\u6253\u5f00\u6444\u50cf\u5934\u2026"
            banner_sub = None
        elif is_guide or self._resting:
            banner_title = ""
            banner_sub = None

        column_children: list[ft.Control] = [
            build_top_bar(
                elapsed_seconds=self._current_elapsed(),
                action_name=self._queue.hud_title,
                ai_active=ai_active,
                recording=recording,
                on_close=self._close,
                on_switch_camera=(
                    self._switch_cam
                    if self._phase in {"running", "paused"} and not self._booting
                    else None
                ),
            ),
            ft.Container(height=14),
            *mid,
            ft.Container(expand=True),
            (
                build_correction_banner(
                    title=banner_title,
                    subtitle=banner_sub,
                    is_warning=self._coach_is_warning(banner_title, banner_sub),
                )
                if show_banner and banner_title
                else ft.Container(height=0)
            ),
            ft.Container(height=16),
        ]
        live_nav = self._phase in {"running", "paused"}
        show_pick_idle = self._queue.is_multi and self._phase == "idle"
        if live_nav or show_pick_idle:
            if self._resting:
                mode = {
                    "prev_label": _LABEL_PREV_SET,
                    "next_label": _LABEL_SKIP_REST,
                    "can_prev": False,
                    "can_next": True,
                }
            elif live_nav:
                mode = self._nav_mode()
            else:
                mode = {
                    "prev_label": _LABEL_PREV_SET,
                    "next_label": _LABEL_NEXT_SET,
                    "can_prev": False,
                    "can_next": False,
                }
            column_children.append(
                build_set_nav(
                    on_previous=self._on_nav_previous if live_nav else None,
                    on_next=self._on_nav_next if live_nav else None,
                    on_pick=self._pick_action if self._queue.is_multi else None,
                    can_previous=live_nav and mode["can_prev"],
                    can_next=live_nav and mode["can_next"],
                    show_pick=self._queue.is_multi and (live_nav or show_pick_idle),
                    prev_label=mode["prev_label"],
                    next_label=mode["next_label"],
                )
            )
            column_children.append(ft.Container(height=12))
        # Android: skip flashing Flet「开始训练」while opening the native page.
        hide_idle_start = (
            bottom_phase == "idle"
            and self._uses_native_preview()
            and (self._booting or (self._session.detector_available and not self._cam_error))
        )
        if hide_idle_start:
            column_children.append(ft.Container(height=54))
        else:
            column_children.append(
                build_bottom_controls(
                    phase=bottom_phase,
                    on_start=self._start_session,
                    on_pause=self._pause_session,
                    on_stop=self._confirm_end_and_finish,
                    on_resume=self._resume_session,
                    on_end=self._confirm_end_and_finish,
                    on_switch_camera=self._switch_cam if bottom_phase == "paused" else None,
                    show_manual_continue=is_manual and self._phase == "running",
                    on_manual_continue=self._manual_complete,
                    start_enabled=self._session.detector_available and not self._booting,
                )
            )
        self._hud_layer.content = ft.Container(
            expand=True,
            padding=ft.Padding.only(left=16, top=8, right=16, bottom=16),
            content=ft.Column(column_children, expand=True, spacing=0),
        )

    def _hide_demo(self) -> None:
        self._show_demo = False
        self._rebuild_hud()
        self._safe_update()

    def _confirm_delete_record(self) -> None:
        dlg = ft.AlertDialog(
            title=ft.Text("删除这条训练记录？"),
            content=ft.Text("删除后无法恢复。"),
            actions=[
                ft.TextButton("取消", on_click=lambda e: self._close_dlg()),
                ft.TextButton("删除", on_click=self._do_delete_record),
            ],
        )
        self._open_dlg(dlg)

    def _do_delete_record(self, _: ft.ControlEvent | None = None) -> None:
        self._close_dlg()
        if self._record_id:
            self._svc.delete_training_record(self._record_id)
            self._record_id = None
            self._record_saved = False
        self._close()

    def _summary_actions(self) -> list[dict]:
        items: list[dict] = []
        for a in self._queue.completed:
            if ExerciseKind.is_guide_only(a.action_name):
                continue
            reps = int(a.reps or 0)
            est_sets = (
                max(1, min(_SETS_PER_ACTION, math.ceil(reps / _TARGET_REPS)))
                if reps > 0
                else 1
            )
            items.append(
                {
                    "name": a.action_name,
                    "reps": reps,
                    "sets": est_sets,
                    "avg_score": a.avg_score,
                }
            )
        return items

    def _previous_record(self, session_name: str) -> TrainingRecord | None:
        for r in self._svc.get_training_history():
            if r.exercise_name == session_name and r.id != self._record_id:
                return r
        return None

    def _muscle_svg_srcs(self, action_names: list[str]) -> tuple[str | None, str | None]:
        return write_muscle_svgs(action_names)

    def _rebuild_summary(self) -> None:
        self._hud_safe.visible = True
        self._hud_layer.visible = False
        self._summary_layer.visible = True
        self._summary_layer.bgcolor = "#F5F7FA"
        name = self._session_title or self._default_session_title()
        actions = self._summary_actions()
        sets_done = max(1, self._session_sets_completed) if self._session_sets_completed else (
            max(1, sum(a["sets"] for a in actions) or self._queue.completed_count or 1)
        )
        planned = sum(
            1 for a in self._queue.actions if not ExerciseKind.is_guide_only(a)
        )
        prev = self._previous_record(name)
        front_src, back_src = self._muscle_svg_srcs([a["name"] for a in actions])
        self._summary_layer.content = ft.Container(
            expand=True,
            padding=ft.Padding.all(16),
            content=build_finished_summary(
                session_name=name,
                started_at=self._started_at,
                finished_at=self._finished_at,
                sets=sets_done,
                duration_seconds=self._elapsed,
                calories=self._calories,
                posture_pct=self._avg_quality if self._avg_quality > 0 else 0,
                planned_actions=planned,
                actions=actions,
                prev_calories=prev.calories if prev else None,
                prev_duration_seconds=prev.duration * 60 if prev else None,
                summary_text=build_session_summary_text(actions),
                muscle_front_src=front_src,
                muscle_back_src=back_src,
                on_back=self._close,
                on_delete=self._confirm_delete_record,
                on_share=lambda: self._toast(_SHARE_SOON),
                on_download=lambda: self._toast(_DOWNLOAD_SOON),
            ),
        )

    def _toast(self, msg: str) -> None:
        self._host.show_dialog(ft.SnackBar(ft.Text(msg)))
