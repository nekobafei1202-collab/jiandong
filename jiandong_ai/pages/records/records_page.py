from __future__ import annotations

from datetime import datetime

import flet as ft

from jiandong_ai.app.theme import (
    SHELL_ACCENT,
    SHELL_BORDER,
    SHELL_CALORIE,
    SHELL_CANVAS,
    SHELL_DIVIDER,
    SHELL_SURFACE,
    SHELL_TEXT,
    SHELL_TEXT_SECONDARY,
    SHELL_TEXT_TERTIARY,
)
from jiandong_ai.services.mock_service import MockService
from jiandong_ai.widgets.matte_card import matte_card
from jiandong_ai.widgets.section_header import section_header


class RecordsView(ft.Container):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, bgcolor=SHELL_CANVAS, padding=0)
        self._host = page
        self._svc = MockService.instance()
        self._list = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self.content = self._list

    def on_show(self) -> None:
        self.refresh()

    def _day_label(self, iso: str) -> str:
        try:
            d = datetime.fromisoformat(iso)
        except ValueError:
            return iso
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return f"{d.month}月{d.day}日 {weekdays[d.weekday()]}"

    def _full_date(self, iso: str) -> str:
        try:
            d = datetime.fromisoformat(iso)
        except ValueError:
            return iso
        return f"{d.year}年{d.month}月{d.day}日"

    def refresh(self) -> None:
        stats = self._svc.get_today_stats()
        weekly = self._svc.get_weekly_stats()
        history = self._svc.get_training_history()
        week_total = sum(w.minutes for w in weekly)
        max_m = max((w.minutes for w in weekly), default=1) or 1

        bars: list[ft.Control] = []
        for w in weekly:
            h = max(8, int(100 * w.minutes / max_m)) if w.minutes else 8
            bars.append(
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        [
                            ft.Container(expand=True),
                            ft.Container(
                                width=22,
                                height=h,
                                bgcolor=SHELL_ACCENT if w.minutes else SHELL_BORDER,
                                border_radius=6,
                            ),
                            ft.Text(w.label, size=11, color=SHELL_TEXT_SECONDARY),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                )
            )

        history_controls: list[ft.Control] = []
        if not history:
            history_controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(vertical=24),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.HISTORY, size=40, color=SHELL_TEXT_TERTIARY),
                            ft.Text("还没有训练记录", color=SHELL_TEXT_SECONDARY),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        tight=True,
                    ),
                )
            )
        else:
            for r in history:
                history_controls.append(
                    ft.Container(
                        margin=ft.Margin.only(bottom=10),
                        bgcolor=SHELL_SURFACE,
                        border=ft.Border.all(1, SHELL_BORDER),
                        border_radius=12,
                        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                        on_click=lambda e, rec=r: self._show_detail(rec),
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            r.exercise_name,
                                            weight=ft.FontWeight.W_600,
                                            color=SHELL_TEXT,
                                            size=15,
                                        ),
                                        ft.Text(
                                            f"{self._day_label(r.date)} · {r.duration} 分钟",
                                            size=12,
                                            color=SHELL_TEXT_SECONDARY,
                                        ),
                                    ],
                                    spacing=4,
                                    expand=True,
                                    tight=True,
                                ),
                                ft.Text(
                                    str(r.score),
                                    size=22,
                                    weight=ft.FontWeight.BOLD,
                                    color=SHELL_ACCENT,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )

        self._list.controls = [
            ft.Container(
                padding=ft.Padding.only(left=20, top=20, right=20, bottom=0),
                content=ft.Column(
                    [
                        ft.Text("记录", size=22, weight=ft.FontWeight.W_700, color=SHELL_TEXT),
                        ft.Container(height=24),
                        ft.Text("今日", size=18, weight=ft.FontWeight.W_700, color=SHELL_TEXT),
                        ft.Container(height=16),
                        ft.Row(
                            [
                                self._today_metric("时长", str(stats["durationMinutes"]), "分钟"),
                                ft.Container(width=1, height=48, bgcolor=SHELL_DIVIDER),
                                self._today_metric(
                                    "消耗",
                                    str(stats["todayCalories"]),
                                    "kcal",
                                    value_color=SHELL_CALORIE,
                                ),
                                ft.Container(width=1, height=48, bgcolor=SHELL_DIVIDER),
                                self._today_metric("组数", str(stats["todaySets"]), "组"),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Container(height=32),
                        section_header("本周", action_label=f"合计 {week_total}m"),
                        ft.Container(height=14),
                        matte_card(
                            ft.Container(height=148, content=ft.Row(bars, expand=True)),
                            padding=ft.Padding.only(left=12, top=16, right=12, bottom=12),
                        ),
                        ft.Container(height=12),
                        ft.Text(
                            f"累计 {stats['totalHours']} 小时 · 连续 {self._svc.get_streak_days()} 天",
                            size=12,
                            color=SHELL_TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=32),
                        section_header("历史"),
                        ft.Container(height=12),
                        *history_controls,
                        ft.Container(height=28),
                    ],
                    spacing=0,
                    tight=True,
                ),
            )
        ]
        if self._host:
            try:
                self.update()
            except Exception:
                pass

    def _today_metric(
        self,
        label: str,
        value: str,
        unit: str,
        *,
        value_color: str | None = None,
    ) -> ft.Control:
        return ft.Container(
            expand=True,
            content=ft.Column(
                [
                    ft.Text(label, size=12, color=SHELL_TEXT_SECONDARY),
                    ft.Row(
                        [
                            ft.Text(
                                value,
                                size=24,
                                weight=ft.FontWeight.W_700,
                                color=value_color or SHELL_TEXT,
                            ),
                            ft.Text(unit, size=12, color=SHELL_TEXT_SECONDARY),
                        ],
                        spacing=4,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
                tight=True,
            ),
        )

    def _show_detail(self, record) -> None:
        stats_row = [
            self._sheet_stat("时长", f"{record.duration} 分钟"),
        ]
        if record.calories is not None:
            stats_row.append(self._sheet_stat("消耗", f"{record.calories} 千卡"))
        if record.total_reps is not None:
            stats_row.append(self._sheet_stat("总次数", str(record.total_reps)))
        stats_row.append(self._sheet_stat("评分", str(record.score)))

        action_rows: list[ft.Control] = []
        for a in record.actions:
            detail = f"{a.reps} 次"
            if a.avg_score:
                detail += f" · {a.avg_score} 分"
            action_rows.append(
                ft.Container(
                    padding=ft.Padding.symmetric(vertical=6),
                    content=ft.Row(
                        [
                            ft.Text(a.action_name, expand=True, color=SHELL_TEXT),
                            ft.Text(detail, size=13, color=SHELL_TEXT_SECONDARY),
                        ]
                    ),
                )
            )

        score = record.score
        if score >= 90:
            review = "总体评价：表现优秀，动作质量很高，保持这个节奏。"
        elif score >= 75:
            review = "总体评价：整体不错，注意个别动作的稳定性和幅度。"
        elif score >= 60:
            review = "总体评价：完成了训练，下次放慢一点、优先保证姿势。"
        else:
            review = "总体评价：先别追求次数，把每个动作做标准更重要。"

        dlg = ft.AlertDialog(
            bgcolor=SHELL_SURFACE,
            title=ft.Text(record.exercise_name),
            content=ft.Column(
                [
                    ft.Text(self._full_date(record.date), size=12, color=SHELL_TEXT_SECONDARY),
                    ft.Container(height=12),
                    ft.Row(stats_row, wrap=True, spacing=10),
                    *(
                        [
                            ft.Container(height=12),
                            ft.Text("动作明细", weight=ft.FontWeight.W_600, color=SHELL_TEXT),
                            *action_rows,
                            ft.Text(review, size=13, color=SHELL_ACCENT),
                        ]
                        if record.actions
                        else []
                    ),
                ],
                tight=True,
                height=280,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[ft.TextButton("关闭", on_click=lambda e: self._host.close(dlg))],
        )
        self._host.open(dlg)

    def _sheet_stat(self, label: str, value: str) -> ft.Control:
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            bgcolor=SHELL_CANVAS,
            border_radius=10,
            content=ft.Column(
                [
                    ft.Text(label, size=11, color=SHELL_TEXT_SECONDARY),
                    ft.Text(value, size=13, weight=ft.FontWeight.W_600, color=SHELL_TEXT),
                ],
                spacing=2,
                tight=True,
            ),
        )
