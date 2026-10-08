from __future__ import annotations

import flet as ft

from jiandong_ai.app.theme import SHELL_RADIUS_CARD, ShellColors


def matte_card(content: ft.Control, *, padding=16, expand: bool = False) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=ShellColors.surface,
        border=ft.Border.all(1, ShellColors.border),
        border_radius=SHELL_RADIUS_CARD,
        padding=padding,
        expand=expand,
    )
