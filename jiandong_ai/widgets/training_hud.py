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


# ---- Finished summary (light "report card" theme, page-local constants) ----
_SUM_BG = "#F5F7FA"
_SUM_CARD = "#FFFFFF"
_SUM_BORDER = "#E5E7EB"
_SUM_TEXT = "#111827"
_SUM_TEXT2 = "#6B7280"
_SUM_GREEN = "#16A34A"
_SUM_GREEN_BG = "#F0FDF4"
_SUM_ORANGE = "#F97316"
_SUM_RED = "#EF4444"
_SUM_BLUE = "#1D4ED8"

_ACTION_ICON_ASSETS = {
    "squat": "assets/actions/squat.png",
    "pushup": "assets/actions/pushup.png",
    "reverse_lunge": "assets/actions/lunge.png",
    "plank": "assets/actions/plank.png",
    "jumping_jack": "assets/actions/cardio.png",
    "crunch": "assets/actions/crunch.png",
    "side_bridge": "assets/actions/core.png",
    "dead_bug": "assets/actions/dead_bug.png",
    "high_knees": "assets/actions/high_knees.png",
    "glute_bridge": "assets/actions/lower_body.png",
}


def _action_icon_asset(action_name: str) -> str | None:
    from jiandong_ai.ai.action.exercise_kind import ExerciseKind
    from jiandong_ai.widgets.course_cover import asset_src

    for key, src in _ACTION_ICON_ASSETS.items():
        if getattr(ExerciseKind, f"is_{key}")(action_name):
            return asset_src(src)
    return None


def posture_encouragement(pct: int) -> str:
    if pct >= 90:
        return "非常棒！"
    if pct >= 70:
        return "很不错！"
    return "继续加油！"


def build_session_summary_text(actions: list[dict]) -> str:
    """Whole-session summary: praise best posture, flag the weakest as next focus."""
    done = [a for a in actions if a.get("name")]
    if not done:
        return "本次训练已完成，节奏稳定，继续保持。"
    names = "、".join(f"「{a['name']}」" for a in done)
    total = sum(int(a.get("reps") or 0) for a in done)
    base = f"本次训练完成了{names}"
    if total > 0:
        base += f"，累计 {total} 次。"
    else:
        base += "。"
    scored = [a for a in done if a.get("avg_score")]
    if not scored:
        return base + "本次暂无姿势评分，保持当前节奏，稳步提升。"
    best = max(scored, key=lambda a: a["avg_score"])
    worst = min(scored, key=lambda a: a["avg_score"])
    text = base + f"「{best['name']}」姿势最标准（{best['avg_score']}%），值得表扬；"
    if best is worst:
        return text + "整体表现均衡，继续加油。"
    return text + (
        f"「{worst['name']}」是下次重点（{worst['avg_score']}%），"
        "优先保证姿势幅度，再逐步提升次数。"
    )


def _sum_card(content: ft.Control, *, padding: float = 16) -> ft.Container:
    return ft.Container(
        bgcolor=_SUM_CARD,
        border_radius=18,
        border=ft.Border.all(1, _SUM_BORDER),
        padding=ft.Padding.all(padding),
        content=content,
    )


def _stat_cell(
    *,
    value: str,
    unit: str,
    label: str,
    sub: str,
    value_color: str = _SUM_TEXT,
    sub_color: str = _SUM_TEXT2,
) -> ft.Control:
    return ft.Container(
        expand=True,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(value, size=28, weight=ft.FontWeight.W_800, color=value_color),
                        ft.Text(unit, size=12, weight=ft.FontWeight.W_600, color=_SUM_TEXT2),
                    ],
                    spacing=2,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                ),
                ft.Text(label, size=12, color=_SUM_TEXT2),
                ft.Text(sub, size=11, color=sub_color, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=3,
            tight=True,
        ),
    )


def _plain_icon(icon, color: str, on_click) -> ft.Control:
    return ft.IconButton(
        icon=icon,
        icon_color=color,
        icon_size=22,
        on_click=lambda e: on_click() if on_click else None,
        style=ft.ButtonStyle(padding=0),
    )


def build_finished_summary(
    *,
    session_name: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    sets: int = 1,
    duration_seconds: int = 0,
    calories: int = 0,
    posture_pct: int = 0,
    planned_actions: int = 0,
    actions: list[dict] | None = None,
    prev_calories: int | None = None,
    prev_duration_seconds: int | None = None,
    summary_text: str = "",
    muscle_front_src: str | None = None,
    muscle_back_src: str | None = None,
    on_back=None,
    on_delete=None,
    on_share=None,
    on_download=None,
) -> ft.Control:
    end = finished_at or datetime.now()
    minutes = max(1, round(duration_seconds / 60)) if duration_seconds else 0
    if started_at:
        date_label = (
            f"{end.month}月{end.day}日 "
            f"{started_at.hour:02d}:{started_at.minute:02d}–{end.hour:02d}:{end.minute:02d}"
        )
    else:
        date_label = f"{end.month}月{end.day}日 {end.hour:02d}:{end.minute:02d}"
    done_actions = list(actions or [])

    def _delta(cur: int, prev: int | None, unit: str) -> str:
        if prev is None or prev <= 0:
            return "首次训练"
        diff_pct = round((cur - prev) / prev * 100)
        sign = "+" if diff_pct >= 0 else ""
        return f"比上次 {sign}{diff_pct}%"

    more_menu = ft.PopupMenuButton(
        icon=ft.Icons.MORE_HORIZ,
        icon_color=_SUM_TEXT,
        items=[
            ft.PopupMenuItem(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.IMAGE_OUTLINED, size=18, color=_SUM_TEXT2),
                        ft.Text("保存本地", size=14, color=_SUM_TEXT),
                    ],
                    spacing=10,
                    tight=True,
                ),
                on_click=lambda e: on_download() if on_download else None,
            ),
            ft.PopupMenuItem(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.DELETE_OUTLINE, size=18, color=_SUM_RED),
                        ft.Text("删除", size=14, color=_SUM_RED),
                    ],
                    spacing=10,
                    tight=True,
                ),
                on_click=lambda e: on_delete() if on_delete else None,
            ),
        ],
    )
    top_bar = ft.Row(
        [
            _plain_icon(ft.Icons.ARROW_BACK, _SUM_TEXT, on_back),
            ft.Text(
                "训练完成",
                size=17,
                weight=ft.FontWeight.W_700,
                color=_SUM_TEXT,
                text_align=ft.TextAlign.CENTER,
                expand=True,
            ),
            _plain_icon(ft.Icons.IOS_SHARE, _SUM_TEXT, on_share),
            more_menu,
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    hero = ft.Row(
        [
            ft.Icon(ft.Icons.CHECK_CIRCLE, color=_SUM_GREEN, size=44),
            ft.Column(
                [
                    ft.Text("太棒了！", size=24, weight=ft.FontWeight.W_800, color=_SUM_TEXT),
                    ft.Text("你已完成本次训练计划", size=13, color=_SUM_TEXT2),
                ],
                spacing=2,
                tight=True,
            ),
            ft.Container(expand=True),
            ft.Text(
                "每一次坚持，\n都是更好的自己。",
                size=11,
                color=_SUM_TEXT2,
                text_align=ft.TextAlign.RIGHT,
            ),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    info = ft.Column(
        [
            ft.Row(
                [
                    ft.Icon(ft.Icons.FITNESS_CENTER, size=15, color=_SUM_TEXT2),
                    ft.Text(session_name, size=14, weight=ft.FontWeight.W_600, color=_SUM_TEXT),
                    ft.Text(f"{sets}组", size=13, color=_SUM_TEXT2),
                    ft.Icon(ft.Icons.TIMER_OUTLINED, size=14, color=_SUM_TEXT2),
                    ft.Text(f"{minutes}分钟", size=13, color=_SUM_TEXT2),
                ],
                spacing=6,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                [
                    ft.Icon(ft.Icons.CALENDAR_TODAY, size=13, color=_SUM_TEXT2),
                    ft.Text(date_label, size=12, color=_SUM_TEXT2),
                ],
                spacing=6,
                tight=True,
            ),
        ],
        spacing=6,
        tight=True,
    )

    stats = _sum_card(
        ft.Row(
            [
                _stat_cell(
                    value=str(calories),
                    unit="千卡",
                    label="总消耗",
                    sub=_delta(calories, prev_calories, "千卡"),
                    value_color=_SUM_ORANGE,
                    sub_color=_SUM_ORANGE if prev_calories else _SUM_TEXT2,
                ),
                _stat_cell(
                    value=str(minutes),
                    unit="分钟",
                    label="训练时长",
                    sub=_delta(minutes, round(prev_duration_seconds / 60) if prev_duration_seconds else None, "分钟"),
                ),
                _stat_cell(
                    value=str(len(done_actions)),
                    unit="个",
                    label="完成动作",
                    sub=f"计划 {planned_actions} 个",
                ),
                _stat_cell(
                    value=f"{posture_pct}%" if posture_pct else "--",
                    unit="",
                    label="完成度",
                    sub=posture_encouragement(posture_pct) if posture_pct else "暂无评分",
                    value_color=_SUM_BLUE if posture_pct else _SUM_TEXT2,
                    sub_color=_SUM_GREEN if posture_pct >= 70 else _SUM_TEXT2,
                ),
            ]
        ),
        padding=14,
    )

    detail_rows: list[ft.Control] = []
    for a in done_actions:
        name = str(a.get("name") or "")
        reps = int(a.get("reps") or 0)
        a_sets = int(a.get("sets") or 1)
        score = a.get("avg_score")
        icon_src = _action_icon_asset(name)
        icon_ctrl: ft.Control = (
            ft.Image(src=icon_src, width=32, height=32, fit=ft.BoxFit.CONTAIN)
            if icon_src
            else ft.Icon(ft.Icons.FITNESS_CENTER, size=24, color=_SUM_TEXT2)
        )
        detail_rows.append(
            ft.Row(
                [
                    ft.Container(
                        width=40,
                        height=40,
                        border_radius=12,
                        bgcolor=_SUM_BG,
                        alignment=ft.Alignment.CENTER,
                        content=icon_ctrl,
                    ),
                    ft.Column(
                        [
                            ft.Text(name, size=14, weight=ft.FontWeight.W_600, color=_SUM_TEXT),
                            ft.Text(f"{a_sets}组 × {reps}次", size=12, color=_SUM_TEXT2),
                        ],
                        spacing=2,
                        tight=True,
                        expand=True,
                    ),
                    ft.Text(
                        f"{score}%" if score else "--",
                        size=15,
                        weight=ft.FontWeight.W_700,
                        color=_SUM_BLUE if score else _SUM_TEXT2,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
    detail = _sum_card(
        ft.Column(
            [
                ft.Text("训练详情", size=16, weight=ft.FontWeight.W_700, color=_SUM_TEXT),
                *detail_rows,
            ],
            spacing=12,
            tight=True,
        )
    )

    legend = ft.Row(
        [
            *[
                ft.Row(
                    [
                        ft.Container(width=10, height=10, border_radius=999, bgcolor=c),
                        ft.Text(t, size=11, color=_SUM_TEXT2),
                    ],
                    spacing=4,
                    tight=True,
                )
                for c, t in (
                    ("#1D4ED8", "高强度"),
                    ("#60A5FA", "中等强度"),
                    ("#BFDBFE", "轻度"),
                )
            ]
        ],
        spacing=14,
        alignment=ft.MainAxisAlignment.CENTER,
    )
    muscle_bodies: list[ft.Control] = []
    for src in (muscle_front_src, muscle_back_src):
        muscle_bodies.append(
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                content=ft.Image(src=src, height=230, fit=ft.BoxFit.CONTAIN) if src else None,
            )
        )
    muscle = _sum_card(
        ft.Column(
            [
                ft.Text("肌肉激活", size=16, weight=ft.FontWeight.W_700, color=_SUM_TEXT),
                ft.Text("本次训练主要激活了以下肌群", size=12, color=_SUM_TEXT2),
                ft.Row(muscle_bodies, spacing=8),
                legend,
            ],
            spacing=10,
            tight=True,
        )
    )

    summary_card = ft.Container(
        bgcolor=_SUM_GREEN_BG,
        border_radius=18,
        padding=ft.Padding.all(16),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.DESCRIPTION, size=16, color=_SUM_GREEN),
                        ft.Text("训练小结", size=15, weight=ft.FontWeight.W_700, color=_SUM_TEXT),
                    ],
                    spacing=6,
                ),
                ft.Text(summary_text, size=13, color="#374151"),
            ],
            spacing=8,
            tight=True,
        ),
    )

    return ft.Column(
        [top_bar, hero, info, stats, detail, muscle, summary_card],
        spacing=14,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
