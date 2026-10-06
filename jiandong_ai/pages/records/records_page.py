from __future__ import annotations

from datetime import datetime

import flet as ft

from jiandong_ai.app.theme import (
    SHELL_ACCENT,
    SHELL_BORDER,
    SHELL_CANVAS,
    SHELL_SURFACE,
    SHELL_TEXT,
    SHELL_TEXT_SECONDARY,
)
from jiandong_ai.services.mock_service import MockService


class RecordsView(ft.Container):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, bgcolor=SHELL_CANVAS, padding=16)
        self.page = page
        self._svc = MockService.instance()
        self._stats = ft.Text("", color=SHELL_TEXT_SECONDARY)
        self._week = ft.Row(spacing=6)
        self._list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self.content = ft.Column(
            [
                ft.Text("训练记录", size=24, weight=ft.FontWeight.BOLD, color=SHELL_TEXT),
                self._stats,
                ft.Text("本周时长（分钟）", size=14, weight=ft.FontWeight.W_600, color=SHELL_TEXT),
                self._week,
                self._list,
            ],
            expand=True,
            spacing=12,
        )

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        streak = self._svc.get_streak_days()
        today = self._svc.get_today_stats()
        self._stats.value = (
            f"连续 {streak} 天 · 今日 {today['durationMinutes']} 分钟 · "
            f"均分 {today['avgScore']}"
        )
        self._week.controls.clear()
        weekly = self._svc.get_weekly_stats()
        max_m = max((w.minutes for w in weekly), default=1) or 1
        for w in weekly:
            h = max(8, int(80 * w.minutes / max_m))
            self._week.controls.append(
                ft.Column(
                    [
                        ft.Container(width=28, height=h, bgcolor=SHELL_ACCENT, border_radius=6),
                        ft.Text(w.label, size=11, color=SHELL_TEXT_SECONDARY),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                )
            )
        self._list.controls.clear()
        for r in self._svc.get_training_history():
            try:
                when = datetime.fromisoformat(r.date).strftime("%m-%d %H:%M")
            except ValueError:
                when = r.date
            self._list.controls.append(
                ft.Container(
                    bgcolor=SHELL_SURFACE,
                    border=ft.border.all(1, SHELL_BORDER),
                    border_radius=12,
                    padding=12,
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(r.exercise_name, weight=ft.FontWeight.W_600, color=SHELL_TEXT),
                                    ft.Text(f"{when} · {r.duration} 分钟", size=12, color=SHELL_TEXT_SECONDARY),
                                ],
                                expand=True,
                                spacing=2,
                            ),
                            ft.Text(f"{r.score}", size=22, weight=ft.FontWeight.BOLD, color=SHELL_ACCENT),
                        ]
                    ),
                )
            )
        if self.page:
            self.update()
