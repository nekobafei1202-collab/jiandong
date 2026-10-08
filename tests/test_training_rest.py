from __future__ import annotations

from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.pages.training import training_page as tp


def test_rest_seconds_by_kind():
    assert ExerciseKind.rest_seconds("热身") == 0
    assert ExerciseKind.rest_seconds("拉伸") == 0
    assert ExerciseKind.rest_seconds("warmup") == 0
    assert ExerciseKind.rest_seconds("开合跳") == 30
    assert ExerciseKind.rest_seconds("jumping_jack") == 30
    assert ExerciseKind.rest_seconds("高抬腿") == 30
    assert ExerciseKind.rest_seconds("平板支撑") == 45
    assert ExerciseKind.rest_seconds("plank") == 45
    assert ExerciseKind.rest_seconds("深蹲") == 60
    assert ExerciseKind.rest_seconds("俯卧撑") == 60
    assert ExerciseKind.rest_seconds("弓步蹲") == 60
    assert ExerciseKind.rest_seconds("臀桥") == 60
    assert ExerciseKind.rest_seconds("卷腹") == 60


def test_plan_rest_between_sets():
    planned = tp.plan_rest_after_set(
        action_name="深蹲",
        set_index=1,
        next_action="俯卧撑",
    )
    assert planned == ("next_set", 60)

    cardio = tp.plan_rest_after_set(
        action_name="开合跳",
        set_index=3,
        next_action="深蹲",
    )
    assert cardio == ("next_set", 30)


def test_plan_rest_between_actions():
    planned = tp.plan_rest_after_set(
        action_name="深蹲",
        set_index=4,
        next_action="俯卧撑",
    )
    assert planned == ("advance", 60)

    plank = tp.plan_rest_after_set(
        action_name="平板支撑",
        set_index=4,
        next_action="开合跳",
    )
    assert plank == ("advance", 45)


def test_plan_rest_skips_guide_bookends():
    assert (
        tp.plan_rest_after_set(
            action_name="热身",
            set_index=1,
            next_action="深蹲",
        )
        is None
    )
    assert (
        tp.plan_rest_after_set(
            action_name="深蹲",
            set_index=4,
            next_action="拉伸",
        )
        is None
    )
    assert (
        tp.plan_rest_after_set(
            action_name="深蹲",
            set_index=4,
            next_action=None,
        )
        is None
    )


def test_rest_hud_helpers_smoke():
    from jiandong_ai.widgets.training_hud import build_rest_countdown

    ctrl = build_rest_countdown(seconds=45, label="组间休息")
    assert ctrl is not None
    assert tp._LABEL_SKIP_REST == "跳过休息"
    assert tp._REST_LABEL_SET == "组间休息"
    assert tp._REST_LABEL_ACTION == "动作切换"
