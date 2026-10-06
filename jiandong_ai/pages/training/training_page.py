from __future__ import annotations

import time
from datetime import datetime

import flet as ft

from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.ai.session.live_pose_session import LivePoseSession
from jiandong_ai.ai.session.training_pipeline import TrainingPipeline
from jiandong_ai.app.theme import HUD_CANVAS
from jiandong_ai.models import RecordAction, TrainingRecord
from jiandong_ai.services.mock_service import MockService
from jiandong_ai.widgets.pose_overlay import draw_pose_overlay, frame_to_image_src, placeholder_image
from jiandong_ai.widgets.training_hud import (
    build_bottom_controls,
    build_correction_banner,
    build_demo_window,
    build_finished_summary,
    build_posture_ring,
    build_rep_counter,
    build_top_bar,
)

# Chinese UI strings via escapes (avoid encoding corruption on Windows tooling).
_SQUAT = "\u6df1\u8e72"
_ENGINE_TITLE = "\u59ff\u6001\u5f15\u64ce\u672a\u5c31\u7eea"
_ENGINE_HINT = "\u8bf7\u5b89\u88c5 mediapipe"
_CAM_TITLE = "\u6444\u50cf\u5934\u5f02\u5e38"
_CAM_HINT = "\u65e0\u6cd5\u6253\u5f00\u6444\u50cf\u5934\uff0c\u8bf7\u68c0\u67e5\u8bbe\u5907\u6743\u9650"
_ENDED = "\u8bad\u7ec3\u5df2\u7ed3\u675f"
_INSIGHT_FALLBACK = (
    "\u672c\u6b21\u8bad\u7ec3\u8282\u594f\u7a33\u5b9a\uff0c\u6574\u4f53\u5b8c\u6210\u5ea6\u4e0d\u9519\u3002"
)
_KEY_POINT = "\u5173\u952e\u70b9\uff1a\u4fdd\u6301\u6838\u5fc3\u6536\u7d27\uff0c\u52a8\u4f5c\u5e45\u5ea6\u505a\u6ee1\u3002"
_NEXT_FOCUS_TMPL = (
    "\u4e0b\u6b21\u7ee7\u7eed\u7ec3\u4e60\u300c{name}\u300d\uff0c\u4f18\u5148\u4fdd\u8bc1\u59ff\u52bf\u518d\u63d0\u5347\u6b21\u6570\u3002"
)
_SHARE_SOON = "\u5206\u4eab\u529f\u80fd\u5373\u5c06\u5f00\u653e"
_DOWNLOAD_SOON = "\u4e0b\u8f7d\u529f\u80fd\u5373\u5c06\u5f00\u653e"


class TrainingView(ft.Container):
    """Fullscreen camera Stack: preview + vignette + HUD + finished summary."""

    def __init__(self, page: ft.Page, *, on_close=None) -> None:
        super().__init__(expand=True, bgcolor=HUD_CANVAS, padding=0)
        self._host = page
        self.on_close = on_close
        self._svc = MockService.instance()
        self._action_name = _SQUAT
        self._pipeline = TrainingPipeline(exercise_id="squat")
        self._session = LivePoseSession()
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
        self._record_saved = False
        self._saving = False

        self._preview = ft.Image(
            src=placeholder_image(),
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

        self.content = ft.Stack(
            [
                ft.Container(expand=True, bgcolor=HUD_CANVAS, content=self._preview),
                self._vignette,
                self._hud_layer,
                self._summary_layer,
            ],
            expand=True,
        )
        self._rebuild_hud()

    def _safe_update(self) -> None:
        try:
            self.update()
        except Exception:
            pass

    def set_action(self, action: str) -> None:
        if self._phase in {"running", "paused"}:
            self._stop_session(save=False, finish=False)
        self._action_name = action
        self._phase = "idle"
        self._record_saved = False
        self._show_demo = True
        if ExerciseKind.supports_auto_detect(action):
            self._pipeline.switch_exercise(ExerciseKind.normalize(action))
        else:
            self._pipeline.switch_exercise("squat")
            self._pipeline.stop()
        self._preview.src = placeholder_image()
        self._rebuild_hud()
        self._safe_update()

    def on_show(self) -> None:
        if not self._session.detector_available and self._phase == "idle":
            self._rebuild_hud(
                coach_title=_ENGINE_TITLE,
                coach_subtitle=self._session.detector_error or _ENGINE_HINT,
            )
        else:
            self._rebuild_hud()
        self._safe_update()

    def _start_session(self) -> None:
        if not self._session.start():
            self._rebuild_hud(coach_title=_CAM_TITLE, coach_subtitle=_CAM_HINT)
            self._safe_update()
            return
        self._started_at = datetime.now()
        self._elapsed_base = 0
        self._elapsed_anchor = time.time()
        self._elapsed = 0
        self._display_reps = 0
        self._avg_quality = 0
        self._record_saved = False
        self._pipeline.start()
        self._session.set_listener(self._on_frame)
        self._phase = "running"
        self._rebuild_hud()
        self._safe_update()

    def _pause_session(self) -> None:
        if self._phase != "running":
            return
        self._elapsed_base = self._current_elapsed()
        self._pipeline.pause()
        self._session.set_listener(None)
        self._phase = "paused"
        self._rebuild_hud()
        self._safe_update()

    def _resume_session(self) -> None:
        if self._phase != "paused":
            return
        self._elapsed_anchor = time.time()
        self._pipeline.resume()
        self._session.set_listener(self._on_frame)
        self._phase = "running"
        self._rebuild_hud()
        self._safe_update()

    def _stop_session(self, *, save: bool, finish: bool = True) -> None:
        self._session.set_listener(None)
        self._session.stop()
        reps = self._pipeline.action.rep_count
        score = self._pipeline.evaluation.score or 0
        self._pipeline.stop()
        self._elapsed = self._current_elapsed()
        self._display_reps = reps
        self._avg_quality = score or self._avg_quality or 80
        self._calories = max(1, self._elapsed // 15) * 4
        self._finished_at = datetime.now()
        self._preview.src = placeholder_image(text=_ENDED)
        if finish:
            self._phase = "finished"
            self._rebuild_summary()
        else:
            self._phase = "idle"
            self._rebuild_hud()
        if save and self._started_at is not None and not self._record_saved:
            self._persist_record()
        self._safe_update()

    def _persist_record(self) -> None:
        if self._record_saved or self._started_at is None:
            return
        self._saving = True
        self._rebuild_summary()
        self._safe_update()
        minutes = max(1, int(self._elapsed // 60) or 1)
        self._svc.mark_plan_done(self._action_name)
        self._svc.add_training_record(
            TrainingRecord(
                id=f"r_{int(time.time() * 1000)}",
                exercise_name=self._action_name,
                duration=minutes,
                score=self._avg_quality or 80,
                date=datetime.now().isoformat(),
                calories=self._calories,
                total_reps=self._display_reps,
                actions=(
                    RecordAction(
                        action_name=self._action_name,
                        reps=self._display_reps,
                        avg_score=self._avg_quality or None,
                        feedback=self._pipeline.coach.message,
                    ),
                ),
            )
        )
        self._record_saved = True
        self._saving = False
        self._rebuild_summary()
        self._safe_update()

    def _manual_complete(self) -> None:
        self._svc.mark_plan_done(self._action_name)
        self._stop_session(save=True, finish=True)

    def _switch_cam(self) -> None:
        was = self._phase == "running"
        self._session.switch_camera()
        if was:
            self._session.set_listener(self._on_frame)

    def _close(self) -> None:
        if self._phase in {"running", "paused"}:
            self._stop_session(save=False, finish=False)
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
        if self._phase != "running":
            return
        coach = self._pipeline.process_pose(pose)
        overlay = draw_pose_overlay(frame, pose, vignette=True)
        src = frame_to_image_src(overlay, quality=70)
        now = time.time()
        if now - self._last_ui < 0.08:
            return
        self._last_ui = now
        score = self._pipeline.evaluation.score or 0
        if score > 0:
            self._avg_quality = score
        self._elapsed = self._current_elapsed()
        reps = self._pipeline.action.rep_count

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
            self._host.run_thread(apply)

    def _rebuild_hud(
        self,
        *,
        coach_title: str | None = None,
        coach_subtitle: str | None = None,
        reps: int | None = None,
        score: int | None = None,
    ) -> None:
        if self._phase == "finished":
            self._hud_layer.visible = False
            self._summary_layer.visible = True
            return

        self._hud_layer.visible = True
        self._summary_layer.visible = False
        c = self._pipeline.coach
        title = coach_title if coach_title is not None else c.status_text
        subtitle = coach_subtitle if coach_subtitle is not None else c.message
        rep_count = reps if reps is not None else self._pipeline.action.rep_count
        live_score = score if score is not None else (self._pipeline.evaluation.score or 0)
        has_score = live_score > 0 and self._phase in {"running", "paused"}
        is_manual = ExerciseKind.is_manual_complete(self._action_name)
        ai_active = self._phase == "running" and not is_manual
        recording = self._phase in {"running", "paused"}

        mid: list[ft.Control] = []
        if self._phase != "idle":
            mid.append(
                ft.Row(
                    [
                        build_demo_window(on_close=self._hide_demo)
                        if self._show_demo
                        else ft.Container(width=8),
                        ft.Container(
                            expand=True,
                            padding=ft.Padding.only(top=4),
                            content=build_rep_counter(set_index=1, rep_count=rep_count),
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

        bottom_phase = self._phase if self._phase in {"idle", "running", "paused"} else "idle"
        show_banner = self._phase != "idle" or coach_title is not None
        self._hud_layer.content = ft.Container(
            expand=True,
            padding=ft.Padding.only(left=16, top=8, right=16, bottom=16),
            content=ft.Column(
                [
                    build_top_bar(
                        elapsed_seconds=self._current_elapsed(),
                        action_name=ExerciseKind.display_name(self._action_name),
                        ai_active=ai_active,
                        recording=recording,
                        on_close=self._close,
                        on_switch_camera=self._switch_cam,
                    ),
                    ft.Container(height=14),
                    *mid,
                    ft.Container(expand=True),
                    (
                        build_correction_banner(
                            title=title or "",
                            subtitle=subtitle,
                            is_warning=True,
                        )
                        if show_banner
                        else ft.Container(height=0)
                    ),
                    ft.Container(height=16),
                    build_bottom_controls(
                        phase=bottom_phase,
                        on_start=self._start_session,
                        on_pause=self._pause_session,
                        on_stop=lambda: self._stop_session(save=True, finish=True),
                        on_resume=self._resume_session,
                        on_end=lambda: self._stop_session(save=True, finish=True),
                        show_manual_continue=is_manual and self._phase == "running",
                        on_manual_continue=self._manual_complete,
                    ),
                ],
                expand=True,
                spacing=0,
            ),
        )

    def _hide_demo(self) -> None:
        self._show_demo = False
        self._rebuild_hud()
        self._safe_update()

    def _rebuild_summary(self) -> None:
        self._hud_layer.visible = False
        self._summary_layer.visible = True
        name = ExerciseKind.display_name(self._action_name)
        self._summary_layer.content = ft.Container(
            expand=True,
            padding=ft.Padding.all(16),
            content=build_finished_summary(
                action_name=name,
                finished_at=self._finished_at,
                sets=1,
                reps=self._display_reps,
                posture_pct=self._avg_quality or 80,
                duration_seconds=self._elapsed,
                calories=self._calories,
                effort_out_of_10=max(3, min(10, (self._display_reps // 2) + 4)),
                insight_reason=self._pipeline.coach.message or _INSIGHT_FALLBACK,
                insight_key_point=_KEY_POINT,
                next_focus=_NEXT_FOCUS_TMPL.format(name=name),
                saving=self._saving,
                saved=self._record_saved,
                on_delete=self._close,
                on_save=self._persist_record,
                on_share=lambda: self._toast(_SHARE_SOON),
                on_download=lambda: self._toast(_DOWNLOAD_SOON),
            ),
        )

    def _toast(self, msg: str) -> None:
        self._host.snack_bar = ft.SnackBar(ft.Text(msg))
        self._host.snack_bar.open = True
        self._host.update()
