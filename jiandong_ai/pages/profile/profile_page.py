from __future__ import annotations

import flet as ft

from jiandong_ai.app.constants import APP_NAME, APP_TAGLINE
from jiandong_ai.app.theme import (
    SHELL_ACCENT,
    SHELL_BORDER,
    SHELL_CANVAS,
    SHELL_DIVIDER,
    SHELL_SURFACE,
    SHELL_SURFACE_MUTED,
    SHELL_TEXT,
    SHELL_TEXT_SECONDARY,
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
    ) -> None:
        super().__init__(expand=True, bgcolor=SHELL_CANVAS, padding=0)
        self._host = page
        self.on_logout = on_logout
        self.on_open_records = on_open_records
        self.on_open_plan = on_open_plan
        self._svc = MockService.instance()
        self._name = ft.Text("", size=18, weight=ft.FontWeight.W_600, color=SHELL_TEXT)
        self._email = ft.Text("", size=13, color=SHELL_TEXT_SECONDARY)
        self._streak = ft.Text("", size=13, weight=ft.FontWeight.W_500, color=SHELL_ACCENT)
        self._avatar_letter = ft.Text("健", size=22, weight=ft.FontWeight.W_700, color=SHELL_TEXT)

        self.content = ft.Column(
            [
                ft.Container(
                    padding=ft.Padding.only(left=20, top=20, right=20, bottom=0),
                    content=ft.Column(
                        [
                            ft.Text("我的", size=22, weight=ft.FontWeight.W_700, color=SHELL_TEXT),
                            ft.Container(height=20),
                            ft.Row(
                                [
                                    ft.CircleAvatar(
                                        radius=32,
                                        bgcolor=SHELL_SURFACE_MUTED,
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
                            self._menu_group(
                                [
                                    ("无障碍训练", self._show_accessibility),
                                    ("设置", None, "即将上线"),
                                    ("关于", self._show_about),
                                ]
                            ),
                            ft.Container(height=28),
                            ft.OutlinedButton(
                                "退出登录",
                                height=48,
                                style=ft.ButtonStyle(
                                    color=SHELL_TEXT,
                                    side=ft.BorderSide(1, SHELL_BORDER),
                                    shape=ft.RoundedRectangleBorder(radius=999),
                                ),
                                on_click=self._logout,
                            ),
                            ft.Container(height=28),
                        ],
                        spacing=0,
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    expand=True,
                )
            ],
            expand=True,
            spacing=0,
        )

    def on_show(self) -> None:
        u = self._svc.get_current_user()
        self._name.value = u.name
        self._email.value = u.email
        self._streak.value = f"连续打卡 {self._svc.get_streak_days()} 天"
        self._avatar_letter.value = u.name[0] if u.name else "健"
        try:
            self.update()
        except Exception:
            pass

    def _menu_group(self, items: list) -> ft.Control:
        rows: list[ft.Control] = []
        for i, item in enumerate(items):
            title = item[0]
            on_tap = item[1] if len(item) > 1 else None
            subtitle = item[2] if len(item) > 2 else None
            rows.append(self._menu_item(title, on_tap=on_tap, subtitle=subtitle))
            if i != len(items) - 1:
                rows.append(
                    ft.Divider(height=1, color=SHELL_DIVIDER, leading_indent=16, trailing_indent=16)
                )
        return matte_card(ft.Column(rows, spacing=0, tight=True), padding=0)

    def _menu_item(self, title: str, *, on_tap=None, subtitle: str | None = None) -> ft.Control:
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
            on_click=lambda e: on_tap() if on_tap else None,
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(title, size=15, weight=ft.FontWeight.W_500, color=SHELL_TEXT),
                            *(
                                [ft.Text(subtitle, size=12, color=SHELL_TEXT_SECONDARY)]
                                if subtitle
                                else []
                            ),
                        ],
                        spacing=2,
                        expand=True,
                        tight=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=SHELL_TEXT_SECONDARY),
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
        dlg = ft.AlertDialog(
            bgcolor=SHELL_SURFACE,
            title=ft.Text("无障碍训练"),
            content=ft.Text(
                "后续支持视觉/听觉辅助模式、差异化动作评价与语音反馈。当前为入口占位。",
                color=SHELL_TEXT_SECONDARY,
            ),
            actions=[ft.TextButton("知道了", on_click=lambda e: self._host.close(dlg))],
        )
        self._host.open(dlg)

    def _show_about(self) -> None:
        dlg = ft.AlertDialog(
            bgcolor=SHELL_SURFACE,
            title=ft.Text(APP_NAME),
            content=ft.Text(
                f"{APP_TAGLINE}\n\n当前阶段：可运行 UI + Mock 数据 + 姿态识别管道。",
                color=SHELL_TEXT_SECONDARY,
            ),
            actions=[
                ft.TextButton(
                    "关闭",
                    style=ft.ButtonStyle(color=SHELL_ACCENT),
                    on_click=lambda e: self._host.close(dlg),
                )
            ],
        )
        self._host.open(dlg)

    def _logout(self, _: ft.ControlEvent) -> None:
        AppSession.clear()
        if self.on_logout:
            self.on_logout()
        else:
            self._host.snack_bar = ft.SnackBar(ft.Text("已退出登录"))
            self._host.snack_bar.open = True
            self._host.update()
