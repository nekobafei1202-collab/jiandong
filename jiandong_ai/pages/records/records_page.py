from __future__ import annotations

import math
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import flet as ft

from jiandong_ai.app.theme import ShellColors
from jiandong_ai.services.mock_service import MockService
from jiandong_ai.widgets.matte_card import matte_card
from jiandong_ai.widgets.muscle_map import activation_for_actions, render_muscle_svg
from jiandong_ai.widgets.section_header import section_header
from jiandong_ai.widgets.training_hud import (
    build_finished_summary,
    build_session_summary_text,
)


class RecordsView(ft.Container):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(expand=True, bgcolor=ShellColors.canvas, padding=0)
        self._host = page
        self._svc = MockService.instance()
        self._list = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self.content = self._list

    def on_show(self) -> None:
        # Tab 切换回来时总是回到记录列表，而不是停留在某条的详情页
        self.content = self._list
        self.refresh()

    def _day_label(self, iso: str) -> str:
        try:
            d = datetime.fromisoformat(iso)
        except ValueError:
            return iso
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return f"{d.month}月{d.day}日 {weekdays[d.weekday()]}"

    def refresh(self) -> None:
        sc = ShellColors
        self.bgcolor = sc.canvas
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
                                bgcolor=sc.accent if w.minutes else sc.border,
                                border_radius=6,
                            ),
                            ft.Text(w.label, size=11, color=sc.text_secondary),
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
                            ft.Icon(ft.Icons.HISTORY, size=40, color=sc.text_tertiary),
                            ft.Text("还没有训练记录", color=sc.text_secondary),
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
                        bgcolor=sc.surface,
                        border=ft.Border.all(1, sc.border),
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
                                            color=sc.text,
                                            size=15,
                                        ),
                                        ft.Text(
                                            f"{self._day_label(r.date)} · {r.duration} 分钟",
                                            size=12,
                                            color=sc.text_secondary,
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
                                    color=sc.accent,
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
                        ft.Text("记录", size=22, weight=ft.FontWeight.W_700, color=sc.text),
                        ft.Container(height=24),
                        ft.Text("今日", size=18, weight=ft.FontWeight.W_700, color=sc.text),
                        ft.Container(height=16),
                        ft.Row(
                            [
                                self._today_metric("时长", str(stats["durationMinutes"]), "分钟"),
                                ft.Container(width=1, height=48, bgcolor=sc.divider),
                                self._today_metric(
                                    "消耗",
                                    str(stats["todayCalories"]),
                                    "kcal",
                                    value_color=sc.calorie,
                                ),
                                ft.Container(width=1, height=48, bgcolor=sc.divider),
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
                            color=sc.text_secondary,
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
        sc = ShellColors
        return ft.Container(
            expand=True,
            content=ft.Column(
                [
                    ft.Text(label, size=12, color=sc.text_secondary),
                    ft.Row(
                        [
                            ft.Text(
                                value,
                                size=24,
                                weight=ft.FontWeight.W_700,
                                color=value_color or sc.text,
                            ),
                            ft.Text(unit, size=12, color=sc.text_secondary),
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
        """Open the full light summary page for a historical record."""
        actions: list[dict] = []
        for a in record.actions:
            reps = int(a.reps or 0)
            est_sets = max(1, min(4, math.ceil(reps / 10))) if reps > 0 else 1
            actions.append(
                {
                    "name": a.action_name,
                    "reps": reps,
                    "sets": est_sets,
                    "avg_score": a.avg_score,
                }
            )
        try:
            finished_at = datetime.fromisoformat(record.date)
        except ValueError:
            finished_at = datetime.now()
        duration_seconds = int(record.duration or 0) * 60
        started_at = finished_at - timedelta(seconds=duration_seconds)

        history = self._svc.get_training_history()
        prev = None
        for i, r in enumerate(history):
            if r.id == record.id:
                prev = history[i + 1] if i + 1 < len(history) else None
                break

        front_src, back_src = None, None
        try:
            activation = activation_for_actions([a["name"] for a in actions])
            tmp = Path(tempfile.gettempdir())
            front = tmp / "jiandong_muscle_front.svg"
            back = tmp / "jiandong_muscle_back.svg"
            front.write_text(render_muscle_svg(activation, view="front"), encoding="utf-8")
            back.write_text(render_muscle_svg(activation, view="back"), encoding="utf-8")
            front_src, back_src = str(front), str(back)
        except Exception:
            pass

        def back_to_list() -> None:
            self.content = self._list
            self.refresh()

        self.content = ft.Container(
            expand=True,
            bgcolor="#F5F7FA",
            padding=ft.Padding.all(16),
            content=build_finished_summary(
                session_name=record.exercise_name,
                started_at=started_at,
                finished_at=finished_at,
                sets=max(1, sum(a["sets"] for a in actions) or 1),
                duration_seconds=duration_seconds,
                calories=record.calories or 0,
                posture_pct=record.score or 0,
                planned_actions=len(actions),
                actions=actions,
                prev_calories=prev.calories if prev else None,
                prev_duration_seconds=(prev.duration * 60) if prev else None,
                summary_text=build_session_summary_text(actions),
                muscle_front_src=front_src,
                muscle_back_src=back_src,
                on_back=back_to_list,
                on_delete=lambda: self._confirm_delete(record, back_to_list),
                on_share=lambda: self._toast("分享功能即将开放"),
                on_download=lambda: self._toast("下载功能即将开放"),
            ),
        )
        try:
            self.update()
        except Exception:
            pass

    def _confirm_delete(self, record, on_deleted) -> None:
        dlg = ft.AlertDialog(
            title=ft.Text("删除这条训练记录？"),
            content=ft.Text("删除后无法恢复。"),
            actions=[
                ft.TextButton("取消", on_click=lambda e: close()),
                ft.TextButton(
                    "删除",
                    on_click=lambda e: confirm(),
                ),
            ],
        )

        def close() -> None:
            dlg.open = False
            try:
                dlg.update()
            except Exception:
                pass

        def confirm() -> None:
            self._svc.delete_training_record(record.id)
            close()
            on_deleted()

        self._host.show_dialog(dlg)

    def _toast(self, msg: str) -> None:
        self._host.show_dialog(ft.SnackBar(ft.Text(msg)))
