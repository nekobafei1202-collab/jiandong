"""Shell light/dark state. Flipping is_dark changes what ShellColors getters return."""

from __future__ import annotations

from collections.abc import Callable


class ThemeController:
    _is_dark: bool = False
    _listeners: list[Callable[[], None]] = []

    @classmethod
    def get_is_dark(cls) -> bool:
        return cls._is_dark

    @classmethod
    def set_dark(cls, value: bool) -> None:
        if cls._is_dark == value:
            return
        cls._is_dark = bool(value)
        for cb in list(cls._listeners):
            try:
                cb()
            except Exception:
                pass

    @classmethod
    def toggle(cls) -> None:
        cls.set_dark(not cls._is_dark)

    @classmethod
    def add_listener(cls, cb: Callable[[], None]) -> None:
        if cb not in cls._listeners:
            cls._listeners.append(cb)

    @classmethod
    def remove_listener(cls, cb: Callable[[], None]) -> None:
        try:
            cls._listeners.remove(cb)
        except ValueError:
            pass
