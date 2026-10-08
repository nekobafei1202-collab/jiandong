"""Android system back: overlay registry + shell consume logic."""
from __future__ import annotations

from typing import Callable

_overlay_close: Callable[[], None] | None = None


def register_plan_editor(close: Callable[[], None]) -> None:
    global _overlay_close
    _overlay_close = close


def unregister_plan_editor() -> None:
    global _overlay_close
    _overlay_close = None


def close_plan_editor_if_open() -> bool:
    if _overlay_close is None:
        return False
    try:
        _overlay_close()
    finally:
        unregister_plan_editor()
    return True
