from __future__ import annotations

import threading

import flet as ft

from jiandong_ai.app.constants import APP_NAME, APP_TAGLINE
from jiandong_ai.app.theme import ShellColors


def build_splash(page: ft.Page, *, on_done) -> ft.Control:
    sc = ShellColors

    def finish() -> None:
        on_done()

    threading.Timer(1.2, lambda: page.run_thread(finish)).start()

    return ft.Container(
        expand=True,
        bgcolor=sc.canvas,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                ft.Text(APP_NAME, size=36, weight=ft.FontWeight.BOLD, color=sc.text),
                ft.Text(APP_TAGLINE, size=14, color=sc.text_secondary),
                ft.Container(height=24),
                ft.ProgressRing(color=sc.accent, width=28, height=28),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    )
