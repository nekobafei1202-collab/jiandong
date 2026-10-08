from __future__ import annotations

import flet as ft

from jiandong_ai.app.theme import ShellColors


def section_header(title: str, *, action_label: str | None = None, on_action=None) -> ft.Control:
    trailing: list[ft.Control] = []
    if action_label and on_action:
        trailing.append(
            ft.TextButton(
                action_label,
                style=ft.ButtonStyle(color=ShellColors.accent),
                on_click=lambda e: on_action(),
            )
        )
    return ft.Row(
        [
            ft.Text(title, size=16, weight=ft.FontWeight.W_600, color=ShellColors.text),
            ft.Container(expand=True),
            *trailing,
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
