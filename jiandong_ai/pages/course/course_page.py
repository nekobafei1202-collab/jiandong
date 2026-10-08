from __future__ import annotations

import flet as ft

from jiandong_ai.app.theme import SHELL_RADIUS_CARD, ShellColors
from jiandong_ai.services.action_guide_catalog import ActionGuideCatalog
from jiandong_ai.services.mock_service import MockService
from jiandong_ai.widgets.course_cover import action_thumb, course_cover
from jiandong_ai.widgets.motion import expanding_filter_chip


class CourseView(ft.Container):
    def __init__(self, page: ft.Page, *, on_start_training) -> None:
        super().__init__(expand=True, bgcolor=ShellColors.canvas, padding=0)
        self._host = page
        self.on_start_training = on_start_training
        self._svc = MockService.instance()
        self._category = "全部"
        self._keyword = ""
        self._cats = ["全部", "新手", "上肢", "下肢", "核心", "拉伸"]
        self._search = ft.TextField(
            hint_text="搜索课程",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=SHELL_RADIUS_CARD,
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
                    ft.Icon(ft.Icons.SEARCH_OFF, size=40, color=ShellColors.text_tertiary),
                    ft.Text("换个关键词试试", color=ShellColors.text_secondary),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                tight=True,
            ),
        )
        self._title = ft.Text("课程", size=22, weight=ft.FontWeight.W_700, color=ShellColors.text)
        self._body = ft.Column(
            [
                ft.Container(
                    padding=ft.Padding.only(left=20, top=20, right=20, bottom=12),
                    content=self._title,
                ),
                ft.Container(padding=ft.Padding.symmetric(horizontal=20), content=self._search),
                ft.Container(height=16),
                ft.Container(height=40, padding=ft.Padding.symmetric(horizontal=20), content=self._chips),
                ft.Container(height=12),
                ft.Stack([self._grid, self._empty], expand=True),
            ],
            expand=True,
            spacing=0,
        )
        self._detail = ft.Container(expand=True, visible=False, bgcolor=ShellColors.canvas)
        self.content = ft.Stack([self._body, self._detail], expand=True)
        self.refresh()

    def on_show(self) -> None:
        self._close_detail()
        self.refresh()

    def _style_search(self) -> None:
        sc = ShellColors
        self._search.bgcolor = sc.surface
        self._search.border_color = sc.border
        self._search.focused_border_color = sc.accent
        self._search.color = sc.text
        self._search.cursor_color = sc.accent

    def _on_search(self, e: ft.ControlEvent) -> None:
        self._keyword = e.control.value or ""
        self.refresh()

    def _set_cat(self, name: str) -> None:
        self._category = name
        self.refresh()

    def _rebuild_chips(self) -> None:
        self._chips.controls.clear()
        for c in self._cats:
            self._chips.controls.append(
                expanding_filter_chip(
                    self._host,
                    label=c,
                    selected=c == self._category,
                    on_selected=lambda name=c: self._set_cat(name),
                )
            )

    def refresh(self) -> None:
        sc = ShellColors
        self.bgcolor = sc.canvas
        self._detail.bgcolor = sc.canvas
        self._title.color = sc.text
        self._style_search()
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
        sc = ShellColors
        return ft.Container(
            bgcolor=sc.surface,
            border=ft.Border.all(1, sc.border),
            border_radius=SHELL_RADIUS_CARD,
            padding=12,
            on_click=lambda e, c=course: self._open_detail(c),
            content=ft.Column(
                [
                    course_cover(exercise=course, height=110, border_radius=12),
                    ft.Text(
                        course.name,
                        size=15,
                        weight=ft.FontWeight.W_600,
                        color=sc.text,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        f"{course.duration} 分钟 · {course.difficulty}",
                        size=12,
                        color=sc.text_secondary,
                    ),
                    ft.Text(course.category, size=11, color=sc.accent),
                ],
                spacing=8,
                tight=True,
            ),
        )

    def open_course(self, course) -> None:
        """Public entry for other tabs (e.g. Home featured cards)."""
        self._open_detail(course)

    def _open_detail(self, course) -> None:
        sc = ShellColors
        action_rows: list[ft.Control] = []
        for a in course.actions:
            guide = ActionGuideCatalog.for_name(a)
            action_rows.append(
                ft.Container(
                    padding=ft.Padding.symmetric(vertical=8),
                    content=ft.Row(
                        [
                            action_thumb(a, size=56),
                            ft.Column(
                                [
                                    ft.Text(a, size=14, weight=ft.FontWeight.W_600, color=sc.text),
                                    ft.Text(
                                        guide.summary,
                                        size=12,
                                        color=sc.text_secondary,
                                        max_lines=2,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                spacing=4,
                                expand=True,
                                tight=True,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        def start(_: ft.ControlEvent) -> None:
            acts = list(course.actions) if course.actions else ["深蹲"]
            self._close_detail()
            self.on_start_training(actions=acts, session_title=course.name)

        self._detail.content = ft.Column(
            [
                ft.Container(
                    height=220,
                    content=ft.Stack(
                        [
                            course_cover(exercise=course, height=220, show_bottom_fade=True),
                            ft.Container(
                                padding=ft.Padding.all(8),
                                content=ft.IconButton(
                                    icon=ft.Icons.ARROW_BACK,
                                    icon_color="white",
                                    on_click=lambda e: self._close_detail(),
                                ),
                            ),
                        ]
                    ),
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.all(20),
                    bgcolor=sc.canvas,
                    content=ft.Column(
                        [
                            ft.Text(course.name, size=22, weight=ft.FontWeight.W_700, color=sc.text),
                            ft.Text(
                                f"{course.duration} 分钟 · {course.difficulty} · {course.category}",
                                size=13,
                                color=sc.text_secondary,
                            ),
                            ft.Container(height=8),
                            ft.Text(course.description, size=14, color=sc.text_secondary),
                            ft.Container(height=16),
                            ft.Text("动作安排", size=16, weight=ft.FontWeight.W_600, color=sc.text),
                            ft.Column(action_rows, spacing=4, scroll=ft.ScrollMode.AUTO, expand=True),
                            ft.FilledButton(
                                "开始训练",
                                bgcolor=sc.accent,
                                color=sc.on_cta,
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
        self.update()

    def _close_detail(self) -> None:
        self._detail.visible = False
        self._body.visible = True
        try:
            self.update()
        except Exception:
            pass
