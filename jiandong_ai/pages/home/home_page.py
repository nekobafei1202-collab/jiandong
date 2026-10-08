from __future__ import annotations

from datetime import datetime

import flet as ft

from jiandong_ai.app.theme import SHELL_RADIUS_CARD, ShellColors
from jiandong_ai.pages.home.plan_editor_page import open_plan_editor
from jiandong_ai.services.mock_service import MockService
from jiandong_ai.widgets.course_cover import action_thumb, course_cover
from jiandong_ai.widgets.matte_card import matte_card
from jiandong_ai.widgets.motion import PROGRESS_MS, duration_ms
from jiandong_ai.widgets.section_header import section_header


class HomeView(ft.Container):
    def __init__(self, page: ft.Page, *, on_start_training, on_open_courses=None, on_open_course=None) -> None:
        super().__init__(expand=True, bgcolor=ShellColors.canvas, padding=0)
        self._host = page
        self.on_start_training = on_start_training
        self.on_open_courses = on_open_courses
        self.on_open_course = on_open_course
        self._svc = MockService.instance()
        self._scroll = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self.content = self._scroll
        self._svc.on_plan_changed(self.refresh)
        self.refresh()

    def on_show(self) -> None:
        self.refresh()

    def _open_course(self, course) -> None:
        if self.on_open_course:
            self.on_open_course(course)
        elif self.on_open_courses:
            self.on_open_courses()

    def _greeting(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "早上好"
        if hour < 18:
            return "下午好"
        return "晚上好"

    def _date_label(self) -> str:
        now = datetime.now()
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return f"{now.month}月{now.day}日 {weekdays[now.weekday()]}"

    def _edit_plan(self, _: ft.ControlEvent | None = None) -> None:
        open_plan_editor(
            self._host,
            on_saved=self.refresh,
            on_start_training=self.on_start_training,
        )

    def _start_plan(self) -> None:
        actions = self._svc.get_today_plan_actions()
        if not actions:
            self._edit_plan()
            return
        # Full today's plan queue (start index resolved inside go_training).
        def go() -> None:
            self.on_start_training(actions=actions, session_title="今日计划")

        try:
            self._host.run_thread(go)
        except Exception:
            go()

    def refresh(self) -> None:
        sc = ShellColors
        self.bgcolor = sc.canvas
        user = self._svc.get_current_user()
        plan = self._svc.get_today_plan()
        done = sum(1 for _, d in plan if d)
        goal = len(plan)
        progress = 0.0 if goal == 0 else done / goal
        percent = round(progress * 100)
        stats = self._svc.get_today_stats()
        week_count = sum(1 for w in self._svc.get_weekly_stats() if w.minutes > 0)
        recommended = self._svc.get_recommended_workouts()
        quick = self._svc.get_quick_exercises()[:3]
        continue_training = done < goal
        next_action = next((a for a, d in plan if not d), plan[0][0] if plan else "深蹲")
        hero = recommended[0] if recommended else None
        streak = self._svc.get_streak_days()
        prog_ms = duration_ms(self._host, PROGRESS_MS)

        children: list[ft.Control] = [
            ft.Container(
                padding=ft.Padding.only(left=20, top=16, right=20, bottom=8),
                opacity=1,
                animate_opacity=ft.Animation(350, ft.AnimationCurve.EASE_OUT_CUBIC)
                if prog_ms
                else None,
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(
                                    f"{self._greeting()}，{user.name}",
                                    size=22,
                                    weight=ft.FontWeight.W_700,
                                    color=sc.text,
                                ),
                                ft.Text(self._date_label(), size=14, color=sc.text_secondary),
                            ],
                            spacing=6,
                            expand=True,
                            tight=True,
                        ),
                        *(
                            [
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                    bgcolor=sc.accent_soft,
                                    border_radius=999,
                                    content=ft.Row(
                                        [
                                            ft.Icon(
                                                ft.Icons.LOCAL_FIRE_DEPARTMENT,
                                                size=16,
                                                color=sc.accent,
                                            ),
                                            ft.Text(
                                                f"连续 {streak} 天",
                                                size=12,
                                                weight=ft.FontWeight.W_600,
                                                color=sc.accent,
                                            ),
                                        ],
                                        spacing=4,
                                        tight=True,
                                    ),
                                )
                            ]
                            if streak > 0
                            else []
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ),
        ]

        if hero is not None:
            children.append(
                ft.Container(
                    padding=ft.Padding.only(left=20, top=12, right=20, bottom=8),
                    content=ft.Container(
                        border_radius=SHELL_RADIUS_CARD,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        height=180,
                        content=ft.Stack(
                            [
                                course_cover(
                                    exercise=hero,
                                    height=180,
                                    show_bottom_fade=True,
                                    apply_matte_overlay=False,
                                ),
                                ft.Container(
                                    expand=True,
                                    padding=ft.Padding.all(16),
                                    alignment=ft.Alignment(-1, 1),
                                    content=ft.Column(
                                        [
                                            ft.Text(
                                                hero.name,
                                                size=20,
                                                weight=ft.FontWeight.W_700,
                                                color="white",
                                            ),
                                            ft.Text(
                                                f"{hero.duration} 分钟 · {hero.difficulty}",
                                                size=13,
                                                color="#FFFFFFD9",
                                            ),
                                            ft.Container(height=8),
                                            ft.OutlinedButton(
                                                "查看课程",
                                                style=ft.ButtonStyle(
                                                    color="white",
                                                    side=ft.BorderSide(1, "#FFFFFFB3"),
                                                    shape=ft.RoundedRectangleBorder(radius=999),
                                                ),
                                                on_click=lambda e: self._open_course(hero),
                                            ),
                                        ],
                                        spacing=4,
                                        tight=True,
                                    ),
                                ),
                            ]
                        ),
                    ),
                )
            )

        plan_rows: list[ft.Control] = []
        for i, (action, is_done) in enumerate(plan):
            if i > 0:
                plan_rows.append(ft.Divider(height=1, color=sc.divider))
            target = self._svc.get_quick_target(action)
            row = ft.Container(
                padding=ft.Padding.symmetric(vertical=12),
                on_click=None if is_done else (lambda e, a=action: self.on_start_training(a)),
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE if is_done else ft.Icons.RADIO_BUTTON_UNCHECKED,
                            size=20,
                            color=sc.accent if is_done else sc.text_tertiary,
                        ),
                        action_thumb(action, size=40),
                        ft.Text(
                            action,
                            expand=True,
                            size=15,
                            weight=ft.FontWeight.W_400 if is_done else ft.FontWeight.W_600,
                            color=sc.text_secondary if is_done else sc.text,
                        ),
                        *(
                            [ft.Text(target, size=12, color=sc.text_secondary)]
                            if target
                            else []
                        ),
                        *(
                            []
                            if is_done
                            else [
                                ft.Icon(ft.Icons.CHEVRON_RIGHT, size=18, color=sc.accent),
                            ]
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            plan_rows.append(row)

        cta_label = (
            "编辑今日计划"
            if not plan
            else (f"继续训练 · {next_action}" if continue_training else "开始训练")
        )

        track = ft.Container(
            height=4,
            expand=True,
            bgcolor=sc.surface_muted,
            border_radius=999,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            content=ft.Row(
                [
                    ft.Container(
                        width=max(4.0, progress * 280),
                        height=4,
                        bgcolor=sc.accent,
                        border_radius=999,
                        animate=ft.Animation(prog_ms, ft.AnimationCurve.EASE_OUT_CUBIC)
                        if prog_ms
                        else None,
                    )
                ],
                spacing=0,
            ),
        )

        today_card = matte_card(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("今日训练", size=16, weight=ft.FontWeight.W_600, color=sc.text),
                            ft.Container(expand=True),
                            ft.TextButton(
                                "编辑",
                                style=ft.ButtonStyle(color=sc.accent),
                                on_click=self._edit_plan,
                            ),
                            ft.Text(
                                f"{percent}%",
                                size=20,
                                weight=ft.FontWeight.W_700,
                                color=sc.accent,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    track,
                    *plan_rows,
                    ft.Divider(height=1, color=sc.divider),
                    ft.Row(
                        [
                            self._mini_stat("时长", str(stats["durationMinutes"]), "分钟"),
                            self._mini_stat(
                                "消耗",
                                str(stats["todayCalories"]),
                                "千卡",
                                value_color=sc.calorie,
                            ),
                            self._mini_stat("本周", str(week_count), "次"),
                        ]
                    ),
                    ft.FilledButton(
                        cta_label,
                        bgcolor=sc.accent,
                        color=sc.on_cta,
                        height=48,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=999)),
                        on_click=lambda e: self._start_plan() if plan else self._edit_plan(),
                    ),
                ],
                spacing=12,
                tight=True,
            ),
            padding=16,
        )

        children.append(
            ft.Container(
                padding=ft.Padding.only(left=20, top=20, right=20, bottom=8),
                content=today_card,
            )
        )

        children.append(
            ft.Container(
                padding=ft.Padding.only(left=20, top=28, right=20, bottom=12),
                content=section_header(
                    "精选",
                    action_label="全部",
                    on_action=self.on_open_courses,
                ),
            )
        )

        featured_cards: list[ft.Control] = []
        for w in recommended:
            card = matte_card(
                ft.Column(
                    [
                        course_cover(exercise=w, height=88, border_radius=12),
                        ft.Text(w.name, weight=ft.FontWeight.W_600, color=sc.text, size=14),
                        ft.Text(
                            f"{w.duration} 分钟 · {w.difficulty}",
                            size=12,
                            color=sc.text_secondary,
                        ),
                    ],
                    spacing=8,
                    tight=True,
                ),
                padding=12,
            )
            card.width = 160
            card.on_click = lambda e, c=w: self._open_course(c)
            featured_cards.append(card)

        children.append(
            ft.Container(
                height=176,
                content=ft.Row(
                    featured_cards,
                    spacing=12,
                    scroll=ft.ScrollMode.AUTO,
                )
                if featured_cards
                else ft.Text("暂时没有推荐", color=sc.text_secondary),
                padding=ft.Padding.symmetric(horizontal=20),
            )
        )

        children.append(
            ft.Container(
                padding=ft.Padding.only(left=20, top=28, right=20, bottom=8),
                content=section_header("快捷开始"),
            )
        )

        chips = []
        for name in quick:
            target = self._svc.get_quick_target(name)
            chips.append(
                ft.Container(
                    bgcolor=sc.surface,
                    border=ft.Border.all(1, sc.border),
                    border_radius=999,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    on_click=lambda e, a=name: self.on_start_training(a),
                    content=ft.Row(
                        [
                            action_thumb(name, size=28),
                            ft.Text(name, size=14, weight=ft.FontWeight.W_600, color=sc.text),
                            *(
                                [ft.Text(target, size=12, color=sc.text_secondary)]
                                if target
                                else []
                            ),
                        ],
                        spacing=8,
                        tight=True,
                    ),
                )
            )

        children.append(
            ft.Container(
                padding=ft.Padding.only(left=20, top=0, right=20, bottom=32),
                content=ft.Row(chips, spacing=8, scroll=ft.ScrollMode.AUTO),
            )
        )

        self._scroll.controls = children
        if self._host:
            try:
                self.update()
            except Exception:
                pass

    def _mini_stat(
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
                                size=20,
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
                spacing=4,
                tight=True,
            ),
        )
