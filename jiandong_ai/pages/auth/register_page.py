from __future__ import annotations

import flet as ft

from jiandong_ai.app.theme import ShellColors
from jiandong_ai.services.mock_service import MockService


def build_register(page: ft.Page, *, on_success, on_back) -> ft.Control:
    sc = ShellColors
    name = ft.TextField(
        label="昵称",
        border_color=sc.border,
        bgcolor=sc.surface,
        color=sc.text,
        focused_border_color=sc.accent,
    )
    email = ft.TextField(
        label="邮箱",
        border_color=sc.border,
        bgcolor=sc.surface,
        color=sc.text,
        focused_border_color=sc.accent,
    )
    password = ft.TextField(
        label="密码",
        password=True,
        can_reveal_password=True,
        border_color=sc.border,
        bgcolor=sc.surface,
        color=sc.text,
        focused_border_color=sc.accent,
    )

    def submit(_: ft.ControlEvent) -> None:
        MockService.instance().register(
            name.value or "",
            email.value or "",
            password.value or "",
        )
        on_success()

    return ft.Container(
        expand=True,
        bgcolor=sc.canvas,
        padding=24,
        content=ft.Column(
            [
                ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=sc.text, on_click=lambda e: on_back()),
                ft.Text("注册", size=28, weight=ft.FontWeight.BOLD, color=sc.text),
                ft.Text("创建你的健动账号", size=14, color=sc.text_secondary),
                ft.Container(height=20),
                name,
                email,
                password,
                ft.Container(height=12),
                ft.FilledButton(
                    "注册并进入",
                    bgcolor=sc.accent,
                    color=sc.on_cta,
                    on_click=submit,
                    height=48,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=24)),
                ),
            ]
        ),
    )
