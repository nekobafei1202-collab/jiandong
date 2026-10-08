from __future__ import annotations

from pathlib import Path

import flet as ft

from jiandong_ai.app.constants import APP_NAME
from jiandong_ai.app.theme import ShellColors
from jiandong_ai.app.theme_controller import ThemeController
from jiandong_ai.pages.auth.login_page import build_login
from jiandong_ai.pages.auth.register_page import build_register
from jiandong_ai.pages.shell import MainShell
from jiandong_ai.pages.splash.splash_page import build_splash
from jiandong_ai.services.mock_service import AppSession, MockService
from jiandong_ai.widgets.safe_area import mount


def _asset_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main(page: ft.Page, *, preview: bool = False) -> None:
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.DARK if ThemeController.get_is_dark() else ft.ThemeMode.LIGHT
    page.bgcolor = ShellColors.canvas
    page.padding = 0
    page.window.width = 420
    page.window.height = 860
    page.fonts = {}
    # Needed for radial theme reveal (snapshot + growing hole).
    page.enable_screenshots = True

    svc = MockService.instance()
    svc.init(_asset_root() / "storage")

    def go_login(_: ft.ControlEvent | None = None) -> None:
        page.bgcolor = ShellColors.canvas
        mount(page, build_login(page, on_success=go_shell, on_register=go_register))

    def go_register(_: ft.ControlEvent | None = None) -> None:
        page.bgcolor = ShellColors.canvas
        mount(page, build_register(page, on_success=go_shell, on_back=go_login))

    def go_shell(_: ft.ControlEvent | None = None) -> None:
        page.bgcolor = ShellColors.canvas
        # Shell owns split SafeArea (catalog top + nav bottom; training edge-to-edge).
        mount(page, MainShell(page), safe=False)

    def go_splash() -> None:
        page.bgcolor = ShellColors.canvas
        mount(page, build_splash(page, on_done=go_login))

    if preview:
        AppSession.set_user(svc.get_current_user())
        go_shell()
    else:
        go_splash()


def run(*, preview: bool = False) -> None:
    ft.run(lambda page: main(page, preview=preview), assets_dir=str(_asset_root() / "assets"))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    run(preview=args.preview)
