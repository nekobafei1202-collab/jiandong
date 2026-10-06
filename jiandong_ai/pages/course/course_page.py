from __future__ import annotations

import flet as ft

from jiandong_ai.app.theme import (
    SHELL_ACCENT,
    SHELL_BORDER,
    SHELL_CANVAS,
    SHELL_ON_CTA,
    SHELL_RADIUS_CARD,
    SHELL_SURFACE,
    SHELL_SURFACE_MUTED,
    SHELL_TEXT,
    SHELL_TEXT_SECONDARY,
    SHELL_TEXT_TERTIARY,
)
from jiandong_ai.services.mock_service import MockService


class CourseView(ft.Container):
    def __init__(self, page: ft.Page, *, on_start_training) -> None:
        super().__init__(expand=True, bgcolor=SHELL_CANVAS, padding=0)
        self._host = page
        self.on_start_training = on_start_training
        self._svc = MockService.instance()
        self._category = "全部"
        self._keyword = ""
        self._cats = ["全部", "新手", "上肢", "下肢", "核心", "拉伸"]
        self._search = ft.TextField(
            hint_text="搜索课程",
            prefix_icon=ft.Icons.SEARCH,
            bgcolor=SHELL_SURFACE,
            border_color=SHELL_BORDER,
            focused_border_color=SHELL_ACCENT,
            border_radius=SHELL_RADIUS_CARD,
            color=SHELL_TEXT,
            cursor_color=SHELL_ACCENT,
            on_change=self._on_search,
            content_padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        )
        self._chips = ft.Row(spacing=8, scroll=ft.ScrollMode.AUTO)
        self._grid = ft.GridView(
            expand=True,
            runs_count=2,
            max_extent=220,
            child_aspect_ratio=0.72,
            spacing=12,
            run_spacing=12,
            padding=ft.Padding.only(left=20, top=8, right=20, bottom=28),
        )
        self._empty = ft.Container(
            expand=True,
            visible=False,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.SEARCH_OFF, size=40, color=SHELL_TEXT_TERTIARY),
                    ft.Text("换个关键词试试", color=SHELL_TEXT_SECONDARY),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                tight=True,
            ),
        )
        self._body = ft.Column(
            [
                ft.Container(
                    padding=ft.Padding.only(left=20, top=20, right=20, bottom=12),
                    content=ft.Text("课程", size=22, weight=ft.FontWeight.W_700, color=SHELL_TEXT),
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=20),
                    content=self._search,
                ),
                ft.Container(height=16),
                ft.Container(
                    height=40,
                    padding=ft.Padding.symmetric(horizontal=20),
                    content=self._chips,
                ),
                ft.Container(height=12),
                ft.Stack([self._grid, self._empty], expand=True),
            ],
            expand=True,
            spacing=0,
        )
        self._detail = ft.Container(expand=True, visible=False, bgcolor=SHELL_CANVAS)
        self.content = ft.Stack([self._body, self._detail], expand=True)
        self.refresh()

    def on_show(self) -> None:
        self._close_detail()
        self.refresh()

    def _on_search(self, e: ft.ControlEvent) -> None:
        self._keyword = e.control.value or ""
        self.refresh()

    def _set_cat(self, name: str) -> None:
        self._category = name
        self.refresh()

    def _rebuild_chips(self) -> None:
        self._chips.controls.clear()
        for c in self._cats:
            selected = c == self._category
            self._chips.controls.append(
                ft.Container(
                    bgcolor=SHELL_ACCENT if selected else SHELL_SURFACE,
                    border=ft.Border.all(1, SHELL_ACCENT if selected else SHELL_BORDER),
                    border_radius=999,
                    padding=ft.Padding.symmetric(horizontal=18 if selected else 14, vertical=8),
                    on_click=lambda e, name=c: self._set_cat(name),
                    content=ft.Text(
                        c,
                        size=13,
                        weight=ft.FontWeight.W_600,
                        color=SHELL_ON_CTA if selected else SHELL_TEXT,
                    ),
                )
            )

    def refresh(self) -> None:
        self._rebuild_chips()
        courses = self._svc.get_courses(self._category)
        key = self._keyword.strip()
        if key:
            courses = [c for c in courses if key in c.name]
        self._grid.controls.clear()
        if not courses:
            self._grid.visible = False
            self._empty.visible = True
        else:
            self._grid.visible = True
            self._empty.visible = False
            for c in courses:
                self._grid.controls.append(self._course_card(c))
        if self._host:
            try:
                self.update()
            except Exception:
                pass

    def _course_card(self, course) -> ft.Control:
        return ft.Container(
            bgcolor=SHELL_SURFACE,
            border=ft.Border.all(1, SHELL_BORDER),
            border_radius=SHELL_RADIUS_CARD,
            padding=12,
            on_click=lambda e, c=course: self._open_detail(c),
            content=ft.Column(
                [
                    ft.Container(
                        height=110,
                        border_radius=12,
                        bgcolor=SHELL_SURFACE_MUTED,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.FITNESS_CENTER, color=SHELL_ACCENT, size=32),
                    ),
                    ft.Text(
                        course.name,
                        size=15,
                        weight=ft.FontWeight.W_600,
                        color=SHELL_TEXT,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        f"{course.duration} 分钟 · {course.difficulty}",
                        size=12,
                        color=SHELL_TEXT_SECONDARY,
                    ),
                    ft.Text(course.category, size=11, color=SHELL_ACCENT),
                ],
                spacing=8,
                tight=True,
            ),
        )

    def _open_detail(self, course) -> None:
        actions = ft.Column(
            [ft.Text(f"· {a}", color=SHELL_TEXT, size=14) for a in course.actions],
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        def start(_: ft.ControlEvent) -> None:
            pick = next(
                (a for a in course.actions if a not in {"热身", "拉伸"}),
                course.actions[0] if course.actions else "深蹲",
            )
            self._close_detail()
            self.on_start_training(pick)

        self._detail.content = ft.Column(
            [
                ft.Container(
                    height=220,
                    bgcolor=SHELL_SURFACE_MUTED,
                    content=ft.Stack(
                        [
                            ft.Container(
                                expand=True,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.FITNESS_CENTER, size=64, color=SHELL_ACCENT),
                            ),
                            ft.Container(
                                padding=ft.Padding.all(8),
                                content=ft.IconButton(
                                    icon=ft.Icons.ARROW_BACK,
                                    icon_color=SHELL_TEXT,
                                    on_click=lambda e: self._close_detail(),
                                ),
                            ),
                        ]
                    ),
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.all(20),
                    content=ft.Column(
                        [
                            ft.Text(course.name, size=22, weight=ft.FontWeight.W_700, color=SHELL_TEXT),
                            ft.Text(
                                f"{course.duration} 分钟 · {course.difficulty} · {course.category}",
                                size=13,
                                color=SHELL_TEXT_SECONDARY,
                            ),
                            ft.Container(height=8),
                            ft.Text(course.description, size=14, color=SHELL_TEXT_SECONDARY),
                            ft.Container(height=16),
                            ft.Text("动作安排", size=16, weight=ft.FontWeight.W_600, color=SHELL_TEXT),
                            actions,
                            ft.FilledButton(
                                "开始训练",
                                bgcolor=SHELL_ACCENT,
                                color=SHELL_ON_CTA,
                                height=52,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=999)),
                                on_click=start,
                            ),
                        ],
                        expand=True,
                        spacing=8,
                    ),
                ),
            ],
            expand=True,
            spacing=0,
        )
        self._body.visible = False
        self._detail.visible = True
        try:
            self.update()
        except Exception:
            pass

    def _close_detail(self) -> None:
        self._detail.visible = False
        self._body.visible = True
        if self._host:
            try:
                self.update()
            except Exception:
                pass
