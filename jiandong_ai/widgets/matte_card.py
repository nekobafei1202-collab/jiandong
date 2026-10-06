from __future__ import annotations

import flet as ft

from jiandong_ai.app.theme import SHELL_BORDER, SHELL_RADIUS_CARD, SHELL_SURFACE


def matte_card(content: ft.Control, *, padding=16, expand: bool = False) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=SHELL_SURFACE,
        border=ft.Border.all(1, SHELL_BORDER),
        border_radius=SHELL_RADIUS_CARD,
        padding=padding,
        expand=expand,
    )
