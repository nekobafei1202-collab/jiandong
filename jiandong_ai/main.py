from __future__ import annotations

import os
from pathlib import Path

import flet as ft

from jiandong_ai.app.constants import APP_NAME
from jiandong_ai.app.theme import ShellColors
from jiandong_ai.app.theme_controller import ThemeController
from jiandong_ai.pages.auth.login_page import build_login
from jiandong_ai.pages.auth.register_page import build_register
from jiandong_ai.pages.shell import MainShell
from jiandong_ai.pages.splash.splash_page import build_splash
from jiandong_ai.services.ai_assistant import configure_deepseek_config_path
from jiandong_ai.services.mock_service import MockService
from jiandong_ai.widgets.safe_area import mount


def _asset_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main(page: ft.Page) -> None:
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.DARK if ThemeController.get_is_dark() else ft.ThemeMode.LIGHT
    page.bgcolor = ShellColors.canvas
    page.padding = 0
    page.fonts = {}
    # Needed for radial theme reveal (snapshot + growing hole).
    page.enable_screenshots = True

    svc = MockService.instance()
    storage_dir = Path(
        os.environ.get("FLET_APP_STORAGE_DATA") or (_asset_root() / "storage")
    )
    svc.init(storage_dir)
    from jiandong_ai.ai.session.android_bridge_session import is_android_runtime, _default_bridge_dir
    if is_android_runtime() and (_default_bridge_dir() / "system_reader.flag").exists():
        svc.set_voice_accessibility(True)
    configure_deepseek_config_path(storage_dir / "ai_config.json")

    def go_login(_: ft.ControlEvent | None = None) -> None:
        page.bgcolor = ShellColors.canvas
        # Login paints its own full-bleed background + inner SafeArea for content.
        mount(page, build_login(page, on_success=go_shell, on_register=go_register), safe=False)

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

    go_splash()


def run() -> None:
    ft.run(main, assets_dir=str(_asset_root() / "assets"))


if __name__ == "__main__":
    run()
