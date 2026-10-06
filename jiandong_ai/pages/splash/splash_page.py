from __future__ import annotations

import threading

import flet as ft

from jiandong_ai.app.constants import APP_NAME, APP_TAGLINE
from jiandong_ai.app.theme import SHELL_ACCENT, SHELL_CANVAS, SHELL_TEXT, SHELL_TEXT_SECONDARY


def build_splash(page: ft.Page, *, on_done) -> ft.Control:
    def finish() -> None:
        on_done()

    threading.Timer(1.2, lambda: page.run_thread(finish)).start()

    return ft.Container(
        expand=True,
        bgcolor=SHELL_CANVAS,
        alignment=ft.alignment.center,
        content=ft.Column(
            [
                ft.Text(APP_NAME, size=36, weight=ft.FontWeight.BOLD, color=SHELL_TEXT),
                ft.Text(APP_TAGLINE, size=14, color=SHELL_TEXT_SECONDARY),
                ft.Container(height=24),
                ft.ProgressRing(color=SHELL_ACCENT, width=28, height=28),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    )
