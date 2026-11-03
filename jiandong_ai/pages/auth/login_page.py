from __future__ import annotations

import flet as ft

from jiandong_ai.app.constants import MOCK_EMAIL, MOCK_PASSWORD
from jiandong_ai.services.mock_service import MockService
from jiandong_ai.widgets.course_cover import asset_src

_GREEN = "#3ECF9E"
_GREEN_DISABLED = "#2E6B58"
_TEXT = "#FFFFFF"
_TEXT_DISABLED = "#BFFFFFFF"
_TEXT2 = "#B3FFFFFF"
_TEXT3 = "#80FFFFFF"
_GLASS_BG = "#26FFFFFF"
_GLASS_BORDER = "#40FFFFFF"
_DANGER = "#FF8589"


class _LoginRoot(ft.Container):
    def __init__(self, *, on_mount, on_unmount, **kwargs) -> None:
        super().__init__(**kwargs)
        self._on_mount = on_mount
        self._on_unmount = on_unmount

    def did_mount(self) -> None:
        super().did_mount()
        self._on_mount()

    def will_unmount(self) -> None:
        self._on_unmount()
        super().will_unmount()


def _logo_bars() -> ft.Control:
    heights = [16, 28, 44, 28, 16]
    bars = [
        ft.Container(width=8, height=h, bgcolor=_GREEN, border_radius=4)
        for h in heights
    ]
    return ft.Row(bars, spacing=5, vertical_alignment=ft.CrossAxisAlignment.CENTER)


def _glass_field(*, hint: str, icon: str, password: bool = False, value: str = "") -> ft.TextField:
    return ft.TextField(
        value=value,
        hint_text=hint,
        hint_style=ft.TextStyle(color=_TEXT2, size=14),
        text_style=ft.TextStyle(color=_TEXT, size=14),
        prefix=ft.Container(
            padding=ft.Padding.only(left=16, right=8),
            content=ft.Icon(icon, size=20, color=_TEXT2),
        ),
        password=password,
        can_reveal_password=password,
        bgcolor=_GLASS_BG,
        border=ft.InputBorder.OUTLINE,
        border_radius=999,
        border_color=_GLASS_BORDER,
        focused_border_color=_GREEN,
        cursor_color=_GREEN,
        height=56,
        content_padding=ft.Padding.symmetric(horizontal=4, vertical=14),
        expand=True,
    )


def _social_circle(src: str, on_tap) -> ft.Control:
    return ft.Container(
        width=48,
        height=48,
        border_radius=999,
        border=ft.Border.all(1, _GLASS_BORDER),
        alignment=ft.Alignment.CENTER,
        content=ft.Image(src=asset_src(src), width=22, height=22, fit=ft.BoxFit.CONTAIN),
        on_click=on_tap,
        ink=True,
    )


def build_login(page: ft.Page, *, on_success, on_register) -> ft.Control:
    page.fonts = {
        **(page.fonts or {}),
        "MaShanZheng": asset_src("assets/fonts/MaShanZheng-Regular.ttf"),
    }

    def toast(msg: str) -> None:
        page.show_dialog(ft.SnackBar(ft.Text(msg)))

    # 演示阶段预填测试账号，省去每次手动输入
    account = _glass_field(hint="请输入手机号", icon=ft.Icons.PHONE_ANDROID_OUTLINED, value=MOCK_EMAIL)
    password = _glass_field(hint="请输入密码", icon=ft.Icons.LOCK_OUTLINE, password=True, value=MOCK_PASSWORD)
    error = ft.Text("", color=_DANGER, size=12)

    agreed = ft.Ref[ft.Checkbox]()
    login_btn = ft.Ref[ft.FilledButton]()
    voice_guide = None

    def _stop_voice_guide() -> None:
        nonlocal voice_guide
        if voice_guide is not None:
            voice_guide.stop()
            voice_guide = None

    def _start_voice_guide() -> None:
        nonlocal voice_guide
        if voice_guide is not None:
            return
        if not MockService.instance().get_voice_accessibility():
            return
        from jiandong_ai.ai.session.android_bridge_session import (
            is_android_runtime,
            write_voice_flag,
        )

        if not is_android_runtime():
            return
        from jiandong_ai.ai.session.voice_session import LoginVoiceGuide

        write_voice_flag(True)

        def on_voice_login() -> None:
            def apply() -> None:
                # 语音用户无需再触摸协议勾选框，之后复用完全相同的登录逻辑。
                if agreed.current is not None:
                    agreed.current.value = True
                submit(None)

            try:
                page.run_thread(apply)
            except Exception:
                apply()

        guide = LoginVoiceGuide(on_login=on_voice_login, poll_interval=0.1)
        if guide.start():
            voice_guide = guide

    def _sync_login_state() -> None:
        ok = bool(agreed.current and agreed.current.value)
        if login_btn.current is not None:
            login_btn.current.bgcolor = _GREEN if ok else _GREEN_DISABLED
            login_btn.current.color = _TEXT if ok else _TEXT_DISABLED
        page.update()

    def submit(_: ft.ControlEvent | None = None) -> None:
        if not (agreed.current and agreed.current.value):
            toast("请先阅读并同意《用户协议》和《隐私政策》")
            return
        error.value = ""
        user = MockService.instance().login(account.value or "", password.value or "")
        if user is None:
            error.value = f"账号或密码错误（演示账号 {MOCK_EMAIL} / {MOCK_PASSWORD}）"
            page.update()
            return
        _stop_voice_guide()
        on_success()

    agreement_text = ft.Text(
        size=12,
        spans=[
            ft.TextSpan("我已阅读并同意 ", style=ft.TextStyle(color=_TEXT)),
            ft.TextSpan("《用户协议》", style=ft.TextStyle(color=_GREEN)),
            ft.TextSpan(" 和 ", style=ft.TextStyle(color=_TEXT)),
            ft.TextSpan("《隐私政策》", style=ft.TextStyle(color=_GREEN)),
        ],
    )
    agree_block = ft.Column(
        [
            ft.Row(
                [
                    ft.Checkbox(
                        ref=agreed,
                        value=False,
                        fill_color=ft.Colors.with_opacity(0.2, "#FFFFFF"),
                        check_color=_GREEN,
                        border_side=ft.BorderSide(1.5, _TEXT2),
                        on_change=lambda e: _sync_login_state(),
                    ),
                    ft.Container(expand=True, content=agreement_text),
                ],
                spacing=2,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                [
                    ft.TextButton(
                        "忘记密码?",
                        style=ft.ButtonStyle(color=_TEXT2, padding=0),
                        on_click=lambda e: toast("忘记密码功能暂未开放"),
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
        ],
        spacing=0,
        tight=True,
    )

    content = ft.Column(
        [
            # 区域 A：品牌区
            ft.Container(height=16),
            ft.Row(
                [
                    _logo_bars(),
                    ft.Container(width=12),
                    ft.Text("健动AI", size=30, weight=ft.FontWeight.W_800, color=_TEXT),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=6),
            ft.Text("更好的自己，从每一次训练开始", size=14, color=_TEXT2),
            # 区域 B：宣传语区
            ft.Container(height=36),
            ft.Container(
                rotate=-0.03,
                content=ft.Column(
                    [
                        ft.Text(
                            "坚持",
                            size=40,
                            font_family="MaShanZheng",
                            color="#FFFDF4",
                        ),
                        ft.Container(
                            padding=ft.Padding.only(left=38),
                            content=ft.Text(
                                "让改变发生",
                                size=40,
                                font_family="MaShanZheng",
                                color="#FFFDF4",
                            ),
                        ),
                        ft.Container(
                            margin=ft.Margin.only(left=24, top=2),
                            content=ft.Image(
                                src=asset_src("assets/images/slogan_stroke.svg"),
                                width=190,
                                fit=ft.BoxFit.CONTAIN,
                            ),
                        ),
                    ],
                    spacing=0,
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                ),
            ),
            # 弹性间隔：高屏自然撑开，矮屏/键盘弹出时收缩
            ft.Container(expand=True),
            # 区域 C：登录表单区
            ft.Row([account]),
            ft.Container(height=14),
            ft.Row([password]),
            ft.Container(height=4),
            ft.Container(height=18, alignment=ft.Alignment.CENTER_LEFT, content=error),
            ft.Container(alignment=ft.Alignment.CENTER_LEFT, content=agree_block),
            ft.Container(height=16),
            ft.Row(
                [
                    ft.FilledButton(
                        "登录",
                        ref=login_btn,
                        bgcolor=_GREEN_DISABLED,
                        color=_TEXT_DISABLED,
                        height=56,
                        expand=True,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=999),
                            text_style=ft.TextStyle(size=17, weight=ft.FontWeight.W_700),
                        ),
                        on_click=submit,
                    ),
                ]
            ),
            # 区域 D：辅助登录区
            ft.Container(height=28),
            ft.Row(
                [
                    ft.Container(expand=True, height=1, bgcolor="#33FFFFFF"),
                    ft.Text("  其他登录方式  ", size=12, color=_TEXT3),
                    ft.Container(expand=True, height=1, bgcolor="#33FFFFFF"),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=18),
            ft.Row(
                [
                    _social_circle("assets/images/wechat.svg", lambda e: toast("微信登录暂未接入")),
                    ft.Container(width=28),
                    _social_circle("assets/images/qq.svg", lambda e: toast("QQ登录暂未接入")),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Container(height=18),
            ft.Row(
                [
                    ft.Text("还没有账号？", size=13, color=_TEXT2),
                    ft.TextButton(
                        "立即注册",
                        style=ft.ButtonStyle(color=_GREEN, padding=0),
                        on_click=lambda e: toast("注册功能暂未开放"),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=0,
            ),
            ft.Container(height=8),
        ],
        expand=True,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
    )

    return _LoginRoot(
        on_mount=_start_voice_guide,
        on_unmount=_stop_voice_guide,
        expand=True,
        image=ft.DecorationImage(
            src=asset_src("assets/images/login_bg.jpg"),
            fit=ft.BoxFit.COVER,
        ),
        content=ft.Stack(
            [
                ft.Container(
                    expand=True,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_CENTER,
                        end=ft.Alignment.BOTTOM_CENTER,
                        colors=["#59000000", "#73000000", "#D9000000"],
                    ),
                ),
                ft.SafeArea(
                    expand=True,
                    content=ft.Container(padding=ft.Padding.symmetric(horizontal=24), content=content),
                ),
            ],
            expand=True,
        ),
    )
