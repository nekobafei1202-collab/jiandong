from __future__ import annotations

import flet as ft

from jiandong_ai.app.theme import (
    SHELL_ACCENT,
    SHELL_ACCENT_DARK,
    SHELL_CANVAS,
    SHELL_DIVIDER,
    SHELL_ON_CTA,
    SHELL_SURFACE,
    SHELL_TEXT,
    SHELL_TEXT_TERTIARY,
)
from jiandong_ai.pages.auth.login_page import build_login
from jiandong_ai.pages.auth.register_page import build_register
from jiandong_ai.pages.course.course_page import CourseView
from jiandong_ai.pages.home.home_page import HomeView
from jiandong_ai.pages.home.plan_editor_page import open_plan_editor
from jiandong_ai.pages.profile.profile_page import ProfileView
from jiandong_ai.pages.records.records_page import RecordsView
from jiandong_ai.pages.training.training_page import TrainingView
from jiandong_ai.services.mock_service import AppSession


class MainShell(ft.Column):
    """Catalog shell: home default; hide bottom nav on training tab."""

    training_tab_index = 2

    def __init__(self, page: ft.Page, *, initial_index: int = 0) -> None:
        super().__init__(expand=True, spacing=0)
        self._host = page
        self._index = initial_index
        self._body = ft.Container(expand=True, bgcolor=SHELL_CANVAS)
        self._nav_host = ft.Container(visible=True)

        self._views: list[ft.Control] = [
            HomeView(
                page,
                on_start_training=self.go_training,
                on_open_courses=lambda: self.go_tab(1),
            ),
            CourseView(page, on_start_training=self.go_training),
            TrainingView(page, on_close=lambda: self.go_tab(0)),
            RecordsView(page),
            ProfileView(
                page,
                on_logout=self._logout_to_login,
                on_open_records=lambda: self.go_tab(3),
                on_open_plan=self._open_plan,
            ),
        ]

        self._nav_host.content = self._build_nav()
        self.controls = [self._body, self._nav_host]
        self._show(self._index)

    # ---- public navigation ----

    def go_training(self, action: str | None = None) -> None:
        training: TrainingView = self._views[self.training_tab_index]  # type: ignore[assignment]
        if action:
            training.set_action(action)
        self.go_tab(self.training_tab_index)

    def go_tab(self, i: int) -> None:
        if i < 0 or i >= len(self._views):
            return
        self._index = i
        self._show(i)

    # ---- internals ----

    def _logout_to_login(self) -> None:
        AppSession.clear()
        page = self._host

        def go_register(_: ft.ControlEvent | None = None) -> None:
            page.controls.clear()
            page.add(build_register(page, on_success=go_shell, on_back=go_login))
            page.update()

        def go_shell(_: ft.ControlEvent | None = None) -> None:
            page.controls.clear()
            page.add(MainShell(page))
            page.update()

        def go_login(_: ft.ControlEvent | None = None) -> None:
            page.controls.clear()
            page.add(build_login(page, on_success=go_shell, on_register=go_register))
            page.update()

        go_login()

    def _open_plan(self) -> None:
        home: HomeView = self._views[0]  # type: ignore[assignment]
        open_plan_editor(self._host, on_saved=home.refresh)

    def _build_nav(self) -> ft.Control:
        items = [
            ("首页", ft.Icons.HOME_OUTLINED, ft.Icons.HOME, 0),
            ("课程", ft.Icons.GRID_VIEW_OUTLINED, ft.Icons.GRID_VIEW, 1),
            ("训练", None, None, 2),  # custom play button
            ("记录", ft.Icons.BAR_CHART_OUTLINED, ft.Icons.BAR_CHART, 3),
            ("我的", ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON, 4),
        ]
        children: list[ft.Control] = []
        for label, icon, active_icon, idx in items:
            selected = self._index == idx
            if idx == self.training_tab_index:
                children.append(self._training_nav_item(selected=selected))
                continue
            color = SHELL_ACCENT if selected else SHELL_TEXT_TERTIARY
            children.append(
                ft.Container(
                    expand=True,
                    on_click=lambda e, i=idx: self.go_tab(i),
                    content=ft.Column(
                        [
                            ft.Icon(active_icon if selected else icon, color=color, size=24),
                            ft.Text(
                                label,
                                size=12,
                                weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_500,
                                color=color,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                        tight=True,
                    ),
                    padding=ft.Padding.symmetric(vertical=8),
                    alignment=ft.Alignment.CENTER,
                )
            )
        return ft.Container(
            bgcolor=SHELL_SURFACE,
            border=ft.Border.only(top=ft.BorderSide(1, SHELL_DIVIDER)),
            padding=ft.Padding.only(bottom=4),
            content=ft.Row(children, spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            height=64,
        )

    def _training_nav_item(self, *, selected: bool) -> ft.Control:
        return ft.Container(
            expand=True,
            on_click=lambda e: self.go_tab(self.training_tab_index),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(vertical=4),
            content=ft.Column(
                [
                    ft.Container(
                        width=32,
                        height=32,
                        border_radius=999,
                        bgcolor=SHELL_ACCENT_DARK if selected else SHELL_ACCENT,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.PLAY_ARROW, color=SHELL_ON_CTA, size=20),
                    ),
                    ft.Text(
                        "训练",
                        size=12,
                        weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_500,
                        color=SHELL_ACCENT if selected else SHELL_TEXT_TERTIARY,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
                tight=True,
            ),
        )

    def _show(self, index: int) -> None:
        view = self._views[index]
        if hasattr(view, "on_show"):
            view.on_show()
        self._body.content = view
        on_training = index == self.training_tab_index
        self._nav_host.visible = not on_training
        if not on_training:
            self._nav_host.content = self._build_nav()
        try:
            self.update()
        except Exception:
            pass
