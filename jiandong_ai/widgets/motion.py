"""Shared motion timing and ExpandingFilterChip (Flet port of Flutter motion.dart)."""

from __future__ import annotations

import flet as ft

from jiandong_ai.app.theme import ShellColors

STANDARD_MS = 280
THEME_REVEAL_MS = 520
HOME_REVEAL_MS = 350
PROGRESS_MS = 700
DRAG_LIFT_SCALE = 1.04


def reduce_motion(page: ft.Page | None) -> bool:
    if page is None:
        return False
    return bool(getattr(page, "disable_animations", False))


def duration_ms(page: ft.Page | None, base: int = STANDARD_MS) -> int:
    return 0 if reduce_motion(page) else base


def expanding_filter_chip(
    page: ft.Page | None,
    *,
    label: str,
    selected: bool,
    on_selected,
) -> ft.Control:
    """Exclusive filter chip — selected capsule grows (padding 14→18)."""
    ms = duration_ms(page)
    sc = ShellColors
    return ft.Container(
        bgcolor=sc.accent_soft if selected else sc.surface,
        border=ft.Border.all(1, sc.accent if selected else sc.border),
        border_radius=999,
        padding=ft.Padding.symmetric(horizontal=18 if selected else 14, vertical=8),
        animate=ft.Animation(ms, ft.AnimationCurve.EASE_OUT_CUBIC) if ms else None,
        on_click=lambda e: on_selected() if not selected else None,
        content=ft.Text(
            label,
            size=13,
            weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_500,
            color=sc.accent if selected else sc.text_secondary,
        ),
    )


def reveal_wrap(
    page: ft.Page | None,
    child: ft.Control,
    *,
    index: int = 0,
) -> ft.Control:
    """Staggered fade + slide-up entrance for home sections."""
    ms = duration_ms(page, HOME_REVEAL_MS)
    delay = 0 if ms == 0 else min(index * 40, 200)
    return ft.Container(
        content=child,
        opacity=1,
        offset=ft.Offset(0, 0),
        animate_opacity=ft.Animation(ms, ft.AnimationCurve.EASE_OUT_CUBIC) if ms else None,
        animate_offset=ft.Animation(ms, ft.AnimationCurve.EASE_OUT_CUBIC) if ms else None,
        data={"reveal_delay": delay},
    )
