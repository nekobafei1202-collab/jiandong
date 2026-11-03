from __future__ import annotations

from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.services.body_part_recommender import (
    BodyPartRecommender,
    resolve_part,
)
from jiandong_ai.widgets.muscle_map import action_muscle_map


def test_resolve_part_aliases():
    assert resolve_part("腿部") == "leg"
    assert resolve_part("腿") == "leg"
    assert resolve_part("下肢") == "leg"
    assert resolve_part("核心") == "core"
    assert resolve_part("腹部") == "core"
    assert resolve_part("腰腹") == "core"
    assert resolve_part("上肢") == "upper"
    assert resolve_part("胸") == "upper"
    assert resolve_part("手臂") == "upper"
    assert resolve_part("背") == "back"
    assert resolve_part("背部") == "back"
    assert resolve_part("全身") == "full"
    assert resolve_part("今天天气不错") is None
    assert resolve_part("") is None


def test_recommend_structure_and_bookends():
    rec = BodyPartRecommender()
    actions = rec.recommend("leg")
    assert actions[0] == "热身"
    assert actions[-1] == "拉伸"
    core = actions[1:-1]
    assert 3 <= len(core) <= 4
    assert len(set(core)) == len(core)  # 去重
    # 腿部首选应包含深蹲（QUADS 强度 3）。
    assert "深蹲" in core
    for name in core:
        assert ExerciseKind.supports_auto_detect(name)


def test_recommend_respects_part_groups():
    rec = BodyPartRecommender()
    core_actions = rec.recommend("core")[1:-1]
    table = action_muscle_map()
    for name in core_actions:
        # 找到动作 key，核对它确实锻炼核心肌群。
        key = next(
            k for k in table if ExerciseKind.display_name(k) == name
        )
        assert any(g in table[key] for g in ("CORE", "OBLIQUES"))
    assert "平板支撑" in core_actions


def test_reroll_rotates_without_repeats():
    rec = BodyPartRecommender(pick_count=2)
    first = rec.recommend("core")
    seen = {tuple(first)}
    for _ in range(3):
        nxt = rec.reroll()
        assert nxt[0] == "热身" and nxt[-1] == "拉伸"
        assert len(nxt) == len(first)
        # 每次「换一个」都应有变化（候选耗尽前）。
        assert tuple(nxt) not in seen
        seen.add(tuple(nxt))
    # 已拒绝项被记录。
    assert rec.rejected


def test_reroll_without_recommend_is_empty():
    assert BodyPartRecommender().reroll() == []


def test_unknown_part_returns_empty():
    assert BodyPartRecommender().recommend("unknown") == []
