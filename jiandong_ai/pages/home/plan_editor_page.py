from __future__ import annotations

import flet as ft

from jiandong_ai.app.theme import SHELL_ACCENT, SHELL_BORDER, SHELL_SURFACE, SHELL_TEXT
from jiandong_ai.services.mock_service import MockService


def open_plan_editor(page: ft.Page, *, on_saved) -> None:
    svc = MockService.instance()
    pool = ["深蹲", "俯卧撑", "开合跳", "平板支撑", "弓步蹲", "高抬腿", "臀桥", "卷腹", "抬臂"]
    selected = list(svc.get_today_plan_actions())
    chips = ft.Column(spacing=8)

    def rebuild() -> None:
        chips.controls.clear()
        for name in pool:
            active = name in selected

            def toggle(e, n=name) -> None:
                if n in selected:
                    selected.remove(n)
                else:
                    selected.append(n)
                rebuild()
                dlg.update()

            chips.controls.append(
                ft.Container(
                    bgcolor=SHELL_ACCENT if active else SHELL_SURFACE,
                    border=ft.border.all(1, SHELL_BORDER),
                    border_radius=20,
                    padding=ft.padding.symmetric(horizontal=14, vertical=8),
                    on_click=toggle,
                    content=ft.Text(name, color="white" if active else SHELL_TEXT),
                )
            )

    def save(_: ft.ControlEvent) -> None:
        svc.set_today_plan_actions(selected)
        page.close(dlg)
        on_saved()

    rebuild()
    dlg = ft.AlertDialog(
        title=ft.Text("编辑今日计划"),
        content=ft.Container(content=chips, width=320, height=360),
        actions=[
            ft.TextButton("取消", on_click=lambda e: page.close(dlg)),
            ft.FilledButton("保存", bgcolor=SHELL_ACCENT, on_click=save),
        ],
    )
    page.open(dlg)
