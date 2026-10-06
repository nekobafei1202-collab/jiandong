from __future__ import annotations

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


def build_register(page: ft.Page, *, on_success, on_back) -> ft.Control:
    name = ft.TextField(label="昵称", border_color=SHELL_BORDER, bgcolor=SHELL_SURFACE)
    email = ft.TextField(label="邮箱", border_color=SHELL_BORDER, bgcolor=SHELL_SURFACE)
    password = ft.TextField(
        label="密码",
        password=True,
        can_reveal_password=True,
        border_color=SHELL_BORDER,
        bgcolor=SHELL_SURFACE,
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
        bgcolor=SHELL_CANVAS,
        padding=24,
        content=ft.Column(
            [
                ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: on_back()),
                ft.Text("注册", size=28, weight=ft.FontWeight.BOLD, color=SHELL_TEXT),
                ft.Text("创建你的健动账号", size=14, color=SHELL_TEXT_SECONDARY),
                ft.Container(height=20),
                name,
                email,
                password,
                ft.Container(height=12),
                ft.FilledButton(
                    "注册并进入",
                    bgcolor=SHELL_ACCENT,
                    color="white",
                    on_click=submit,
                    height=48,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=24)),
                ),
            ]
        ),
    )
