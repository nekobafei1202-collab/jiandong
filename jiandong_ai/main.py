from __future__ import annotations

from pathlib import Path

import flet as ft

from jiandong_ai.app.constants import APP_NAME, APP_TAGLINE
from jiandong_ai.app.theme import SHELL_ACCENT, SHELL_CANVAS, SHELL_SURFACE, SHELL_TEXT
from jiandong_ai.pages.auth.login_page import build_login
from jiandong_ai.pages.auth.register_page import build_register
from jiandong_ai.pages.shell import MainShell
from jiandong_ai.pages.splash.splash_page import build_splash
from jiandong_ai.services.mock_service import AppSession, MockService


def _asset_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main(page: ft.Page, *, preview: bool = False) -> None:
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = SHELL_CANVAS
    page.padding = 0
    page.window.width = 420
    page.window.height = 860
    page.fonts = {}

    svc = MockService.instance()
    svc.init(_asset_root() / "storage")

    def go_login(_: ft.ControlEvent | None = None) -> None:
        page.controls.clear()
        page.add(build_login(page, on_success=go_shell, on_register=go_register))
        page.update()

    def go_register(_: ft.ControlEvent | None = None) -> None:
        page.controls.clear()
        page.add(build_register(page, on_success=go_shell, on_back=go_login))
        page.update()

    def go_shell(_: ft.ControlEvent | None = None) -> None:
        page.controls.clear()
        page.add(MainShell(page))
        page.update()

    def go_splash() -> None:
        page.controls.clear()
        page.add(build_splash(page, on_done=go_login))
        page.update()

    if preview:
        AppSession.set_user(svc.get_current_user())
        go_shell()
    else:
        go_splash()


def run(*, preview: bool = False) -> None:
    ft.app(lambda page: main(page, preview=preview), assets_dir=str(_asset_root() / "assets"))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    run(preview=args.preview)
