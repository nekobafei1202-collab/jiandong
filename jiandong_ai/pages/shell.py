from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import flet as ft

from jiandong_ai.app.back_navigation import close_plan_editor_if_open
from jiandong_ai.app.theme import ShellColors
from jiandong_ai.ai.session.android_bridge_session import is_android_runtime
from jiandong_ai.pages.auth.login_page import build_login
from jiandong_ai.pages.auth.register_page import build_register
from jiandong_ai.pages.course.course_page import CourseView
from jiandong_ai.pages.home.home_page import HomeView
from jiandong_ai.pages.home.plan_editor_page import open_plan_editor
from jiandong_ai.pages.profile.profile_page import ProfileView
from jiandong_ai.pages.records.records_page import RecordsView
from jiandong_ai.pages.training.training_page import TrainingView
from jiandong_ai.services.mock_service import AppSession, MockService
from jiandong_ai.widgets.safe_area import mount, safe_area


class MainShell(ft.Column):
    """Catalog shell: home default; hide bottom nav on training tab."""

    training_tab_index = 2

    def __init__(self, page: ft.Page, *, initial_index: int = 0) -> None:
        super().__init__(expand=True, spacing=0)
        self._host = page
        self._index = initial_index
        self._body = ft.Container(expand=True, bgcolor=ShellColors.canvas)
        self._nav_host = ft.Container(visible=True)

        self._views: list[ft.Control] = [
            HomeView(
                page,
                on_start_training=self.go_training,
                on_open_courses=lambda: self.go_tab(1),
                on_open_course=self.go_course,
            ),
            CourseView(page, on_start_training=self.go_training),
            TrainingView(page, on_close=lambda: self.go_tab(0)),
            RecordsView(page),
            ProfileView(
                page,
                on_logout=self._logout_to_login,
                on_open_records=lambda: self.go_tab(3),
                on_open_plan=self._open_plan,
                on_theme_rebuild=self.apply_theme,
            ),
        ]

        self._nav_host.content = self._wrap_nav(self._build_nav())
        self.controls = [self._body, self._nav_host]
        self._back_loop_running = False
        self._back_thread: threading.Thread | None = None
        self._show(self._index)
        self._install_system_back(page)

    def _bridge_dir(self) -> Path:
        from jiandong_ai.ai.session.android_bridge_session import _default_bridge_dir

        return _default_bridge_dir()

    def _install_system_back(self, page: ft.Page) -> None:
        if not is_android_runtime():
            return

        def view_pop(_: ft.ControlEvent) -> None:
            if self.handle_system_back():
                try:
                    page.update()
                except Exception:
                    pass

        page.on_view_pop = view_pop

        if self._back_thread is not None and self._back_thread.is_alive():
            return
        self._back_loop_running = True
        self._back_thread = threading.Thread(target=self._shell_back_loop, daemon=True)
        self._back_thread.start()

    def _shell_back_loop(self) -> None:
        req = self._bridge_dir() / "shell_back_req.json"
        ack = self._bridge_dir() / "shell_back_ack.json"
        while self._back_loop_running:
            try:
                if not req.exists():
                    time.sleep(0.02)
                    continue
                consumed_box: dict[str, bool] = {"v": False}
                done = threading.Event()

                def apply() -> None:
                    try:
                        consumed_box["v"] = self.handle_system_back()
                        ack.write_text(
                            json.dumps({"consumed": bool(consumed_box["v"])}),
                            encoding="utf-8",
                        )
                        req.unlink(missing_ok=True)
                    except Exception:
                        ack.write_text(json.dumps({"consumed": False}), encoding="utf-8")
                        req.unlink(missing_ok=True)
                    finally:
                        done.set()

                try:
                    self._host.run_thread(apply)
                except Exception:
                    apply()
                done.wait(timeout=0.3)
            except Exception:
                pass
            time.sleep(0.02)

    def handle_system_back(self) -> bool:
        """Return True to stay in app (navigate to home), False to allow exit."""
        if close_plan_editor_if_open():
            self.go_tab(0)
            return True

        training: TrainingView = self._views[self.training_tab_index]  # type: ignore[assignment]
        if self._index == self.training_tab_index:
            phase = getattr(training, "_phase", "idle")
            if phase == "finished":
                training._close()
                return True
            if phase == "running":
                # Mirror the Dart original: back while running pauses, not exits.
                training._pause_session()
                return True
            if phase == "paused":
                training._confirm_end_and_finish()
                return True
            if phase == "preview":
                training._stop_session(save=False, finish=False)
            self.go_tab(0)
            return True

        if self._index != 0:
            self.go_tab(0)
            return True
        return False

    def apply_theme(self) -> None:
        """Rebuild shell chrome + visible catalog tab after theme flip (skip training HUD)."""
        self._body.bgcolor = ShellColors.canvas
        self._host.bgcolor = ShellColors.canvas
        if self._index != self.training_tab_index:
            self._nav_host.content = self._wrap_nav(self._build_nav())
            view = self._views[self._index]
            if hasattr(view, "refresh"):
                view.refresh()
            elif hasattr(view, "on_show"):
                view.on_show()
            # Re-wrap catalog body after theme (view tree may refresh in place).
            self._body.content = safe_area(view, bottom=False)
        try:
            self.update()
        except Exception:
            pass

    def go_training(
        self,
        action: str | None = None,
        *,
        actions: list[str] | None = None,
        session_title: str | None = None,
    ) -> None:
        from jiandong_ai.ai.action.exercise_kind import ExerciseKind

        training: TrainingView = self._views[self.training_tab_index]  # type: ignore[assignment]
        svc = MockService.instance()
        start_index = 0
        today = svc.get_today_plan_actions()
        if actions:
            plan_actions = list(actions)
            if plan_actions == today:
                start_index = svc.first_incomplete_plan_index()
        elif action:
            plan_actions = [action]
        else:
            plan_actions = today
            start_index = svc.first_incomplete_plan_index()

        title = session_title
        if not title:
            if plan_actions == today and len(plan_actions) > 1:
                title = "今日计划"
            elif len(plan_actions) == 1:
                title = ExerciseKind.display_name(plan_actions[0])
            else:
                title = "训练"

        # Launch native preview BEFORE switching tab so Flet never paints a black flash.
        training.prepare_native_entry(
            actions=plan_actions,
            action_index=start_index,
            session_title=title,
        )
        if training._uses_native_preview():
            training.launch_native_preview()
        self.go_tab(self.training_tab_index)

    def go_tab(self, i: int) -> None:
        if i < 0 or i >= len(self._views):
            return
        self._index = i
        self._show(i)

    def go_course(self, course) -> None:
        """Switch to the Courses tab and open that course's detail."""
        self.go_tab(1)
        course_view: CourseView = self._views[1]  # type: ignore[assignment]
        course_view.open_course(course)

    def _logout_to_login(self) -> None:
        AppSession.clear()
        page = self._host

        def go_register(_: ft.ControlEvent | None = None) -> None:
            page.bgcolor = ShellColors.canvas
            mount(page, build_register(page, on_success=go_shell, on_back=go_login))

        def go_shell(_: ft.ControlEvent | None = None) -> None:
            page.bgcolor = ShellColors.canvas
            mount(page, MainShell(page), safe=False)

        def go_login(_: ft.ControlEvent | None = None) -> None:
            page.bgcolor = ShellColors.canvas
            mount(page, build_login(page, on_success=go_shell, on_register=go_register))

        go_login()

    @staticmethod
    def _wrap_nav(nav: ft.Control) -> ft.Control:
        return safe_area(nav, top=False, expand=False)

    def _open_plan(self) -> None:
        home: HomeView = self._views[0]  # type: ignore[assignment]
        open_plan_editor(
            self._host,
            on_saved=home.refresh,
            on_start_training=self.go_training,
        )

    def _build_nav(self) -> ft.Control:
        sc = ShellColors
        items = [
            ("首页", ft.Icons.HOME_OUTLINED, ft.Icons.HOME, 0),
            ("课程", ft.Icons.GRID_VIEW_OUTLINED, ft.Icons.GRID_VIEW, 1),
            ("训练", None, None, 2),
            ("记录", ft.Icons.BAR_CHART_OUTLINED, ft.Icons.BAR_CHART, 3),
            ("我的", ft.Icons.PERSON_OUTLINE, ft.Icons.PERSON, 4),
        ]
        children: list[ft.Control] = []
        for label, icon, active_icon, idx in items:
            selected = self._index == idx
            if idx == self.training_tab_index:
                children.append(self._training_nav_item(selected=selected))
                continue
            color = sc.accent if selected else sc.text_tertiary
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
            bgcolor=sc.surface,
            border=ft.Border.only(top=ft.BorderSide(1, sc.divider)),
            padding=ft.Padding.only(bottom=4),
            content=ft.Row(children, spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            height=64,
        )

    def _training_nav_item(self, *, selected: bool) -> ft.Control:
        sc = ShellColors
        return ft.Container(
            expand=True,
            on_click=lambda e: self.go_training(),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(vertical=4),
            content=ft.Column(
                [
                    ft.Container(
                        width=32,
                        height=32,
                        border_radius=999,
                        bgcolor=sc.accent_dark if selected else sc.accent,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.PLAY_ARROW, color=sc.on_cta, size=20),
                    ),
                    ft.Text(
                        "训练",
                        size=12,
                        weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_500,
                        color=sc.accent if selected else sc.text_tertiary,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
                tight=True,
            ),
        )

    def _show(self, index: int) -> None:
        view = self._views[index]
        on_training = index == self.training_tab_index
        # Mount into the tree BEFORE on_show/update — Flet requires controls on-page.
        self._body.content = view if on_training else safe_area(view, bottom=False)
        self._body.bgcolor = ShellColors.canvas
        self._nav_host.visible = not on_training
        if not on_training:
            self._nav_host.content = self._wrap_nav(self._build_nav())
        try:
            self.update()
        except Exception:
            pass
        if hasattr(view, "on_show"):
            view.on_show()
