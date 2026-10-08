"""Full-page plan editor — Flutter PlanEditorPage parity (two-zone drag/reorder)."""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from jiandong_ai.app.back_navigation import register_plan_editor, unregister_plan_editor
from jiandong_ai.app.theme import SHELL_RADIUS_BTN, SHELL_RADIUS_CARD, ShellColors
from jiandong_ai.services.action_guide_catalog import ActionGuideCatalog
from jiandong_ai.services.mock_service import MockService
from jiandong_ai.widgets.course_cover import action_thumb
from jiandong_ai.widgets.matte_card import matte_card
from jiandong_ai.widgets.motion import DRAG_LIFT_SCALE, STANDARD_MS, reduce_motion
from jiandong_ai.widgets.safe_area import safe_area

_GROUP_LIB = "plan_lib"
_GROUP_REMOVE = "plan_remove"


@dataclass
class DraftSlot:
    id: int
    name: str


def reorder_draft(draft: list[DraftSlot], old_index: int, new_index: int) -> list[DraftSlot]:
    """Pure reorder helper (Flutter ReorderableListView index adjust)."""
    if old_index < 0 or old_index >= len(draft):
        return list(draft)
    out = list(draft)
    if new_index > old_index:
        new_index -= 1
    new_index = max(0, min(new_index, len(out)))
    item = out.pop(old_index)
    out.insert(new_index, item)
    return out


def _chip(name: str, *, selected: bool, on_click=None) -> ft.Control:
    sc = ShellColors
    return ft.Container(
        bgcolor=sc.accent_soft if selected else sc.surface,
        border=ft.Border.all(1, sc.accent if selected else sc.border),
        border_radius=20,
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        on_click=on_click,
        content=ft.Row(
            [
                action_thumb(name, size=36),
                ft.Text(
                    name,
                    color=sc.accent if selected else sc.text,
                    weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_500,
                    size=14,
                ),
            ],
            spacing=10,
            tight=True,
        ),
    )


class PlanEditorView(ft.Container):
    """Fullscreen editor: plan zone + library zone."""

    def __init__(
        self,
        page: ft.Page,
        *,
        on_close,
        on_saved,
        on_start_training=None,
    ) -> None:
        super().__init__(expand=True, bgcolor=ShellColors.canvas, padding=0)
        self._host = page
        self.on_close = on_close
        self.on_saved = on_saved
        self.on_start_training = on_start_training
        self._svc = MockService.instance()
        self._next_id = 0
        self._draft: list[DraftSlot] = [
            self._new_slot(n) for n in self._svc.get_today_plan_actions()
        ]
        self._plan_highlight = False
        self._lib_highlight = False
        self._plan_box: ft.Container | None = None
        self._lib_box: ft.Container | None = None

        self._save_btn = ft.TextButton(
            "保存",
            style=ft.ButtonStyle(color=ShellColors.accent),
        )
        # Flutter PrimaryButton / SecondaryButton parity (h=52, radiusBtn=14).
        self._save_start_btn = ft.FilledButton(
            "保存并开始训练",
            height=52,
            style=ft.ButtonStyle(
                bgcolor=ShellColors.accent,
                color=ShellColors.on_cta,
                text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_600),
                shape=ft.RoundedRectangleBorder(radius=SHELL_RADIUS_BTN),
                padding=ft.Padding.symmetric(horizontal=16),
            ),
        )
        self._save_bottom = ft.OutlinedButton(
            "仅保存",
            height=52,
            style=ft.ButtonStyle(
                color=ShellColors.accent_dark,
                bgcolor=ft.Colors.TRANSPARENT,
                side=ft.BorderSide(1, ShellColors.accent),
                text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_600),
                shape=ft.RoundedRectangleBorder(radius=SHELL_RADIUS_BTN),
                padding=ft.Padding.symmetric(horizontal=16),
            ),
        )
        self._body = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.AUTO)
        self.content = ft.Column(
            [
                self._build_app_bar(),
                ft.Container(content=self._body, expand=True, padding=0),
                self._build_bottom_bar(),
            ],
            spacing=0,
            expand=True,
        )
        self._wire_actions()
        self._rebuild()

    def _new_slot(self, name: str) -> DraftSlot:
        slot = DraftSlot(id=self._next_id, name=name)
        self._next_id += 1
        return slot

    def _names(self) -> list[str]:
        return [s.name for s in self._draft]

    def _empty(self) -> bool:
        return len(self._draft) == 0

    def _wire_actions(self) -> None:
        self._save_btn.on_click = lambda e: self._save(close=True)
        self._save_bottom.on_click = lambda e: self._save(close=True)
        self._save_start_btn.on_click = lambda e: self._save_and_start()

    def _build_app_bar(self) -> ft.Control:
        sc = ShellColors
        return ft.Container(
            bgcolor=sc.canvas,
            padding=ft.Padding.symmetric(horizontal=8, vertical=8),
            border=ft.Border.only(bottom=ft.BorderSide(1, sc.divider)),
            content=ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        icon_color=sc.text,
                        on_click=lambda e: self.on_close(),
                    ),
                    ft.Text(
                        "编辑今日计划",
                        size=18,
                        weight=ft.FontWeight.W_700,
                        color=sc.text,
                        expand=True,
                    ),
                    self._save_btn,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _build_bottom_bar(self) -> ft.Control:
        # Single MatteCard foot — no canvas strip + hairline + nested card.
        return matte_card(
            ft.Column(
                [self._save_start_btn, self._save_bottom],
                spacing=8,
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=ft.Padding.only(left=20, top=12, right=20, bottom=20),
        )

    def _sync_buttons(self) -> None:
        sc = ShellColors
        empty = self._empty()
        self._save_btn.disabled = empty
        self._save_btn.style = ft.ButtonStyle(
            color=sc.text_tertiary if empty else sc.accent,
        )
        self._save_start_btn.disabled = empty
        self._save_start_btn.style = ft.ButtonStyle(
            bgcolor=sc.surface_muted if empty else sc.accent,
            color=sc.text_tertiary if empty else sc.on_cta,
            text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_600),
            shape=ft.RoundedRectangleBorder(radius=SHELL_RADIUS_BTN),
            padding=ft.Padding.symmetric(horizontal=16),
        )
        self._save_bottom.disabled = empty
        self._save_bottom.style = ft.ButtonStyle(
            color=sc.text_tertiary if empty else sc.accent_dark,
            bgcolor=ft.Colors.TRANSPARENT,
            side=ft.BorderSide(1, sc.border if empty else sc.accent),
            text_style=ft.TextStyle(size=15, weight=ft.FontWeight.W_600),
            shape=ft.RoundedRectangleBorder(radius=SHELL_RADIUS_BTN),
            padding=ft.Padding.symmetric(horizontal=16),
        )

    def _rebuild(self) -> None:
        sc = ShellColors
        self._sync_buttons()
        self._body.controls = [
            ft.Container(
                padding=ft.Padding.only(left=20, top=12, right=20, bottom=20),
                content=ft.Column(
                    [
                        ft.Text("今日计划", size=16, weight=ft.FontWeight.W_700, color=sc.text),
                        ft.Container(height=6),
                        ft.Text(
                            "左侧手柄排序；长按卡片拖到下方可移出",
                            size=13,
                            color=sc.text_tertiary,
                        ),
                        ft.Container(height=12),
                        self._plan_zone(),
                        ft.Container(height=28),
                        ft.Text("动作素材库", size=16, weight=ft.FontWeight.W_700, color=sc.text),
                        ft.Container(height=6),
                        ft.Text(
                            "点击或拖到上方加入计划（可重复）",
                            size=13,
                            color=sc.text_tertiary,
                        ),
                        ft.Container(height=12),
                        self._library_zone(),
                    ],
                    spacing=0,
                    tight=True,
                ),
            )
        ]
        try:
            self.update()
        except Exception:
            pass

    def _plan_zone(self) -> ft.Control:
        sc = ShellColors
        highlight = self._plan_highlight
        if not self._draft:
            inner: ft.Control = ft.Container(
                height=160,
                alignment=ft.Alignment.CENTER,
                content=ft.Text("把动作拖到上面", size=14, color=sc.text_tertiary),
            )
        else:
            items: list[ft.Control] = []
            for i, slot in enumerate(self._draft):
                items.append(self._plan_row(i, slot))
            list_h = min(56 * len(items) + 8, 320)
            inner = ft.ReorderableListView(
                controls=items,
                show_default_drag_handles=False,
                height=list_h,
                on_reorder=self._on_reorder,
            )

        self._plan_box = ft.Container(
            padding=12,
            border_radius=SHELL_RADIUS_CARD,
            bgcolor=sc.accent_soft if highlight else sc.surface_muted,
            border=ft.Border.all(1, sc.accent if highlight else sc.border),
            animate=ft.Animation(
                0 if reduce_motion(self._host) else STANDARD_MS,
                ft.AnimationCurve.EASE_OUT_CUBIC,
            ),
            content=inner,
        )
        return ft.DragTarget(
            group=_GROUP_LIB,
            content=self._plan_box,
            on_will_accept=self._on_plan_will_accept,
            on_leave=self._on_plan_leave,
            on_accept=self._on_plan_accept,
        )

    def _plan_row(self, index: int, slot: DraftSlot) -> ft.Control:
        sc = ShellColors
        chip = _chip(slot.name, selected=True)
        drag = ft.Draggable(
            group=_GROUP_REMOVE,
            content=chip,
            content_when_dragging=ft.Container(
                opacity=0.35,
                content=_chip(slot.name, selected=True),
            ),
            content_feedback=ft.Container(
                scale=DRAG_LIFT_SCALE,
                content=_chip(slot.name, selected=True),
            ),
            data={"kind": "plan", "index": index, "name": slot.name},
        )

        return ft.Container(
            key=f"plan-{slot.id}",
            padding=ft.Padding.symmetric(vertical=4),
            content=ft.Row(
                [
                    ft.ReorderableDragHandle(
                        content=ft.Icon(ft.Icons.DRAG_HANDLE, color=sc.text_tertiary),
                        mouse_cursor=ft.MouseCursor.GRAB,
                    ),
                    ft.Container(content=drag, expand=True),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _library_zone(self) -> ft.Control:
        sc = ShellColors
        highlight = self._lib_highlight
        chips: list[ft.Control] = []
        for name in ActionGuideCatalog.known_names():
            chip = _chip(name, selected=False, on_click=lambda e, n=name: self._add(n))
            drag = ft.Draggable(
                group=_GROUP_LIB,
                content=chip,
                content_feedback=ft.Container(
                    scale=DRAG_LIFT_SCALE,
                    content=_chip(name, selected=False),
                ),
                data={"kind": "library", "name": name},
            )
            chips.append(drag)

        wrap = ft.Row(chips, wrap=True, spacing=8, run_spacing=8)
        self._lib_box = ft.Container(
            padding=12,
            border_radius=SHELL_RADIUS_CARD,
            bgcolor=sc.accent_soft if highlight else sc.surface,
            border=ft.Border.all(1, sc.accent if highlight else sc.border),
            animate=ft.Animation(
                0 if reduce_motion(self._host) else STANDARD_MS,
                ft.AnimationCurve.EASE_OUT_CUBIC,
            ),
            content=wrap,
        )
        return ft.DragTarget(
            group=_GROUP_REMOVE,
            content=self._lib_box,
            on_will_accept=self._on_lib_will_accept,
            on_leave=self._on_lib_leave,
            on_accept=self._on_lib_accept,
        )

    def _add(self, name: str) -> None:
        self._draft.append(self._new_slot(name))
        self._rebuild()

    def _remove_at(self, index: int) -> None:
        if 0 <= index < len(self._draft):
            self._draft.pop(index)
            self._rebuild()

    def _on_reorder(self, e: ft.ControlEvent) -> None:
        old_i = getattr(e, "old_index", None)
        new_i = getattr(e, "new_index", None)
        if old_i is None or new_i is None:
            return
        self._draft = reorder_draft(self._draft, int(old_i), int(new_i))
        self._rebuild()

    def _payload(self, e) -> dict | None:
        src = getattr(e, "src", None)
        if src is None:
            return None
        data = getattr(src, "data", None)
        return data if isinstance(data, dict) else None

    def _paint_plan_highlight(self, on: bool) -> None:
        self._plan_highlight = on
        if self._plan_box is None:
            return
        sc = ShellColors
        self._plan_box.bgcolor = sc.accent_soft if on else sc.surface_muted
        self._plan_box.border = ft.Border.all(1, sc.accent if on else sc.border)
        try:
            self._plan_box.update()
        except Exception:
            pass

    def _paint_lib_highlight(self, on: bool) -> None:
        self._lib_highlight = on
        if self._lib_box is None:
            return
        sc = ShellColors
        self._lib_box.bgcolor = sc.accent_soft if on else sc.surface
        self._lib_box.border = ft.Border.all(1, sc.accent if on else sc.border)
        try:
            self._lib_box.update()
        except Exception:
            pass

    def _on_plan_will_accept(self, e) -> None:
        self._paint_plan_highlight(True)

    def _on_plan_leave(self, e) -> None:
        self._paint_plan_highlight(False)

    def _on_plan_accept(self, e) -> None:
        self._paint_plan_highlight(False)
        data = self._payload(e)
        if data and data.get("kind") == "library":
            self._add(str(data["name"]))

    def _on_lib_will_accept(self, e) -> None:
        self._paint_lib_highlight(True)

    def _on_lib_leave(self, e) -> None:
        self._paint_lib_highlight(False)

    def _on_lib_accept(self, e) -> None:
        self._paint_lib_highlight(False)
        data = self._payload(e)
        if data and data.get("kind") == "plan":
            self._remove_at(int(data["index"]))

    def _save(self, *, close: bool) -> bool:
        if self._empty():
            return False
        self._svc.set_today_plan_actions(self._names())
        if self.on_saved:
            self.on_saved()
        if close:
            self.on_close()
        return True

    def _save_and_start(self) -> None:
        if self._empty():
            return
        names = self._names()
        self._svc.set_today_plan_actions(names)
        if self.on_saved:
            self.on_saved()
        self.on_close()
        if self.on_start_training:
            self.on_start_training(actions=names, session_title="今日计划")


def open_plan_editor(
    page: ft.Page,
    *,
    on_saved,
    on_start_training=None,
) -> None:
    """Show fullscreen plan editor over the shell (not a dialog)."""

    holder: dict[str, ft.Container | None] = {"overlay": None}

    def close() -> None:
        unregister_plan_editor()
        ov = holder["overlay"]
        if ov is not None and ov in page.overlay:
            page.overlay.remove(ov)
            page.update()
        holder["overlay"] = None

    w = float(page.width or 420)
    h = float(page.height or 860)
    editor = PlanEditorView(
        page,
        on_close=close,
        on_saved=on_saved,
        on_start_training=on_start_training,
    )
    overlay = ft.Container(
        left=0,
        top=0,
        width=w,
        height=h,
        bgcolor=ShellColors.canvas,
        content=safe_area(editor),
    )
    holder["overlay"] = overlay
    register_plan_editor(close)
    page.overlay.append(overlay)
    page.update()
