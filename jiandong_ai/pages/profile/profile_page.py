from __future__ import annotations

import flet as ft

from jiandong_ai.app.constants import APP_NAME, APP_TAGLINE
from jiandong_ai.app.theme import (
    SHELL_ACCENT,
    SHELL_BORDER,
    SHELL_CANVAS,
    SHELL_SURFACE,
    SHELL_TEXT,
    SHELL_TEXT_SECONDARY,
)
from jiandong_ai.services.mock_service import AppSession, MockService


class ProfileView(ft.Container):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, bgcolor=SHELL_CANVAS, padding=16)
        self.page = page
        self._svc = MockService.instance()
        self._name = ft.Text("", size=22, weight=ft.FontWeight.BOLD, color=SHELL_TEXT)
        self._email = ft.Text("", size=13, color=SHELL_TEXT_SECONDARY)
        self._meta = ft.Text("", size=13, color=SHELL_TEXT_SECONDARY)
        self.content = ft.Column(
            [
                ft.Text("我的", size=24, weight=ft.FontWeight.BOLD, color=SHELL_TEXT),
                ft.Container(
                    bgcolor=SHELL_SURFACE,
                    border=ft.border.all(1, SHELL_BORDER),
                    border_radius=16,
                    padding=16,
                    content=ft.Row(
                        [
                            ft.CircleAvatar(
                                content=ft.Text("健", color="white"),
                                bgcolor=SHELL_ACCENT,
                                radius=28,
                            ),
                            ft.Column([self._name, self._email, self._meta], spacing=2),
                        ],
                        spacing=14,
                    ),
                ),
                ft.Container(
                    bgcolor=SHELL_SURFACE,
                    border=ft.border.all(1, SHELL_BORDER),
                    border_radius=12,
                    padding=14,
                    content=ft.Column(
                        [
                            ft.Text(APP_NAME, weight=ft.FontWeight.W_600, color=SHELL_TEXT),
                            ft.Text(APP_TAGLINE, size=12, color=SHELL_TEXT_SECONDARY),
                            ft.Text("Python / Flet 版 · 与 Flutter 原版并行", size=12, color=SHELL_TEXT_SECONDARY),
                        ],
                        spacing=4,
                    ),
                ),
                ft.OutlinedButton(
                    "退出登录（仅清除会话）",
                    on_click=self._logout,
                ),
            ],
            spacing=14,
        )

    def on_show(self) -> None:
        u = self._svc.get_current_user()
        self._name.value = u.name
        self._email.value = u.email
        self._meta.value = f"已坚持训练 {u.training_days} 天 · 连续 {self._svc.get_streak_days()} 天"
        if self.page:
            self.update()

    def _logout(self, _: ft.ControlEvent) -> None:
        AppSession.clear()
        self.page.snack_bar = ft.SnackBar(ft.Text("已清除会话，重启应用可重新登录"))
        self.page.snack_bar.open = True
        self.page.update()
