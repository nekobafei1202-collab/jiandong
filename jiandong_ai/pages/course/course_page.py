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


class CourseView(ft.Container):
    def __init__(self, page: ft.Page, *, on_start_training) -> None:
        super().__init__(expand=True, bgcolor=SHELL_CANVAS, padding=16)
        self.page = page
        self.on_start_training = on_start_training
        self._svc = MockService.instance()
        self._category = "全部"
        self._list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
        cats = ["全部", "新手", "下肢", "核心", "上肢", "拉伸"]
        self._chips = ft.Row(
            [
                ft.TextButton(
                    c,
                    on_click=lambda e, name=c: self._set_cat(name),
                )
                for c in cats
            ],
            scroll=ft.ScrollMode.AUTO,
        )
        self.content = ft.Column(
            [
                ft.Text("课程", size=24, weight=ft.FontWeight.BOLD, color=SHELL_TEXT),
                self._chips,
                self._list,
            ],
            expand=True,
            spacing=12,
        )
        self.refresh()

    def _set_cat(self, name: str) -> None:
        self._category = name
        self.refresh()

    def refresh(self) -> None:
        self._list.controls.clear()
        for c in self._svc.get_courses(self._category):
            self._list.controls.append(
                ft.Container(
                    bgcolor=SHELL_SURFACE,
                    border=ft.border.all(1, SHELL_BORDER),
                    border_radius=12,
                    padding=14,
                    on_click=lambda e, course=c: self._open_detail(course),
                    content=ft.Column(
                        [
                            ft.Text(c.name, size=16, weight=ft.FontWeight.W_600, color=SHELL_TEXT),
                            ft.Text(
                                f"{c.duration} 分钟 · {c.difficulty} · {c.category}",
                                size=12,
                                color=SHELL_TEXT_SECONDARY,
                            ),
                            ft.Text(c.description, size=12, color=SHELL_TEXT_SECONDARY, max_lines=2),
                        ],
                        spacing=4,
                    ),
                )
            )
        if self.page:
            self.update()

    def _open_detail(self, course) -> None:
        actions = ft.Column(
            [ft.Text(f"· {a}", color=SHELL_TEXT) for a in course.actions],
            spacing=4,
        )

        def start(_: ft.ControlEvent) -> None:
            page = self.page
            page.close(dlg)
            # Start first auto-friendly action if present
            pick = next((a for a in course.actions if a not in {"热身", "拉伸"}), course.actions[0] if course.actions else "深蹲")
            self.on_start_training(pick)

        dlg = ft.AlertDialog(
            title=ft.Text(course.name),
            content=ft.Column(
                [
                    ft.Text(course.description, color=SHELL_TEXT_SECONDARY),
                    ft.Container(height=8),
                    ft.Text("动作安排", weight=ft.FontWeight.W_600),
                    actions,
                ],
                tight=True,
                height=280,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("关闭", on_click=lambda e: self.page.close(dlg)),
                ft.FilledButton("开始训练", bgcolor=SHELL_ACCENT, on_click=start),
            ],
        )
        self.page.open(dlg)

    def on_show(self) -> None:
        self.refresh()
