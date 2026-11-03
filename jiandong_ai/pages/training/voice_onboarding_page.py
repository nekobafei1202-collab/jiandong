"""无障碍模式首次引导页：功能介绍 → 麦克风权限说明 → 语音待命页。

仅 Android 无障碍模式下由 MainShell 在进入训练前展示；
「暂用触屏模式」随时兜底退出，勾选「以后自动开启」写入 MockService 设置。
"""

from __future__ import annotations

import flet as ft

from jiandong_ai.app.theme import ShellColors
from jiandong_ai.services.mock_service import MockService

_COMMANDS = (
    "腿部 / 核心 / 上肢 / 背部 / 全身 —— 选择训练部位",
    "确认 / 换一个 —— 确认或调整推荐",
    "开始训练 —— 进入训练",
    "暂停训练 / 继续训练 / 结束训练 —— 训练中控制",
    "帮助 —— 随时收听口令说明",
)


class VoiceOnboardingPage(ft.Container):
    """三步引导；on_finish(use_voice: bool) 在用户做出选择后调用。"""

    def __init__(self, page: ft.Page, *, on_finish) -> None:
        super().__init__(expand=True, bgcolor=ShellColors.canvas)
        self._host = page
        self.on_finish = on_finish
        self._svc = MockService.instance()
        self._step = 0
        self._auto_open = ft.Checkbox(
            label="以后自动开启语音模式",
            value=True,
            fill_color=ShellColors.accent,
            label_style=ft.TextStyle(size=13, color=ShellColors.text_secondary),
        )
        self.content = self._build_step()

    def _go(self, step: int) -> None:
        self._step = step
        self.content = self._build_step()
        try:
            self.update()
        except Exception:
            pass

    def _finish(self, *, use_voice: bool) -> None:
        if use_voice:
            self._svc.set_voice_accessibility(bool(self._auto_open.value))
        if self.on_finish:
            self.on_finish(use_voice)

    def _build_step(self) -> ft.Control:
        if self._step == 0:
            return self._build_intro()
        if self._step == 1:
            return self._build_mic()
        return self._build_standby()

    def _primary_button(self, label: str, on_click) -> ft.Control:
        return ft.FilledButton(
            label,
            bgcolor=ShellColors.accent,
            color=ShellColors.on_cta,
            height=52,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=999)),
            on_click=on_click,
            width=float("inf"),
        )

    def _ghost_button(self, label: str, on_click) -> ft.Control:
        return ft.TextButton(
            label,
            style=ft.ButtonStyle(color=ShellColors.text_secondary),
            on_click=on_click,
        )

    def _build_intro(self) -> ft.Control:
        sc = ShellColors
        return ft.Column(
            [
                ft.Container(height=64),
                ft.Icon(ft.Icons.RECORD_VOICE_OVER, size=72, color=sc.accent),
                ft.Container(height=16),
                ft.Text(
                    "语音控制训练",
                    size=24,
                    weight=ft.FontWeight.W_700,
                    color=sc.text,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=8),
                ft.Text(
                    "不用看屏幕，说出想练的部位，\n"
                    "语音为你推荐动作组合并播报计数与纠正。\n"
                    "所有识别都在本机离线完成。",
                    size=14,
                    color=sc.text_secondary,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(expand=True),
                self._primary_button("开启语音控制", lambda e: self._go(1)),
                self._ghost_button(
                    "暂用触屏模式", lambda e: self._finish(use_voice=False)
                ),
                ft.Row([self._auto_open], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=24),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        )

    def _build_mic(self) -> ft.Control:
        sc = ShellColors
        return ft.Column(
            [
                ft.Container(height=64),
                ft.Icon(ft.Icons.MIC, size=72, color=sc.accent),
                ft.Container(height=16),
                ft.Text(
                    "需要麦克风权限",
                    size=22,
                    weight=ft.FontWeight.W_700,
                    color=sc.text,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=8),
                ft.Text(
                    "语音识别需要用到麦克风。\n"
                    "系统弹出权限请求时请选「允许」；\n"
                    "拒绝后会回到触屏模式，不影响正常训练。",
                    size=14,
                    color=sc.text_secondary,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(expand=True),
                # 实际 RECORD_AUDIO 运行时请求由原生 VoiceCommandBridge 发起。
                self._primary_button(
                    "授权并继续", lambda e: self._go(2)
                ),
                self._ghost_button(
                    "暂用触屏模式", lambda e: self._finish(use_voice=False)
                ),
                ft.Container(height=24),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        )

    def _build_standby(self) -> ft.Control:
        sc = ShellColors
        command_rows = [
            ft.Row(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=16, color=sc.accent),
                    ft.Text(text, size=13, color=sc.text, expand=True),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            for text in _COMMANDS
        ]
        return ft.Column(
            [
                ft.Container(height=48),
                ft.Icon(ft.Icons.HEARING, size=64, color=sc.accent),
                ft.Container(height=12),
                ft.Text(
                    "正在聆听",
                    size=22,
                    weight=ft.FontWeight.W_700,
                    color=sc.text,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "想练哪个部位？直接说出来即可。",
                    size=13,
                    color=sc.text_secondary,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=20),
                ft.Container(
                    bgcolor=sc.surface,
                    border_radius=16,
                    padding=ft.Padding.all(16),
                    content=ft.Column(
                        [
                            ft.Text(
                                "可用口令",
                                size=14,
                                weight=ft.FontWeight.W_600,
                                color=sc.text,
                            ),
                            *command_rows,
                        ],
                        spacing=10,
                        tight=True,
                    ),
                ),
                ft.Container(expand=True),
                self._primary_button(
                    "开始体验", lambda e: self._finish(use_voice=True)
                ),
                self._ghost_button(
                    "暂用触屏模式", lambda e: self._finish(use_voice=False)
                ),
                ft.Container(height=24),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            expand=True,
        )


def build_voice_onboarding(page: ft.Page, *, on_finish) -> ft.Control:
    return VoiceOnboardingPage(page, on_finish=on_finish)
