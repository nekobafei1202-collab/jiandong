from __future__ import annotations

import flet as ft

from jiandong_ai.app.constants import APP_NAME, MOCK_EMAIL, MOCK_PASSWORD
from jiandong_ai.app.theme import ShellColors
from jiandong_ai.services.mock_service import MockService


def build_login(page: ft.Page, *, on_success, on_register) -> ft.Control:
    sc = ShellColors
    email = ft.TextField(
        label="邮箱",
        value=MOCK_EMAIL,
        border_color=sc.border,
        bgcolor=sc.surface,
        color=sc.text,
        cursor_color=sc.accent,
        focused_border_color=sc.accent,
    )
    password = ft.TextField(
        label="密码",
        value=MOCK_PASSWORD,
        password=True,
        can_reveal_password=True,
        border_color=sc.border,
        bgcolor=sc.surface,
        color=sc.text,
        cursor_color=sc.accent,
        focused_border_color=sc.accent,
    )
    error = ft.Text("", color=sc.danger, size=12)
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
        bgcolor=sc.canvas,
        padding=24,
        content=ft.Column(
            [
                ft.Container(height=48),
                ft.Text(APP_NAME, size=32, weight=ft.FontWeight.BOLD, color=sc.text),
                ft.Text("登录后开始训练", size=14, color=sc.text_secondary),
                ft.Container(height=28),
                email,
                password,
                error,
                ft.Container(height=8),
                ft.FilledButton(
                    "登录",
                    bgcolor=sc.accent,
                    color=sc.on_cta,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=24)),
                    on_click=submit,
                    width=page.width or 360,
                    height=48,
                ),
                ft.TextButton("注册账号", style=ft.ButtonStyle(color=sc.accent), on_click=lambda e: on_register()),
                ft.ProgressRing(ref=busy, visible=False, width=20, height=20),
            ],
            tight=True,
        ),
    )
