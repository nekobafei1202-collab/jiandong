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
from jiandong_ai.pages.course.course_page import CourseView
from jiandong_ai.pages.home.home_page import HomeView
from jiandong_ai.pages.profile.profile_page import ProfileView
from jiandong_ai.pages.records.records_page import RecordsView
from jiandong_ai.pages.training.training_page import TrainingView


class MainShell(ft.Column):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, spacing=0)
        self.page = page
        self._index = 2  # Training center tab like Keep-style default focus
        self._body = ft.Container(expand=True, bgcolor=SHELL_CANVAS)
        self._nav = ft.NavigationBar(
            bgcolor=SHELL_SURFACE,
            indicator_color=SHELL_ACCENT + "33",
            selected_index=self._index,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="首页"),
                ft.NavigationBarDestination(icon=ft.Icons.GRID_VIEW_OUTLINED, selected_icon=ft.Icons.GRID_VIEW, label="课程"),
                ft.NavigationBarDestination(icon=ft.Icons.FITNESS_CENTER, label="训练"),
                ft.NavigationBarDestination(icon=ft.Icons.BAR_CHART_OUTLINED, selected_icon=ft.Icons.BAR_CHART, label="记录"),
                ft.NavigationBarDestination(icon=ft.Icons.PERSON_OUTLINE, selected_icon=ft.Icons.PERSON, label="我的"),
            ],
            on_change=self._on_nav,
        )
        self.controls = [self._body, self._nav]
        self._views = [
            HomeView(page, on_start_training=self._go_training),
            CourseView(page, on_start_training=self._go_training),
            TrainingView(page),
            RecordsView(page),
            ProfileView(page),
        ]
        self._show(self._index)

    def _go_training(self, action: str | None = None) -> None:
        training: TrainingView = self._views[2]  # type: ignore[assignment]
        if action:
            training.set_action(action)
        self._index = 2
        self._nav.selected_index = 2
        self._show(2)

    def _on_nav(self, e: ft.ControlEvent) -> None:
        self._index = int(e.control.selected_index)
        self._show(self._index)

    def _show(self, index: int) -> None:
        view = self._views[index]
        if hasattr(view, "on_show"):
            view.on_show()
        self._body.content = view
        self._body.border = ft.border.only(bottom=ft.BorderSide(1, SHELL_BORDER))
        self.update()
