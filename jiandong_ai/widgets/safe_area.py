"""System inset helpers — mirror Flutter SafeArea for status bar / home indicator."""

from __future__ import annotations

import flet as ft


def safe_area(
    content: ft.Control,
    *,
    expand: bool = True,
    top: bool = True,
    bottom: bool = True,
    left: bool = True,
    right: bool = True,
) -> ft.SafeArea:
    return ft.SafeArea(
        content=content,
        expand=expand,
        avoid_intrusions_top=top,
        avoid_intrusions_bottom=bottom,
        avoid_intrusions_left=left,
        avoid_intrusions_right=right,
    )


def mount(page: ft.Page, root: ft.Control, *, safe: bool = True) -> None:
    """Replace page root. Auth/splash use safe=True; MainShell uses safe=False
    (shell applies top/bottom insets itself so training stays edge-to-edge)."""
    page.controls.clear()
    page.add(safe_area(root) if safe else root)
    page.update()
