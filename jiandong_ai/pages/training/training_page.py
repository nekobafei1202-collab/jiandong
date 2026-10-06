from __future__ import annotations

import threading
import time
from datetime import datetime

import flet as ft

from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.ai.session.live_pose_session import LivePoseSession
from jiandong_ai.ai.session.training_pipeline import TrainingPipeline
from jiandong_ai.app.theme import (
    HUD_CANVAS,
    HUD_CORAL,
    HUD_CYAN,
    HUD_GREEN,
    HUD_SURFACE,
    HUD_TEXT,
    HUD_TEXT_SECONDARY,
    SHELL_ACCENT,
)
from jiandong_ai.models import RecordAction, TrainingRecord
from jiandong_ai.services.mock_service import MockService
from jiandong_ai.widgets.pose_overlay import (
    draw_pose_overlay,
    frame_to_base64_jpg,
    placeholder_image,
)


class TrainingView(ft.Container):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, bgcolor=HUD_CANVAS, padding=0)
        self.page = page
        self._svc = MockService.instance()
        self._action_name = "深蹲"
        self._pipeline = TrainingPipeline(exercise_id="squat")
        self._session = LivePoseSession()
        self._ui_lock = threading.Lock()
        self._last_ui = 0.0
        self._started_at: datetime | None = None
        self._session_reps = 0

        self._preview = ft.Image(
            src_base64=placeholder_image(),
            fit=ft.ImageFit.COVER,
            expand=True,
        )
        self._title = ft.Text("深蹲", size=18, weight=ft.FontWeight.BOLD, color=HUD_TEXT)
        self._status = ft.Text("准备开始", size=14, color=HUD_CYAN)
        self._message = ft.Text(
            "请站到摄像头前，点击开始训练",
            size=13,
            color=HUD_TEXT_SECONDARY,
        )
        self._reps = ft.Text("0", size=40, weight=ft.FontWeight.BOLD, color=HUD_TEXT)
        self._score = ft.Text("--", size=28, weight=ft.FontWeight.BOLD, color=HUD_GREEN)
        self._angle = ft.Text("--", size=16, color=HUD_TEXT_SECONDARY)
        self._start_btn = ft.FilledButton(
            "开始训练",
            bgcolor=HUD_CORAL,
            color="white",
            on_click=self._toggle_run,
        )
        self._manual_btn = ft.OutlinedButton(
            "完成并继续",
            visible=False,
            style=ft.ButtonStyle(color=HUD_TEXT),
            on_click=self._manual_complete,
        )

        hud = ft.Container(
            bgcolor=HUD_SURFACE,
            padding=14,
            border_radius=ft.border_radius.only(top_left=16, top_right=16),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            self._title,
                            ft.IconButton(
                                icon=ft.Icons.CAMERASWITCH,
                                icon_color=HUD_TEXT,
                                on_click=self._switch_cam,
                                tooltip="切换摄像头",
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("次数", size=11, color=HUD_TEXT_SECONDARY),
                                    self._reps,
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Column(
                                [
                                    ft.Text("评分", size=11, color=HUD_TEXT_SECONDARY),
                                    self._score,
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Column(
                                [
                                    ft.Text("关节角", size=11, color=HUD_TEXT_SECONDARY),
                                    self._angle,
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_AROUND,
                    ),
                    self._status,
                    self._message,
                    ft.Row([self._start_btn, self._manual_btn], spacing=10),
                ],
                spacing=8,
                tight=True,
            ),
        )

        self.content = ft.Column(
            [
                ft.Container(content=self._preview, expand=True, bgcolor=HUD_CANVAS),
                hud,
            ],
            expand=True,
            spacing=0,
        )

    def set_action(self, action: str) -> None:
        self._action_name = action
        self._title.value = ExerciseKind.display_name(action)
        manual = ExerciseKind.is_manual_complete(action)
        self._manual_btn.visible = manual
        if ExerciseKind.supports_auto_detect(action):
            self._pipeline.switch_exercise(ExerciseKind.normalize(action))
        else:
            # Manual actions (e.g. crunch) skip auto pipeline counting
            self._pipeline.switch_exercise("squat")
            self._pipeline.stop()
        self._refresh_coach()
        if self.page:
            self.update()

    def on_show(self) -> None:
        self._refresh_coach()
        if not self._session.detector_available:
            self._message.value = (
                f"姿态引擎未就绪：{self._session.detector_error or '请安装 mediapipe'}"
            )
        if self.page:
            self.update()

    def _refresh_coach(self) -> None:
        c = self._pipeline.coach
        self._status.value = c.status_text
        self._message.value = c.message
        self._score.value = c.score_text
        self._angle.value = c.knee_angle_text
        self._reps.value = str(self._pipeline.action.rep_count)

    def _toggle_run(self, _: ft.ControlEvent) -> None:
        if self._pipeline.is_running:
            self._stop_session(save=True)
        else:
            self._start_session()

    def _start_session(self) -> None:
        if not self._session.start():
            self._message.value = "无法打开摄像头，请检查设备权限"
            self.update()
            return
        self._started_at = datetime.now()
        self._session_reps = 0
        self._pipeline.start()
        self._session.set_listener(self._on_frame)
        self._start_btn.text = "结束训练"
        self._start_btn.bgcolor = "#666666"
        self.update()

    def _stop_session(self, *, save: bool) -> None:
        self._session.set_listener(None)
        self._session.stop()
        reps = self._pipeline.action.rep_count
        score = self._pipeline.evaluation.score or 0
        self._pipeline.stop()
        self._start_btn.text = "开始训练"
        self._start_btn.bgcolor = HUD_CORAL
        self._preview.src_base64 = placeholder_image(text="训练已结束")
        self._refresh_coach()
        if save and self._started_at is not None:
            minutes = max(1, int((datetime.now() - self._started_at).total_seconds() // 60) or 1)
            self._svc.mark_plan_done(self._action_name)
            self._svc.add_training_record(
                TrainingRecord(
                    id=f"r_{int(time.time()*1000)}",
                    exercise_name=self._action_name,
                    duration=minutes,
                    score=score or 80,
                    date=datetime.now().isoformat(),
                    calories=minutes * 4,
                    total_reps=reps,
                    actions=(
                        RecordAction(
                            action_name=self._action_name,
                            reps=reps,
                            avg_score=score or None,
                            feedback=self._pipeline.coach.message,
                        ),
                    ),
                )
            )
        self.update()

    def _manual_complete(self, _: ft.ControlEvent) -> None:
        self._svc.mark_plan_done(self._action_name)
        self._message.value = f"「{self._action_name}」已标记完成"
        self.update()

    def _switch_cam(self, _: ft.ControlEvent) -> None:
        was = self._pipeline.is_running
        self._session.switch_camera()
        if was:
            self._session.set_listener(self._on_frame)

    def _on_frame(self, frame, pose) -> None:
        coach = self._pipeline.process_pose(pose)
        overlay = draw_pose_overlay(frame, pose)
        b64 = frame_to_base64_jpg(overlay, quality=70)
        now = time.time()
        if now - self._last_ui < 0.08:
            return
        self._last_ui = now

        def apply() -> None:
            self._preview.src_base64 = b64
            self._status.value = coach.status_text
            self._message.value = coach.message
            self._score.value = coach.score_text
            self._angle.value = coach.knee_angle_text
            self._reps.value = str(self._pipeline.action.rep_count)
            try:
                self.update()
            except Exception:
                pass

        if self.page:
            self.page.run_thread(apply)
