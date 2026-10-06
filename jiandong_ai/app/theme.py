from __future__ import annotations

# ---- HUD / camera (dark glass coaching) ----
HUD_CANVAS = "#070A0F"
HUD_SURFACE = "#0E141C"
HUD_SURFACE_MUTED = "#151C26"
HUD_GLASS_FILL = "#1218208C"
HUD_GLASS_STROKE = "#FFFFFF1F"
HUD_CYAN = "#5CE1E6"
HUD_GREEN = "#5ED662"
HUD_CORAL = "#E8917A"
HUD_RECORD_RED = "#FF3B30"
HUD_TIP_AMBER_BG = "#4A3B2BBF"
HUD_TIP_AMBER_TEXT = "#FFD08A"
HUD_METRIC_BLUE = "#5B8CFF"
HUD_METRIC_PURPLE = "#B07CFF"
HUD_METRIC_ORANGE = "#FF9F43"
HUD_TEXT = "#FFFFFF"
HUD_TEXT_SECONDARY = "#A8B0BC"
HUD_TEXT_TERTIARY = "#6B7380"
HUD_DIVIDER = "#FFFFFF14"
HUD_RADIUS_BTN = 14

# ---- Light catalog shell ----
SHELL_CANVAS = "#F4F5F7"
SHELL_SURFACE = "#FFFFFF"
SHELL_SURFACE_MUTED = "#EEF0F3"
SHELL_BORDER = "#E8EAEE"
SHELL_DIVIDER = "#E5E7EB"
SHELL_TEXT = "#0F1115"
SHELL_TEXT_SECONDARY = "#6B7280"
SHELL_TEXT_TERTIARY = "#9CA3AF"
SHELL_ACCENT = "#24C789"
SHELL_ACCENT_DARK = "#1BA873"
SHELL_ACCENT_SOFT = "#E6F9F2"
SHELL_CALORIE = "#FF7A45"
SHELL_DANGER = "#DC2626"
SHELL_ON_CTA = "#FFFFFF"
SHELL_RADIUS_CARD = 16
SHELL_RADIUS_BTN = 14


def glass_container(*, content, padding=None, border_radius: float = 999, expand: bool = False):
    import flet as ft

    return ft.Container(
        content=content,
        padding=padding if padding is not None else ft.Padding.symmetric(horizontal=12, vertical=8),
        border_radius=border_radius,
        bgcolor=HUD_GLASS_FILL,
        border=ft.Border.all(1, HUD_GLASS_STROKE),
        expand=expand,
    )
