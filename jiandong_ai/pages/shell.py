from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import flet as ft

from jiandong_ai.app.back_navigation import close_plan_editor_if_open
from jiandong_ai.app.theme import ShellColors
from jiandong_ai.ai.session.android_bridge_session import (
    is_android_runtime,
    write_voice_flag,
)
from jiandong_ai.ai.session.assistant_session import AssistantSession
from jiandong_ai.ai.session.voice_session import VoiceCourseSession
from jiandong_ai.services.ai_assistant import DeepSeekAssistant
from jiandong_ai.services.body_part_recommender import PART_DISPLAY
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
    _VOICE_ENABLED_GREETING = "语音辅助模式已开启。可以说：腿部、核心、上肢、背部，或全身。"

    def __init__(self, page: ft.Page, *, initial_index: int = 0, skip_voice_onboarding: bool = False) -> None:
        super().__init__(expand=True, spacing=0)
        self._host = page
        self._index = initial_index
        self._body = ft.Container(expand=True, bgcolor=ShellColors.canvas)
        self._nav_host = ft.Container(visible=True)
        self._voice_session = None
        self._assistant_session = None
        self._voice_onboarding_done = skip_voice_onboarding

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
                on_voice_accessibility_changed=self._on_voice_accessibility_changed,
                on_ai_assistant_changed=self._on_ai_assistant_changed,
                on_ai_api_key_changed=self._on_ai_api_key_changed,
            ),
        ]

        self._nav_host.content = self._wrap_nav(self._build_nav())
        self.controls = [self._body, self._nav_host]
        self._back_loop_running = False
        self._back_thread: threading.Thread | None = None
        self._show(self._index)
        self._install_system_back(page)
        self._maybe_start_voice_session()

    def _maybe_start_voice_session(self) -> None:
        """无障碍开关打开且处于 Android 运行时才启动语音选课轮询（桌面完全惰性）。"""
        self.start_voice_session_if_needed()

    def _on_voice_accessibility_changed(self, enabled: bool) -> None:
        if enabled:
            self.start_voice_session_if_needed(announce_enabled=True)
        else:
            self.stop_voice_session()

    def _on_ai_assistant_changed(self, enabled: bool) -> None:
        if enabled:
            self._start_assistant_session_if_needed()
        else:
            self._stop_assistant_session()

    def _on_ai_api_key_changed(self, _configured: bool) -> None:
        """Recreate the client so a saved or cleared key takes effect immediately."""
        self._stop_assistant_session()
        self._start_assistant_session_if_needed()

    def start_voice_session_if_needed(self, *, announce_enabled: bool = False) -> bool:
        """按当前设置启动语音选课会话；重复调用只保留一个会话。"""
        if not is_android_runtime():
            return False
        enabled = MockService.instance().get_voice_accessibility()
        if not enabled:
            if self._voice_session is not None:
                self.stop_voice_session()
            else:
                write_voice_flag(False)
            return False
        if self._voice_session is not None:
            return True
        write_voice_flag(True)

        def _start(actions: list[str], title: str) -> None:
            def apply() -> None:
                self._voice_onboarding_done = True
                self.go_training(actions=list(actions), session_title=title)

            try:
                self._host.run_thread(apply)
            except Exception:
                apply()

        session = VoiceCourseSession(on_start_training=_start)
        if not session.start():
            return False
        self._voice_session = session
        session.begin(self._VOICE_ENABLED_GREETING if announce_enabled else None)
        self._start_assistant_session_if_needed()
        return True

    def _start_assistant_session_if_needed(self) -> bool:
        """AI 助手是语音辅助的子功能；无选课会话或子开关关闭时不启动。"""
        if self._assistant_session is not None:
            return True
        if not is_android_runtime():
            return False
        svc = MockService.instance()
        if not svc.get_voice_accessibility() or not svc.get_ai_assistant_enabled():
            return False
        voice = self._voice_session
        if voice is None:
            return False

        def recommend(part: str) -> str:
            voice.handle_keyword(PART_DISPLAY.get(part, "全身"))
            # VoiceCourseSession has already announced the detailed recommendation.
            return ""

        def control(command: str) -> str:
            if command == "start":
                def apply() -> None:
                    self.go_training()

                try:
                    self._host.run_thread(apply)
                except Exception:
                    apply()
                return "好的，即将开始今日训练。"
            return "训练中请直接说：暂停训练、继续训练，或结束训练。"

        def query_plan() -> str:
            actions = svc.get_today_plan_actions()
            if not actions:
                return "今天还没有训练计划。"
            return "今天的训练计划是：" + "、".join(actions) + "。"

        def navigate(destination: str) -> str:
            def apply() -> None:
                if destination == "plan":
                    self._open_plan()
                else:
                    self.go_tab({"home": 0, "courses": 1, "profile": 4}[destination])
            self._host.run_thread(apply)
            return "好的，正在打开。"

        session = AssistantSession(
            ai_client=DeepSeekAssistant(),
            speaker=voice.speak,
            on_recommend=recommend,
            on_control=control,
            on_query_plan=query_plan,
            on_navigate=navigate,
            poll_interval=0.05,
        )
        if not session.start():
            return False
        self._assistant_session = session
        return True

    def _stop_assistant_session(self) -> None:
        session = self._assistant_session
        self._assistant_session = None
        if session is not None:
            try:
                session.stop()
            except Exception:
                pass

    def stop_voice_session(self) -> None:
        """立即停止 Python 轮询并同步 Kotlin 总开关；关闭时保持静默。"""
        self._stop_assistant_session()
        session = self._voice_session
        self._voice_session = None
        if session is not None:
            try:
                session.stop()
            except Exception:
                pass
        if not is_android_runtime():
            return
        try:
            write_voice_flag(False)
        except Exception:
            pass

    def _show_voice_onboarding(
        self,
        *,
        action: str | None,
        actions: list[str] | None,
        session_title: str | None,
    ) -> None:
        from jiandong_ai.pages.training.voice_onboarding_page import (
            build_voice_onboarding,
        )

        page = self._host

        def done(_use_voice: bool) -> None:
            # onboarding 会 remount MainShell；先停掉旧实例的语音会话，避免双消费者。
            self.stop_voice_session()
            shell = MainShell(page, skip_voice_onboarding=True)
            mount(page, shell, safe=False)
            shell.go_training(action, actions=actions, session_title=session_title)

        mount(page, build_voice_onboarding(page, on_finish=done))

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

        # 已开启语音辅助时直接进入相机，不能再插入必须手点的引导页。
        svc = MockService.instance()
        self._voice_onboarding_done = True

        training: TrainingView = self._views[self.training_tab_index]  # type: ignore[assignment]
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
        self._stop_assistant_session()
        if self._voice_session is not None:
            self._voice_session.stop()
            self._voice_session = None
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
