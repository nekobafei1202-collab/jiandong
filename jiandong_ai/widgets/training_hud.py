from __future__ import annotations

from datetime import datetime

import flet as ft

from jiandong_ai.app.theme import (
    HUD_CANVAS,
    HUD_CORAL,
    HUD_CYAN,
    HUD_DIVIDER,
    HUD_GLASS_STROKE,
    HUD_GREEN,
    HUD_METRIC_BLUE,
    HUD_METRIC_ORANGE,
    HUD_METRIC_PURPLE,
    HUD_RECORD_RED,
    HUD_SURFACE_MUTED,
    HUD_TEXT,
    HUD_TEXT_SECONDARY,
    HUD_TEXT_TERTIARY,
    HUD_TIP_AMBER_BG,
    HUD_TIP_AMBER_TEXT,
    glass_container,
)


def _fmt_mmss(seconds: int) -> str:
    total = max(0, min(int(seconds), 99 * 60 + 59))
    m = total // 60
    s = total % 60
    return f"{m:02d}:{s:02d}"


def _hud_icon_btn(icon, on_click, *, size: float = 36) -> ft.Control:
    return glass_container(
        content=ft.IconButton(
            icon=icon,
            icon_color=HUD_TEXT,
            icon_size=size * 0.42,
            on_click=on_click,
            style=ft.ButtonStyle(padding=0),
        ),
        padding=ft.Padding.all(size * 0.12),
        border_radius=size / 2,
    )


def build_top_bar(
    *,
    elapsed_seconds: int = 0,
    action_name: str = "深蹲",
    ai_active: bool = False,
    recording: bool = False,
    on_close=None,
    on_switch_camera=None,
) -> ft.Control:
    """Close · REC+timer · action name · AI pill · switch cam."""
    left: list[ft.Control] = []
    if on_close is not None:
        left.append(_hud_icon_btn(ft.Icons.CLOSE, lambda e: on_close()))
        left.append(ft.Container(width=8))

    left.append(
        glass_container(
            content=ft.Row(
                [
                    ft.Container(
                        width=8,
                        height=8,
                        border_radius=999,
                        bgcolor=HUD_RECORD_RED if recording else "#FFFFFF61",
                    ),
                    ft.Text(
                        _fmt_mmss(elapsed_seconds),
                        size=13,
                        weight=ft.FontWeight.W_700,
                        color=HUD_TEXT,
                    ),
                ],
                spacing=8,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=7),
        )
    )

    right: list[ft.Control] = [
        glass_container(
            content=ft.Row(
                [
                    ft.Container(
                        width=8,
                        height=8,
                        border_radius=999,
                        bgcolor=HUD_GREEN if ai_active else "#FFFFFF61",
                    ),
                    ft.Text(
                        "AI已激活" if ai_active else "AI未激活",
                        size=12,
                        weight=ft.FontWeight.W_600,
                        color=HUD_TEXT,
                    ),
                ],
                spacing=6,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=7),
        )
    ]
    if on_switch_camera is not None:
        right.append(ft.Container(width=8))
        right.append(_hud_icon_btn(ft.Icons.CAMERASWITCH, lambda e: on_switch_camera()))

    return ft.Row(
        [
            ft.Row(left, spacing=0, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(width=6),
            ft.Container(
                expand=True,
                content=glass_container(
                    content=ft.Text(
                        action_name,
                        size=15,
                        weight=ft.FontWeight.W_700,
                        color=HUD_TEXT,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                ),
            ),
            ft.Container(width=6),
            ft.Row(right, spacing=0, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ],
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def build_rep_counter(
    *,
    set_index: int = 1,
    set_total: int | None = None,
    rep_count: int = 0,
    rep_target: int | None = None,
    unit: str = "次",
    hide_count: bool = False,
) -> ft.Control:
    if hide_count:
        count_label = "--"
        unit_label = ""
    elif rep_target and rep_target > 0:
        count_label = f"{int(rep_count)}/{int(rep_target)}"
        unit_label = f" {unit}" if unit else ""
    else:
        count_label = str(rep_count)
        unit_label = f" {unit}" if unit else ""
    # set_index = current set, set_total = target sets (e.g. 2/4).
    if hide_count:
        set_label = "组 --"
    elif set_total and set_total > 0:
        set_label = f"组 {set_index}/{set_total}"
    else:
        set_label = f"组 {set_index}"
    return ft.Column(
        [
            glass_container(
                content=ft.Text(
                    set_label,
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color=HUD_TEXT,
                ),
                padding=ft.Padding.symmetric(horizontal=14, vertical=5),
            ),
            ft.Container(height=10),
            glass_container(
                content=ft.Row(
                    [
                        ft.Text(
                            count_label,
                            size=36,
                            weight=ft.FontWeight.W_800,
                            color=HUD_TEXT,
                        ),
                        ft.Text(
                            unit_label,
                            size=14,
                            weight=ft.FontWeight.W_700,
                            color=HUD_TEXT,
                        ),
                    ],
                    spacing=0,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                ),
                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                border_radius=18,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=0,
        tight=True,
    )


def build_posture_ring(*, score: int = 0, has_score: bool = False) -> ft.Control:
    pct = max(0, min(100, int(score))) if has_score else 0
    label = f"{pct}%" if has_score else "--"
    ring_color = HUD_GREEN if has_score and pct >= 70 else (HUD_CORAL if has_score else HUD_CYAN)
    return ft.Column(
        [
            ft.Stack(
                [
                    ft.Container(
                        width=92,
                        height=92,
                        border_radius=999,
                        border=ft.Border.all(8, "#FFFFFF29"),
                    ),
                    ft.Container(
                        width=92,
                        height=92,
                        alignment=ft.Alignment.CENTER,
                        content=ft.ProgressRing(
                            value=(pct / 100.0) if has_score else None,
                            width=84,
                            height=84,
                            stroke_width=8,
                            color=ring_color,
                            bgcolor="#FFFFFF14",
                        ),
                    ),
                    ft.Container(
                        width=92,
                        height=92,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(
                            label,
                            size=22,
                            weight=ft.FontWeight.W_800,
                            color=HUD_TEXT,
                        ),
                    ),
                ],
                width=92,
                height=92,
            ),
            ft.Container(height=6),
            ft.Text("姿势", size=12, weight=ft.FontWeight.W_600, color=HUD_TEXT),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=0,
        tight=True,
    )


def build_effort_pill(*, completed: int = 0, target: int = 10) -> ft.Control:
    tgt = max(1, int(target))
    done = max(0, int(completed))
    ratio = min(1.0, done / tgt)
    if ratio >= 0.8:
        emoji = "\U0001f604"
    elif ratio >= 0.4:
        emoji = "\U0001f642"
    else:
        emoji = "\U0001f610"
    return glass_container(
        content=ft.Row(
            [
                ft.Text(emoji, size=14),
                ft.Container(
                    width=56,
                    height=5,
                    border_radius=4,
                    bgcolor="#FFFFFF3D",
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    content=ft.Container(
                        width=max(2, int(56 * ratio)),
                        height=5,
                        bgcolor=HUD_METRIC_BLUE,
                    ),
                ),
                ft.Text(
                    f"{done}/{tgt}",
                    size=12,
                    weight=ft.FontWeight.W_700,
                    color=HUD_TEXT,
                ),
            ],
            spacing=8,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border_radius=999,
    )


def build_rest_countdown(
    *,
    seconds: int = 0,
    label: str = "组间休息",
) -> ft.Control:
    """Centered large rest countdown for Flet desktop HUD."""
    return ft.Column(
        [
            ft.Text(
                label or "组间休息",
                size=18,
                weight=ft.FontWeight.W_600,
                color=HUD_TEXT_SECONDARY,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Text(
                str(max(0, int(seconds))),
                size=72,
                weight=ft.FontWeight.W_700,
                color=HUD_TEXT,
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Text(
                "秒",
                size=16,
                weight=ft.FontWeight.W_500,
                color=HUD_TEXT_TERTIARY,
                text_align=ft.TextAlign.CENTER,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=4,
        tight=True,
    )


def build_set_nav(
    *,
    on_previous=None,
    on_next=None,
    on_pick=None,
    can_previous: bool = False,
    can_next: bool = False,
    show_pick: bool = False,
    prev_label: str = "上一组",
    next_label: str = "下一组",
) -> ft.Control:
    """Set/action nav (optional 选动作 for multi-action idle)."""
    middle: ft.Control
    if show_pick and on_pick is not None:
        middle = ft.TextButton(
            "选动作",
            style=ft.ButtonStyle(color=HUD_CYAN),
            on_click=lambda e: on_pick(),
        )
    else:
        middle = ft.Container(expand=True)
    return ft.Row(
        [
            ft.TextButton(
                prev_label,
                style=ft.ButtonStyle(
                    color=HUD_TEXT if can_previous else HUD_TEXT_TERTIARY,
                ),
                disabled=not can_previous,
                on_click=lambda e: on_previous() if on_previous and can_previous else None,
            ),
            ft.Container(expand=True),
            middle,
            ft.Container(expand=True),
            ft.TextButton(
                next_label,
                style=ft.ButtonStyle(
                    color=HUD_TEXT if can_next else HUD_TEXT_TERTIARY,
                ),
                disabled=not can_next,
                on_click=lambda e: on_next() if on_next and can_next else None,
            ),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def build_queue_nav(
    *,
    on_previous=None,
    on_next=None,
    on_pick=None,
    can_previous: bool = False,
    can_next: bool = False,
) -> ft.Control:
    """Deprecated alias — set navigation uses build_set_nav."""
    return build_set_nav(
        on_previous=on_previous,
        on_next=on_next,
        on_pick=on_pick,
        can_previous=can_previous,
        can_next=can_next,
        show_pick=on_pick is not None,
    )


def build_demo_window(
    *,
    on_close=None,
    title: str = "正确的姿势",
    exercise_id: str | None = None,
) -> ft.Control:
    from jiandong_ai.widgets.demo_guide_pane import DemoGuidePane

    demo = DemoGuidePane(exercise_id=exercise_id, height=122)
    return ft.Container(
        width=108,
        content=glass_container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                title,
                                size=11,
                                weight=ft.FontWeight.W_700,
                                color=HUD_TEXT,
                                expand=True,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_size=16,
                                icon_color="#FFFFFFB3",
                                on_click=lambda e: on_close() if on_close else None,
                                style=ft.ButtonStyle(padding=0),
                            ),
                        ],
                        spacing=0,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        width=92,
                        height=122,
                        border_radius=12,
                        clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        bgcolor="#1A2430",
                        border=ft.Border.all(1, HUD_GLASS_STROKE),
                        content=demo,
                    ),
                ],
                spacing=8,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=ft.Padding.all(8),
            border_radius=16,
        ),
    )


def build_correction_banner(
    *,
    title: str,
    subtitle: str | None = None,
    is_warning: bool = True,
) -> ft.Control:
    if not (title or "").strip():
        return ft.Container(height=0)
    bg = HUD_TIP_AMBER_BG if is_warning else "#5ED66259"
    sub_color = HUD_TIP_AMBER_TEXT if is_warning else "#FFFFFFD9"
    show_sub = bool(subtitle and subtitle.strip() and subtitle.strip() != title.strip())
    return ft.Container(
        bgcolor=bg,
        border=ft.Border.all(1, "#FFFFFF24"),
        border_radius=20,
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        content=ft.Row(
            [
                ft.Container(
                    width=32,
                    height=32,
                    border_radius=999,
                    bgcolor="#FFFFFF1F",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(
                        ft.Icons.PRIORITY_HIGH if is_warning else ft.Icons.CHECK,
                        color=HUD_TEXT,
                        size=18,
                    ),
                ),
                ft.Column(
                    [
                        ft.Text(title, size=16, weight=ft.FontWeight.W_700, color=HUD_TEXT),
                        *(
                            [
                                ft.Text(
                                    subtitle or "",
                                    size=13,
                                    weight=ft.FontWeight.W_500,
                                    color=sub_color,
                                )
                            ]
                            if show_sub
                            else []
                        ),
                    ],
                    spacing=2,
                    expand=True,
                    tight=True,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def build_bottom_controls(
    *,
    phase: str = "idle",
    on_start=None,
    on_pause=None,
    on_stop=None,
    on_resume=None,
    on_end=None,
    on_switch_camera=None,
    show_manual_continue: bool = False,
    on_manual_continue=None,
    start_enabled: bool = True,
) -> ft.Control:
    """phase: idle | running | paused — coral start / pause+stop / resume+end."""
    p = (phase or "idle").lower()

    if p == "idle":
        return ft.Container(
            width=float("inf"),
            content=ft.FilledButton(
                "开始训练",
                bgcolor=HUD_CORAL if start_enabled else HUD_SURFACE_MUTED,
                color="white" if start_enabled else HUD_TEXT_TERTIARY,
                height=54,
                disabled=not start_enabled,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=999)),
                on_click=lambda e: on_start() if on_start and start_enabled else None,
            ),
        )

    if p == "paused":
        rows: list[ft.Control] = [
            ft.FilledButton(
                "继续训练",
                bgcolor=HUD_GREEN,
                color=HUD_CANVAS,
                height=50,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=999)),
                on_click=lambda e: on_resume() if on_resume else None,
            ),
            ft.OutlinedButton(
                "结束训练",
                height=48,
                style=ft.ButtonStyle(
                    color=HUD_RECORD_RED,
                    side=ft.BorderSide(1, HUD_RECORD_RED),
                    shape=ft.RoundedRectangleBorder(radius=999),
                ),
                on_click=lambda e: on_end() if on_end else None,
            ),
        ]
        if on_switch_camera is not None:
            rows.append(
                ft.TextButton(
                    "切换摄像头",
                    style=ft.ButtonStyle(color=HUD_CYAN),
                    on_click=lambda e: on_switch_camera(),
                )
            )
        return ft.Column(rows, spacing=10, tight=True)

    # running
    controls: list[ft.Control] = []
    if show_manual_continue:
        controls.append(
            ft.FilledButton(
                "完成并继续",
                bgcolor=HUD_GREEN,
                color=HUD_CANVAS,
                height=48,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=999)),
                on_click=lambda e: on_manual_continue() if on_manual_continue else None,
            )
        )
        controls.append(ft.Container(height=12))

    pause_btn = ft.Column(
        [
            glass_container(
                content=ft.IconButton(
                    icon=ft.Icons.PAUSE,
                    icon_color=HUD_TEXT,
                    icon_size=26,
                    on_click=lambda e: on_pause() if on_pause else None,
                    style=ft.ButtonStyle(padding=0),
                ),
                padding=ft.Padding.all(14),
                border_radius=999,
            ),
            ft.Text("暂停", size=12, weight=ft.FontWeight.W_600, color=HUD_TEXT),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=6,
        tight=True,
    )

    stop_btn = ft.Container(
        width=78,
        height=78,
        border_radius=999,
        border=ft.Border.all(4, "white"),
        bgcolor="#00000040",
        alignment=ft.Alignment.CENTER,
        on_click=lambda e: on_stop() if on_stop else None,
        content=ft.Container(
            width=28,
            height=28,
            border_radius=6,
            bgcolor=HUD_RECORD_RED,
        ),
    )

    controls.append(
        ft.Row(
            [
                pause_btn,
                ft.Container(expand=True),
                stop_btn,
                ft.Container(expand=True),
                ft.Container(width=72),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )
    return ft.Column(controls, spacing=0, tight=True)


def _metric_cell(*, icon, icon_color: str, value: str, label: str) -> ft.Control:
    return ft.Container(
        expand=True,
        padding=ft.Padding.symmetric(vertical=8),
        content=ft.Column(
            [
                ft.Icon(icon, color=icon_color, size=22),
                ft.Text(value, size=20, weight=ft.FontWeight.W_800, color=HUD_TEXT, text_align=ft.TextAlign.CENTER),
                ft.Text(label, size=12, color=HUD_TEXT_SECONDARY),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
            tight=True,
        ),
    )


def build_finished_summary(
    *,
    action_name: str,
    finished_at: datetime | None = None,
    sets: int = 1,
    reps: int = 0,
    posture_pct: int = 0,
    duration_seconds: int = 0,
    calories: int = 0,
    effort_out_of_10: int = 6,
    insight_reason: str = "本次训练节奏稳定，整体完成度不错。",
    insight_key_point: str = "关键点：下蹲时注意膝盖方向与脚尖一致。",
    next_focus: str = "下次优先保证动作幅度，再逐步提升次数。",
    on_delete=None,
    on_save=None,
    on_share=None,
    on_download=None,
    saving: bool = False,
    saved: bool = False,
) -> ft.Control:
    when = finished_at or datetime.now()
    date_label = f"{when.month}月{when.day}日 {when.hour:02d}:{when.minute:02d}"
    time_label = _fmt_mmss(duration_seconds)
    effort = max(0, min(10, int(effort_out_of_10)))
    emoji = "😄" if effort >= 8 else ("🙂" if effort >= 4 else "😐")
    save_label = "保存中…" if saving else ("已保存" if saved else "保存训练")

    hero = ft.Container(
        border_radius=24,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        height=180,
        bgcolor=HUD_SURFACE_MUTED,
        content=ft.Stack(
            [
                ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.FITNESS_CENTER, size=56, color=HUD_CYAN),
                ),
                ft.Container(
                    expand=True,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_CENTER,
                        end=ft.Alignment.BOTTOM_CENTER,
                        colors=["#66000000", "#CC070A0F"],
                    ),
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.all(16),
                    alignment=ft.Alignment(-1, 1),
                    content=ft.Column(
                        [
                            glass_container(
                                content=ft.Text(
                                    "训练完成",
                                    size=12,
                                    weight=ft.FontWeight.W_700,
                                    color=HUD_GREEN,
                                ),
                                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                            ),
                            ft.Text(action_name, size=28, weight=ft.FontWeight.W_800, color=HUD_TEXT),
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.CALENDAR_TODAY, size=14, color=HUD_TEXT_SECONDARY),
                                    ft.Text(date_label, size=13, color=HUD_TEXT_SECONDARY),
                                ],
                                spacing=6,
                                tight=True,
                            ),
                        ],
                        spacing=6,
                        tight=True,
                    ),
                ),
            ]
        ),
    )

    metrics = glass_container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        _metric_cell(icon=ft.Icons.LAYERS, icon_color=HUD_METRIC_BLUE, value=str(sets), label="组数"),
                        _metric_cell(icon=ft.Icons.AUTORENEW, icon_color=HUD_METRIC_PURPLE, value=str(reps), label="次数"),
                        _metric_cell(
                            icon=ft.Icons.VERIFIED_USER,
                            icon_color=HUD_GREEN,
                            value=f"{posture_pct}%",
                            label="姿势",
                        ),
                    ]
                ),
                ft.Row(
                    [
                        _metric_cell(
                            icon=ft.Icons.TIMER_OUTLINED,
                            icon_color=HUD_METRIC_BLUE,
                            value=time_label,
                            label="时间",
                        ),
                        _metric_cell(
                            icon=ft.Icons.LOCAL_FIRE_DEPARTMENT,
                            icon_color=HUD_METRIC_ORANGE,
                            value=str(calories),
                            label="卡路里",
                        ),
                        _metric_cell(
                            icon=ft.Icons.SENTIMENT_SATISFIED_ALT,
                            icon_color=HUD_GREEN,
                            value=f"{effort}/10 {emoji}",
                            label="努力",
                        ),
                    ]
                ),
            ],
            spacing=8,
            tight=True,
        ),
        padding=ft.Padding.only(left=12, top=16, right=12, bottom=8),
        border_radius=24,
    )

    insight = glass_container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.CircleAvatar(
                            radius=14,
                            bgcolor=HUD_CORAL,
                            content=ft.Icon(ft.Icons.AUTO_AWESOME, size=16, color="white"),
                        ),
                        ft.Text("AI 教练洞察", size=16, weight=ft.FontWeight.W_700, color=HUD_TEXT),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(insight_reason, size=14, color=HUD_TEXT_SECONDARY),
                ft.Text(insight_key_point, size=14, color=HUD_TEXT_SECONDARY),
                ft.Container(
                    bgcolor="#070A0F8C",
                    border_radius=14,
                    border=ft.Border.only(left=ft.BorderSide(3, HUD_CORAL)),
                    padding=ft.Padding.all(12),
                    content=ft.Column(
                        [
                            ft.Text("下次训练重点", size=13, weight=ft.FontWeight.W_700, color=HUD_CORAL),
                            ft.Text(next_focus, size=13, color=HUD_TEXT),
                        ],
                        spacing=6,
                        tight=True,
                    ),
                ),
            ],
            spacing=12,
            tight=True,
        ),
        padding=ft.Padding.all(16),
        border_radius=24,
    )

    bottom = ft.Row(
        [
            glass_container(
                content=ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=HUD_RECORD_RED,
                    on_click=lambda e: on_delete() if on_delete else None,
                ),
                padding=ft.Padding.all(8),
                border_radius=999,
            ),
            ft.Container(
                expand=True,
                content=ft.FilledButton(
                    save_label,
                    bgcolor=HUD_CORAL,
                    color="white",
                    disabled=saved or saving,
                    height=52,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=999)),
                    on_click=lambda e: on_save() if on_save else None,
                ),
            ),
            glass_container(
                content=ft.IconButton(
                    icon=ft.Icons.IOS_SHARE,
                    icon_color=HUD_TEXT,
                    on_click=lambda e: on_share() if on_share else None,
                ),
                padding=ft.Padding.all(8),
                border_radius=999,
            ),
            glass_container(
                content=ft.IconButton(
                    icon=ft.Icons.DOWNLOAD,
                    icon_color=HUD_TEXT,
                    on_click=lambda e: on_download() if on_download else None,
                ),
                padding=ft.Padding.all(8),
                border_radius=999,
            ),
        ],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return ft.Column(
        [
            ft.Column(
                [hero, metrics, insight],
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            bottom,
        ],
        expand=True,
        spacing=12,
    )
