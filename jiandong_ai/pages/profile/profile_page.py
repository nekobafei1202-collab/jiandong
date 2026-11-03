from __future__ import annotations

import flet as ft

from jiandong_ai.app.constants import APP_NAME, APP_TAGLINE
from jiandong_ai.app.theme import ShellColors
from jiandong_ai.app.theme_controller import ThemeController
from jiandong_ai.app.theme_switch import schedule_theme_toggle
from jiandong_ai.services.ai_assistant import (
    clear_deepseek_api_key,
    get_deepseek_api_key_status,
    save_deepseek_api_key,
)
from jiandong_ai.services.mock_service import AppSession, MockService
from jiandong_ai.widgets.matte_card import matte_card


class ProfileView(ft.Container):
    def __init__(
        self,
        page: ft.Page,
        *,
        on_logout=None,
        on_open_records=None,
        on_open_plan=None,
        on_theme_rebuild=None,
        on_voice_accessibility_changed=None,
        on_ai_assistant_changed=None,
        on_ai_api_key_changed=None,
    ) -> None:
        super().__init__(expand=True, bgcolor=ShellColors.canvas, padding=0)
        self._host = page
        self.on_logout = on_logout
        self.on_open_records = on_open_records
        self.on_open_plan = on_open_plan
        self.on_theme_rebuild = on_theme_rebuild
        self.on_voice_accessibility_changed = on_voice_accessibility_changed
        self.on_ai_assistant_changed = on_ai_assistant_changed
        self.on_ai_api_key_changed = on_ai_api_key_changed
        self._svc = MockService.instance()
        self._name = ft.Text("", size=18, weight=ft.FontWeight.W_600, color=ShellColors.text)
        self._email = ft.Text("", size=13, color=ShellColors.text_secondary)
        self._streak = ft.Text("", size=13, weight=ft.FontWeight.W_500, color=ShellColors.accent)
        self._avatar_letter = ft.Text("健", size=22, weight=ft.FontWeight.W_700, color=ShellColors.text)
        self._dark_switch = ft.Switch(
            value=ThemeController.get_is_dark(),
            active_color=ShellColors.accent,
        )
        self._strict_switch = ft.Switch(
            value=self._svc.get_strict_mode(),
            active_color=ShellColors.accent,
            on_change=self._toggle_strict_mode,
        )
        self._voice_switch = ft.Switch(
            value=self._svc.get_voice_accessibility(),
            active_color=ShellColors.accent,
            on_change=self._toggle_voice_accessibility,
        )
        self._voice_correction_switch = ft.Switch(
            value=self._svc.get_voice_correction_announce(),
            active_color=ShellColors.accent,
            on_change=self._toggle_voice_correction,
        )
        self._ai_assistant_switch = ft.Switch(
            value=self._svc.get_ai_assistant_enabled(),
            active_color=ShellColors.accent,
            on_change=self._toggle_ai_assistant,
        )
        self._ai_api_key_field = ft.TextField(
            label="DeepSeek API Key",
            hint_text="在此粘贴 platform.deepseek.com 创建的 Key",
            password=True,
            can_reveal_password=True,
            dense=True,
            text_size=13,
        )
        self._ai_api_key_status = ft.Text(
            get_deepseek_api_key_status(),
            size=12,
            color=ShellColors.text_secondary,
        )
        self._theme_icon = ft.Icon(
            ft.Icons.DARK_MODE if ThemeController.get_is_dark() else ft.Icons.LIGHT_MODE,
            color=ShellColors.accent,
            size=22,
        )
        # Last tap origin — Switch.on_change has no coordinates.
        self._last_theme_origin: tuple[float, float] | None = None
        self._scroll = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self.content = self._scroll
        self._rebuild()

    def on_show(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.bgcolor = ShellColors.canvas
        self._name.color = ShellColors.text
        self._email.color = ShellColors.text_secondary
        self._streak.color = ShellColors.accent
        self._avatar_letter.color = ShellColors.text
        self._dark_switch.value = ThemeController.get_is_dark()
        self._dark_switch.active_color = ShellColors.accent
        self._strict_switch.value = self._svc.get_strict_mode()
        self._strict_switch.active_color = ShellColors.accent
        self._voice_switch.value = self._svc.get_voice_accessibility()
        self._voice_switch.active_color = ShellColors.accent
        self._voice_correction_switch.value = self._svc.get_voice_correction_announce()
        self._voice_correction_switch.active_color = ShellColors.accent
        self._ai_assistant_switch.value = self._svc.get_ai_assistant_enabled()
        self._ai_assistant_switch.active_color = ShellColors.accent
        self._ai_api_key_status.value = get_deepseek_api_key_status()
        self._ai_api_key_status.color = ShellColors.text_secondary
        self._theme_icon.name = (
            ft.Icons.DARK_MODE if ThemeController.get_is_dark() else ft.Icons.LIGHT_MODE
        )
        self._theme_icon.color = ShellColors.accent
        self._rebuild()
        u = self._svc.get_current_user()
        self._name.value = u.name
        self._email.value = u.email
        self._streak.value = f"连续打卡 {self._svc.get_streak_days()} 天"
        self._avatar_letter.value = u.name[0] if u.name else "健"
        try:
            self.update()
        except Exception:
            pass

    def _rebuild(self) -> None:
        sc = ShellColors
        self._scroll.controls = [
            ft.Container(
                padding=ft.Padding.only(left=20, top=20, right=20, bottom=0),
                content=ft.Column(
                    [
                        ft.Text("我的", size=22, weight=ft.FontWeight.W_700, color=sc.text),
                        ft.Container(height=20),
                        ft.Row(
                            [
                                ft.CircleAvatar(
                                    radius=32,
                                    bgcolor=sc.surface_muted,
                                    content=self._avatar_letter,
                                ),
                                ft.Column(
                                    [self._name, self._email, self._streak],
                                    spacing=4,
                                    expand=True,
                                    tight=True,
                                ),
                            ],
                            spacing=16,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Container(height=28),
                        self._menu_group(
                            [
                                ("训练历史", self._tap_records),
                                ("我的计划", self._tap_plan),
                            ]
                        ),
                        ft.Container(height=12),
                        self._menu_group_custom(
                            [
                                self._theme_menu_item(),
                                self._strict_menu_item(),
                                self._menu_item("无障碍训练", on_tap=self._show_accessibility),
                                self._menu_item("设置", on_tap=None, subtitle="即将上线"),
                                self._menu_item("关于", on_tap=self._show_about),
                            ]
                        ),
                        ft.Container(height=28),
                        ft.OutlinedButton(
                            "退出登录",
                            height=48,
                            style=ft.ButtonStyle(
                                color=sc.text,
                                side=ft.BorderSide(1, sc.border),
                                shape=ft.RoundedRectangleBorder(radius=999),
                            ),
                            on_click=self._logout,
                        ),
                        ft.Container(height=28),
                    ],
                    spacing=0,
                    expand=True,
                ),
                expand=True,
            )
        ]

    def _strict_menu_item(self) -> ft.Control:
        sc = ShellColors
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.FACT_CHECK, color=sc.accent, size=22),
                            ft.Column(
                                [
                                    ft.Text(
                                        "严格纠错模式",
                                        size=15,
                                        weight=ft.FontWeight.W_500,
                                        color=sc.text,
                                    ),
                                    ft.Text(
                                        "开启后姿势不标准将不计数；关闭则宽松计数并给出改进建议",
                                        size=12,
                                        color=sc.text_secondary,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                                tight=True,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        expand=True,
                    ),
                    self._strict_switch,
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _toggle_strict_mode(self, e: ft.ControlEvent) -> None:
        self._svc.set_strict_mode(bool(self._strict_switch.value))

    def _toggle_voice_accessibility(self, e: ft.ControlEvent) -> None:
        value = bool(self._voice_switch.value)
        self._svc.set_voice_accessibility(value)
        if self.on_voice_accessibility_changed is not None:
            try:
                self.on_voice_accessibility_changed(value)
                return
            except Exception:
                pass
        # 没有 shell 回调时保留旧的 flag 直写兜底。
        try:
            from jiandong_ai.ai.session.android_bridge_session import (
                is_android_runtime,
                write_voice_flag,
            )

            if is_android_runtime():
                write_voice_flag(value)
        except Exception:
            pass

    def _toggle_voice_correction(self, e: ft.ControlEvent) -> None:
        self._svc.set_voice_correction_announce(bool(self._voice_correction_switch.value))

    def _toggle_ai_assistant(self, e: ft.ControlEvent) -> None:
        value = bool(self._ai_assistant_switch.value)
        self._svc.set_ai_assistant_enabled(value)
        if self.on_ai_assistant_changed is not None:
            try:
                self.on_ai_assistant_changed(value)
            except Exception:
                pass

    def _save_ai_api_key(self, e: ft.ControlEvent | None = None) -> None:
        try:
            save_deepseek_api_key(self._ai_api_key_field.value or "")
        except ValueError as exc:
            self._ai_api_key_field.error_text = str(exc)
            self._safe_update(self._ai_api_key_field)
            return
        except Exception:
            self._ai_api_key_field.error_text = "保存失败，请稍后重试"
            self._safe_update(self._ai_api_key_field)
            return
        self._ai_api_key_field.value = ""
        self._ai_api_key_field.error_text = None
        self._ai_api_key_status.value = get_deepseek_api_key_status()
        self._safe_update(self._ai_api_key_field)
        self._safe_update(self._ai_api_key_status)
        self._notify_ai_api_key_changed(True)

    def _clear_ai_api_key(self, e: ft.ControlEvent | None = None) -> None:
        try:
            clear_deepseek_api_key()
        except Exception:
            self._ai_api_key_status.value = "清除失败，请稍后重试"
            self._safe_update(self._ai_api_key_status)
            return
        self._ai_api_key_field.value = ""
        self._ai_api_key_field.error_text = None
        self._ai_api_key_status.value = get_deepseek_api_key_status()
        self._safe_update(self._ai_api_key_field)
        self._safe_update(self._ai_api_key_status)
        self._notify_ai_api_key_changed(False)

    def _notify_ai_api_key_changed(self, configured: bool) -> None:
        if self.on_ai_api_key_changed is not None:
            try:
                self.on_ai_api_key_changed(configured)
            except Exception:
                pass

    @staticmethod
    def _safe_update(control: ft.Control) -> None:
        try:
            control.update()
        except Exception:
            pass

    def _switch_row(
        self,
        *,
        icon,
        title: str,
        subtitle: str,
        switch: ft.Switch,
    ) -> ft.Control:
        sc = ShellColors
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=4, vertical=6),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, color=sc.accent, size=22),
                            ft.Column(
                                [
                                    ft.Text(
                                        title,
                                        size=15,
                                        weight=ft.FontWeight.W_500,
                                        color=sc.text,
                                    ),
                                    ft.Text(
                                        subtitle,
                                        size=12,
                                        color=sc.text_secondary,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                                tight=True,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        expand=True,
                    ),
                    switch,
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _theme_menu_item(self) -> ft.Control:
        sc = ShellColors
        self._dark_switch.on_change = lambda e: self._toggle_theme(e)

        def on_tap_down(e: ft.ControlEvent) -> None:
            gp = getattr(e, "global_position", None)
            if gp is not None and getattr(gp, "x", None) is not None and getattr(gp, "y", None) is not None:
                self._last_theme_origin = (float(gp.x), float(gp.y))

        def on_row_tap(e: ft.ControlEvent) -> None:
            on_tap_down(e)
            self._toggle_theme(e)

        # GestureDetector: tap_down stores real coords; toggle uses switch-area origin.
        return ft.GestureDetector(
            key="theme_switch_row",
            on_tap_down=on_tap_down,
            on_tap=on_row_tap,
            content=ft.Container(
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                self._theme_icon,
                                ft.Text(
                                    "深色模式",
                                    size=15,
                                    weight=ft.FontWeight.W_500,
                                    color=sc.text,
                                    expand=True,
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            expand=True,
                        ),
                        self._dark_switch,
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )

    def _switch_center_x(self) -> float:
        """Switch center X: page pad 20 + row pad 16 + ~52dp switch."""
        w = float(self._host.width or 420)
        page_pad = 20.0
        row_pad = 16.0
        switch_half = 26.0
        return w - page_pad - row_pad - switch_half

    def _toggle_theme(self, e: ft.ControlEvent | None = None) -> None:
        if getattr(self._host, "_theme_toggle_busy", False):
            # Switch may have flipped visually; snap back while animation runs.
            self._dark_switch.value = ThemeController.get_is_dark()
            try:
                self._dark_switch.update()
            except Exception:
                pass
            return

        gp = getattr(e, "global_position", None) if e is not None else None
        if gp is not None and getattr(gp, "x", None) is not None and getattr(gp, "y", None) is not None:
            self._last_theme_origin = (float(gp.x), float(gp.y))

        if self._last_theme_origin is not None:
            origin = self._last_theme_origin
        else:
            h = float(self._host.height or 860)
            origin = (self._switch_center_x(), h * 0.42)

        def rebuild() -> None:
            if self.on_theme_rebuild:
                self.on_theme_rebuild()
            else:
                self.refresh()

        schedule_theme_toggle(self._host, origin=origin, on_rebuild=rebuild)

    def _menu_group(self, items: list) -> ft.Control:
        rows: list[ft.Control] = []
        for i, item in enumerate(items):
            title = item[0]
            on_tap = item[1] if len(item) > 1 else None
            subtitle = item[2] if len(item) > 2 else None
            rows.append(self._menu_item(title, on_tap=on_tap, subtitle=subtitle))
            if i != len(items) - 1:
                rows.append(
                    ft.Divider(
                        height=1,
                        color=ShellColors.divider,
                        leading_indent=16,
                        trailing_indent=16,
                    )
                )
        return matte_card(ft.Column(rows, spacing=0, tight=True), padding=0)

    def _menu_group_custom(self, rows: list[ft.Control]) -> ft.Control:
        out: list[ft.Control] = []
        for i, row in enumerate(rows):
            out.append(row)
            if i != len(rows) - 1:
                out.append(
                    ft.Divider(
                        height=1,
                        color=ShellColors.divider,
                        leading_indent=16,
                        trailing_indent=16,
                    )
                )
        return matte_card(ft.Column(out, spacing=0, tight=True), padding=0)

    def _menu_item(self, title: str, *, on_tap=None, subtitle: str | None = None) -> ft.Control:
        sc = ShellColors
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
            on_click=lambda e: on_tap() if on_tap else None,
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(title, size=15, weight=ft.FontWeight.W_500, color=sc.text),
                            *(
                                [ft.Text(subtitle, size=12, color=sc.text_secondary)]
                                if subtitle
                                else []
                            ),
                        ],
                        spacing=2,
                        expand=True,
                        tight=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=sc.text_secondary),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _tap_records(self) -> None:
        if self.on_open_records:
            self.on_open_records()

    def _tap_plan(self) -> None:
        if self.on_open_plan:
            self.on_open_plan()

    def _show_accessibility(self) -> None:
        sc = ShellColors
        dlg = ft.AlertDialog(
            bgcolor=sc.surface,
            title=ft.Text("无障碍训练", color=sc.text),
            content=ft.Column(
                [
                    ft.Text(
                        "语音引导选课、口令控制训练与 TTS 播报，适合不便看屏的场景。",
                        size=12,
                        color=sc.text_secondary,
                    ),
                    ft.Container(height=6),
                    self._switch_row(
                        icon=ft.Icons.RECORD_VOICE_OVER,
                        title="语音辅助模式",
                        subtitle="开启后可用语音选择部位、确认推荐并控制训练",
                        switch=self._voice_switch,
                    ),
                    self._switch_row(
                        icon=ft.Icons.CAMPAIGN,
                        title="播报纠错建议",
                        subtitle="训练中语音播报姿势纠正提示（5 秒内同类不重复）",
                        switch=self._voice_correction_switch,
                    ),
                    self._switch_row(
                        icon=ft.Icons.AUTO_AWESOME,
                        title="AI 语音助手",
                        subtitle="说“小健小健”唤醒自由对话；训练中仍使用固定口令",
                        switch=self._ai_assistant_switch,
                    ),
                    ft.Container(
                        padding=ft.Padding.only(left=38, right=4, top=4, bottom=4),
                        content=ft.Column(
                            [
                                self._ai_api_key_field,
                                ft.Row(
                                    [
                                        self._ai_api_key_status,
                                        ft.Row(
                                            [
                                                ft.TextButton(
                                                    "清除",
                                                    on_click=self._clear_ai_api_key,
                                                ),
                                                ft.FilledButton(
                                                    "保存 Key",
                                                    on_click=self._save_ai_api_key,
                                                ),
                                            ],
                                            spacing=2,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=2,
                            tight=True,
                        ),
                    ),
                ],
                spacing=4,
                tight=True,
                width=340,
            ),
            actions=[
                ft.TextButton(
                    "完成",
                    style=ft.ButtonStyle(color=sc.accent),
                    on_click=lambda e: _close_dlg(),
                )
            ],
        )

        def _close_dlg() -> None:
            dlg.open = False
            dlg.update()

        self._host.show_dialog(dlg)

    def _show_about(self) -> None:
        sc = ShellColors
        dlg = ft.AlertDialog(
            bgcolor=sc.surface,
            title=ft.Text(APP_NAME, color=sc.text),
            content=ft.Text(
                f"{APP_TAGLINE}\n\n当前阶段：可运行 UI + Mock 数据 + 姿态识别管道。",
                color=sc.text_secondary,
            ),
            actions=[
                ft.TextButton(
                    "关闭",
                    style=ft.ButtonStyle(color=sc.accent),
                    on_click=lambda e: _close_dlg(),
                )
            ],
        )

        def _close_dlg() -> None:
            dlg.open = False
            dlg.update()

        self._host.show_dialog(dlg)

    def _logout(self, _: ft.ControlEvent) -> None:
        AppSession.clear()
        if self.on_logout:
            self.on_logout()
        else:
            self._host.snack_bar = ft.SnackBar(ft.Text("已退出登录"))
            self._host.snack_bar.open = True
            self._host.update()
