"""Plan editor helpers and catalog coverage."""

from __future__ import annotations

from jiandong_ai.pages.home.plan_editor_page import DraftSlot, reorder_draft
from jiandong_ai.services.action_guide_catalog import ActionGuideCatalog


def test_known_names_non_empty_sorted() -> None:
    names = ActionGuideCatalog.known_names()
    assert len(names) >= 9
    assert names == sorted(names)
    assert "深蹲" in names


def test_reorder_draft_moves_item() -> None:
    draft = [DraftSlot(0, "a"), DraftSlot(1, "b"), DraftSlot(2, "c")]
    out = reorder_draft(draft, 0, 2)
    assert [s.name for s in out] == ["b", "a", "c"]
    # original untouched
    assert [s.name for s in draft] == ["a", "b", "c"]


def test_reorder_draft_adjusts_new_index() -> None:
    draft = [DraftSlot(0, "a"), DraftSlot(1, "b"), DraftSlot(2, "c")]
    out = reorder_draft(draft, 0, 3)
    assert [s.name for s in out] == ["b", "c", "a"]
