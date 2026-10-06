from __future__ import annotations

import flet as ft

from jiandong_ai.app.theme import (
    SHELL_ACCENT,
    SHELL_BORDER,
    SHELL_CALORIE,
    SHELL_CANVAS,
    SHELL_SURFACE,
    SHELL_TEXT,
    SHELL_TEXT_SECONDARY,
)
from jiandong_ai.pages.home.plan_editor_page import open_plan_editor
from jiandong_ai.services.mock_service import MockService


class HomeView(ft.Container):
    def __init__(self, page: ft.Page, *, on_start_training) -> None:
        super().__init__(expand=True, bgcolor=SHELL_CANVAS, padding=16)
        self.page = page
        self.on_start_training = on_start_training
        self._svc = MockService.instance()
        self._list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
        self.content = ft.Column(
            [
                ft.Text("今日训练", size=24, weight=ft.FontWeight.BOLD, color=SHELL_TEXT),
                ft.Text(ref=ft.Ref[ft.Text](), size=13, color=SHELL_TEXT_SECONDARY),
                self._progress_row(),
                ft.Row(
                    [
                        ft.Text("今日计划", size=16, weight=ft.FontWeight.W_600, color=SHELL_TEXT),
                        ft.TextButton("编辑", on_click=self._edit_plan),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self._list,
                ft.Text("推荐课程", size=16, weight=ft.FontWeight.W_600, color=SHELL_TEXT),
                self._reco(),
            ],
            expand=True,
            spacing=12,
        )
        self._svc.on_plan_changed(self.refresh)
        self.refresh()

    def _progress_row(self) -> ft.Control:
        self._progress_text = ft.Text("", size=13, color=SHELL_TEXT_SECONDARY)
        self._progress_bar = ft.ProgressBar(color=SHELL_ACCENT, bgcolor=SHELL_BORDER, value=0)
        return ft.Column([self._progress_text, self._progress_bar], spacing=6)

    def _reco(self) -> ft.Control:
        cards = []
        for w in self._svc.get_recommended_workouts():
            cards.append(
                ft.Container(
                    bgcolor=SHELL_SURFACE,
                    border=ft.border.all(1, SHELL_BORDER),
                    border_radius=12,
                    padding=12,
                    width=160,
                    content=ft.Column(
                        [
                            ft.Text(w.name, weight=ft.FontWeight.W_600, color=SHELL_TEXT),
                            ft.Text(f"{w.duration} 分钟 · {w.difficulty}", size=12, color=SHELL_TEXT_SECONDARY),
                        ],
                        spacing=4,
                    ),
                )
            )
        return ft.Row(cards, scroll=ft.ScrollMode.AUTO, spacing=10)

    def _edit_plan(self, _: ft.ControlEvent) -> None:
        open_plan_editor(self.page, on_saved=self.refresh)

    def refresh(self) -> None:
        done = self._svc.get_today_completed_count()
        goal = max(1, self._svc.get_today_goal_count())
        self._progress_text.value = f"已完成 {done}/{self._svc.get_today_goal_count()}"
        self._progress_bar.value = done / goal
        self._list.controls.clear()
        for action, is_done in self._svc.get_today_plan():
            self._list.controls.append(
                ft.Container(
                    bgcolor=SHELL_SURFACE,
                    border=ft.border.all(1, SHELL_BORDER),
                    border_radius=12,
                    padding=12,
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE if is_done else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                color=SHELL_ACCENT if is_done else SHELL_TEXT_SECONDARY,
                            ),
                            ft.Text(action, expand=True, color=SHELL_TEXT),
                            ft.Text(self._svc.get_quick_target(action), size=12, color=SHELL_CALORIE),
                            ft.FilledButton(
                                "开始",
                                bgcolor=SHELL_ACCENT,
                                color="white",
                                height=36,
                                on_click=lambda e, a=action: self.on_start_training(a),
                            ),
                        ]
                    ),
                )
            )
        if self.page:
            self.update()

    def on_show(self) -> None:
        self.refresh()
