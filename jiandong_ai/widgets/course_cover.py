"""Course cover photo + placeholder (Flet port of Flutter CourseCover)."""

from __future__ import annotations

from pathlib import Path

import flet as ft

from jiandong_ai.app.theme import HUD_CANVAS, ShellColors


def asset_src(path: str | None) -> str | None:
    """Normalize asset paths for Flet assets_dir (strip leading assets/)."""
    if not path:
        return None
    p = path.replace("\\", "/").lstrip("/")
    if p.startswith("assets/"):
        p = p[len("assets/") :]
    return p


class CourseCoverCatalog:
    _DIR = "assets/images/courses"

    c001 = f"{_DIR}/c_001.png"
    c002 = f"{_DIR}/c_002.png"
    c003 = f"{_DIR}/c_003.png"
    c004 = f"{_DIR}/c_004.png"
    c005 = f"{_DIR}/c_005.png"
    featured_squat = f"{_DIR}/featured_squat.png"
    featured_hiit = f"{_DIR}/featured_hiit.png"
    featured_yoga = f"{_DIR}/featured_yoga.png"

    PRE_MATTED = {
        c001,
        c002,
        c003,
        c004,
        c005,
        featured_squat,
        featured_hiit,
        featured_yoga,
    }

    @classmethod
    def is_pre_matted(cls, asset: str) -> bool:
        return asset in cls.PRE_MATTED

    @classmethod
    def asset_for(cls, exercise) -> str | None:
        explicit = getattr(exercise, "cover_asset", None)
        if explicit:
            return explicit
        return cls.asset_for_seed(
            id_=getattr(exercise, "id", "") or "",
            name=getattr(exercise, "name", "") or "",
            category=getattr(exercise, "category", "") or "",
        )

    @classmethod
    def asset_for_seed(cls, *, id_: str = "", name: str = "", category: str = "") -> str | None:
        by_id = {
            "c_001": cls.c001,
            "c_002": cls.c002,
            "c_003": cls.c003,
            "c_004": cls.c004,
            "c_005": cls.c005,
            "w_001": cls.featured_hiit,
            "w_002": cls.featured_squat,
            "w_003": cls.featured_yoga,
        }
        if id_ in by_id:
            return by_id[id_]
        n = name.lower()
        if "hiit" in n or "燃脂" in name or "有氧" in name:
            return cls.featured_hiit
        if "深蹲" in name or "下肢" in name or "squat" in n:
            return cls.featured_squat
        if "瑜伽" in name or "拉伸" in name or "yoga" in n:
            return cls.featured_yoga
        if category in {"上肢"}:
            return cls.c002
        if category in {"下肢"}:
            return cls.c001
        if category in {"核心"}:
            return cls.c003
        if category in {"拉伸"}:
            return cls.c005
        return cls.c004


def cover_placeholder(*, height: float | None = None, expand: bool = False) -> ft.Control:
    sc = ShellColors
    return ft.Container(
        height=height,
        expand=expand,
        bgcolor=sc.surface_muted,
        alignment=ft.Alignment.CENTER,
        content=ft.Icon(ft.Icons.FITNESS_CENTER, size=32, color=sc.accent),
    )


def course_cover(
    *,
    exercise=None,
    asset_path: str | None = None,
    height: float | None = None,
    border_radius: float | None = None,
    show_bottom_fade: bool = False,
    apply_matte_overlay: bool = True,
) -> ft.Control:
    asset = asset_path
    if asset is None and exercise is not None:
        asset = CourseCoverCatalog.asset_for(exercise)
    src = asset_src(asset)
    overlay = (
        apply_matte_overlay
        and asset is not None
        and not CourseCoverCatalog.is_pre_matted(asset)
    )

    layers: list[ft.Control] = [
        ft.Container(expand=True, bgcolor=ShellColors.surface_muted),
    ]
    if src:
        layers.append(
            ft.Image(
                src=src,
                fit=ft.BoxFit.COVER,
                expand=True,
                error_content=cover_placeholder(expand=True),
            )
        )
    else:
        layers.append(cover_placeholder(expand=True))

    if overlay:
        layers.append(ft.Container(expand=True, bgcolor=f"{HUD_CANVAS}7A"))

    if show_bottom_fade:
        layers.append(
            ft.Container(
                expand=True,
                gradient=ft.LinearGradient(
                    begin=ft.Alignment.TOP_CENTER,
                    end=ft.Alignment.BOTTOM_CENTER,
                    colors=["#00000000", "#E6070A0F"],
                ),
            )
        )

    stack = ft.Stack(layers, expand=True)
    return ft.Container(
        height=height,
        border_radius=border_radius,
        clip_behavior=ft.ClipBehavior.HARD_EDGE if border_radius else None,
        content=stack,
    )


def action_thumb(name: str, *, size: float = 56) -> ft.Control:
    from jiandong_ai.services.action_guide_catalog import ActionGuideCatalog

    guide = ActionGuideCatalog.for_name(name)
    src = asset_src(guide.image_asset)
    return ft.Container(
        width=size,
        height=size,
        border_radius=12,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        bgcolor=ShellColors.surface_muted,
        content=ft.Image(
            src=src or "",
            fit=ft.BoxFit.COVER,
            width=size,
            height=size,
            error_content=ft.Container(
                width=size,
                height=size,
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(ft.Icons.FITNESS_CENTER, size=22, color=ShellColors.accent),
            ),
        ),
    )


def resolve_asset_file(rel: str) -> Path:
    root = Path(__file__).resolve().parents[2] / "assets"
    src = asset_src(rel) or rel
    return root / src
