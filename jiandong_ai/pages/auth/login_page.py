from __future__ import annotations

import flet as ft

from jiandong_ai.app.constants import APP_NAME, MOCK_EMAIL, MOCK_PASSWORD
from jiandong_ai.app.theme import (
    SHELL_ACCENT,
    SHELL_BORDER,
    SHELL_CANVAS,
    SHELL_SURFACE,
    SHELL_TEXT,
    SHELL_TEXT_SECONDARY,
)
from jiandong_ai.services.mock_service import MockService


def build_login(page: ft.Page, *, on_success, on_register) -> ft.Control:
    email = ft.TextField(
        label="邮箱",
        value=MOCK_EMAIL,
        border_color=SHELL_BORDER,
        bgcolor=SHELL_SURFACE,
    )
    password = ft.TextField(
        label="密码",
        value=MOCK_PASSWORD,
        password=True,
        can_reveal_password=True,
        border_color=SHELL_BORDER,
        bgcolor=SHELL_SURFACE,
    )
    error = ft.Text("", color="red", size=12)
    busy = ft.Ref[ft.ProgressRing]()

    def submit(_: ft.ControlEvent) -> None:
        error.value = ""
        user = MockService.instance().login(email.value or "", password.value or "")
        if user is None:
            error.value = "账号或密码错误（试用 test@example.com / 123456）"
            page.update()
            return
        on_success()

    return ft.Container(
        expand=True,
        bgcolor=SHELL_CANVAS,
        padding=24,
        content=ft.Column(
            [
                ft.Container(height=48),
                ft.Text(APP_NAME, size=32, weight=ft.FontWeight.BOLD, color=SHELL_TEXT),
                ft.Text("登录后开始训练", size=14, color=SHELL_TEXT_SECONDARY),
                ft.Container(height=28),
                email,
                password,
                error,
                ft.Container(height=8),
                ft.FilledButton(
                    "登录",
                    bgcolor=SHELL_ACCENT,
                    color="white",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=24)),
                    on_click=submit,
                    width=page.width or 360,
                    height=48,
                ),
                ft.TextButton("注册账号", on_click=lambda e: on_register()),
                ft.ProgressRing(ref=busy, visible=False, width=20, height=20),
            ],
            tight=True,
        ),
    )
