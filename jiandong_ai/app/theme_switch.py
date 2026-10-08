"""Radial theme reveal — full-bleed old frame with a growing hole from the tap point."""

from __future__ import annotations

import asyncio
import math
from typing import Callable

import flet as ft

from jiandong_ai.app.theme import ShellColors
from jiandong_ai.app.theme_controller import ThemeController
from jiandong_ai.widgets.motion import THEME_REVEAL_MS, reduce_motion

_FRAME_PAD = 24
_SCREENSHOT_TIMEOUT_S = 1.0
_FRAME_MS = 16
_COVER_SETTLE_S = 0.064  # ~4 frames so ft.Image paints before theme flip


def ease_out_cubic(t: float) -> float:
    """Flutter Curves.easeOutCubic: 1 - (1 - t)^3."""
    t = max(0.0, min(1.0, float(t)))
    return 1.0 - (1.0 - t) ** 3


def max_radius(w: float, h: float, ox: float, oy: float) -> float:
    """Distance from origin to farthest corner (+ small pad)."""
    corners = ((0.0, 0.0), (w, 0.0), (0.0, h), (w, h))
    return max(math.hypot(cx - ox, cy - oy) for cx, cy in corners) + _FRAME_PAD


def hole_radius_at(t: float, max_r: float) -> float:
    """Growing hole radius at progress t in [0, 1] (never shrinks)."""
    return float(max_r) * ease_out_cubic(t)


def origin_to_alignment(ox: float, oy: float, w: float, h: float) -> ft.Alignment:
    """Map pixel origin to RadialGradient Alignment in [-1, 1]."""
    w = max(float(w), 1.0)
    h = max(float(h), 1.0)
    return ft.Alignment(ox / w * 2.0 - 1.0, oy / h * 2.0 - 1.0)


def mask_stops(t: float) -> list[float]:
    """DST_IN radial stops: transparent hole grows with t (0→1)."""
    edge = ease_out_cubic(t)
    return [0.0, edge, edge]


def _hole_shader(
    *,
    center: ft.Alignment,
    radius_frac: float,
    t: float,
) -> ft.RadialGradient:
    return ft.RadialGradient(
        center=center,
        radius=radius_frac,
        colors=[
            ft.Colors.TRANSPARENT,
            ft.Colors.TRANSPARENT,
            ft.Colors.WHITE,
        ],
        stops=mask_stops(t),
        tile_mode=ft.GradientTileMode.CLAMP,
    )


def _apply_theme_flip(page: ft.Page, on_rebuild: Callable | None) -> None:
    ThemeController.toggle()
    page.theme_mode = (
        ft.ThemeMode.DARK if ThemeController.get_is_dark() else ft.ThemeMode.LIGHT
    )
    page.bgcolor = ShellColors.canvas
    if on_rebuild:
        on_rebuild()


async def toggle_theme_radial(
    page: ft.Page,
    *,
    origin: tuple[float, float] | None = None,
    on_rebuild,
) -> None:
    """
    Full-bleed old screenshot (opaque) → flip theme underneath → grow a
    ShaderMask hole from the tap origin. Screenshot failure → instant toggle.
    """
    overlay: ft.ShaderMask | None = None
    try:
        w = float(page.width or 420)
        h = float(page.height or 860)
        ox, oy = origin or (w * 0.85, h * 0.55)

        if reduce_motion(page):
            _apply_theme_flip(page, on_rebuild)
            page.update()
            return

        png: bytes | None = None
        dpr = float(getattr(page, "device_pixel_ratio", None) or 1.0)
        capture_ratio = min(dpr, 1.5)
        try:
            if getattr(page, "enable_screenshots", False):
                png = await asyncio.wait_for(
                    page.take_screenshot(pixel_ratio=capture_ratio),
                    timeout=_SCREENSHOT_TIMEOUT_S,
                )
        except Exception:
            png = None

        if not png:
            _apply_theme_flip(page, on_rebuild)
            page.update()
            return

        R = max_radius(w, h, ox, oy)
        radius_frac = R / max(min(w, h), 1.0)
        center = origin_to_alignment(ox, oy, w, h)

        overlay = ft.ShaderMask(
            width=w,
            height=h,
            left=0,
            top=0,
            blend_mode=ft.BlendMode.DST_IN,
            shader=_hole_shader(center=center, radius_frac=radius_frac, t=0.0),
            content=ft.Image(
                src=png,
                width=w,
                height=h,
                fit=ft.BoxFit.FILL,
                gapless_playback=True,
                filter_quality=ft.FilterQuality.MEDIUM,
            ),
        )
        page.overlay.append(overlay)
        page.update()
        # Wait until the cover image has painted — otherwise bgcolor flash shows through.
        await asyncio.sleep(_COVER_SETTLE_S)

        _apply_theme_flip(page, on_rebuild)
        page.update()
        await asyncio.sleep(0.016)

        duration_s = THEME_REVEAL_MS / 1000.0
        elapsed = 0.0
        while elapsed < duration_s:
            t = elapsed / duration_s
            overlay.shader = _hole_shader(
                center=center, radius_frac=radius_frac, t=t
            )
            page.update()
            await asyncio.sleep(_FRAME_MS / 1000.0)
            elapsed += _FRAME_MS / 1000.0

        overlay.shader = _hole_shader(
            center=center, radius_frac=radius_frac, t=1.0
        )
        page.update()
        await asyncio.sleep(0.05)

        if overlay in page.overlay:
            page.overlay.remove(overlay)
            page.update()
    finally:
        page._theme_toggle_busy = False  # type: ignore[attr-defined]


def schedule_theme_toggle(
    page: ft.Page, *, origin: tuple[float, float] | None, on_rebuild
) -> None:
    if getattr(page, "_theme_toggle_busy", False):
        return
    page._theme_toggle_busy = True  # type: ignore[attr-defined]
    page.run_task(toggle_theme_radial, page, origin=origin, on_rebuild=on_rebuild)
