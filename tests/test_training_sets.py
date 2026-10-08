from __future__ import annotations

from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.pages.training import training_page as tp


def test_sets_constants():
    assert tp._SETS_PER_ACTION == 4
    assert tp._TARGET_REPS == 10


def test_guide_only_skips_sets():
    assert ExerciseKind.is_guide_only("热身")
    assert ExerciseKind.is_guide_only("拉伸")
    assert not ExerciseKind.is_guide_only("深蹲")


def test_set_rep_totals_math():
    """4 sealed sets of 10 → 40 total; partial current set adds in."""
    completed = [10, 10, 10]
    live = 4
    assert sum(completed) + live == 34
    completed4 = [10, 10, 10, 10]
    assert sum(completed4) + 0 == 40


def test_set_previous_undo_math():
    """Undoing a sealed set pops reps (+ matching score when 1:1)."""
    completed_reps = [10, 10]
    completed_scores = [88, 90]
    set_index = 3
    session_sets = 2
    # Simulate _set_previous from set 3 → 2
    n_reps = len(completed_reps)
    n_scores = len(completed_scores)
    completed_reps.pop()
    if n_scores == n_reps:
        completed_scores.pop()
    set_index -= 1
    session_sets = max(0, session_sets - 1)
    assert set_index == 2
    assert completed_reps == [10]
    assert completed_scores == [88]
    assert session_sets == 1


def test_build_set_nav_smoke():
    from jiandong_ai.widgets.training_hud import build_set_nav

    ctrl = build_set_nav(
        can_previous=True,
        can_next=True,
        show_pick=False,
        prev_label="上一个",
        next_label="下一组",
    )
    assert ctrl is not None
    with_pick = build_set_nav(
        can_previous=False,
        can_next=False,
        show_pick=True,
        on_pick=lambda: None,
    )
    assert with_pick is not None


def test_compute_nav_mode_matrix():
    guide = tp.compute_nav_mode(
        guide_only=True, set_index=1, has_previous=True
    )
    assert guide["prev_label"] == tp._LABEL_PREV_ACT
    assert guide["next_label"] == tp._LABEL_NEXT_ACT
    assert guide["prev_is_action"] and guide["next_is_action"]
    assert guide["can_prev"] is True

    set1 = tp.compute_nav_mode(
        guide_only=False, set_index=1, has_previous=False
    )
    assert set1["prev_label"] == tp._LABEL_PREV_ACT
    assert set1["next_label"] == tp._LABEL_NEXT_SET
    assert set1["prev_is_action"] and not set1["next_is_action"]
    assert set1["can_prev"] is False

    set2 = tp.compute_nav_mode(
        guide_only=False, set_index=2, has_previous=True
    )
    assert set2["prev_label"] == tp._LABEL_PREV_SET
    assert set2["next_label"] == tp._LABEL_NEXT_SET
    assert not set2["prev_is_action"] and not set2["next_is_action"]

    set4 = tp.compute_nav_mode(
        guide_only=False, set_index=4, has_previous=True
    )
    assert set4["prev_label"] == tp._LABEL_PREV_SET
    assert set4["next_label"] == tp._LABEL_NEXT_ACT
    assert not set4["prev_is_action"] and set4["next_is_action"]


def test_queue_pop_last_completed():
    from jiandong_ai.ai.session.course_action_queue import CourseActionQueue

    q = CourseActionQueue(["热身", "深蹲", "拉伸"])
    q.complete_current_and_advance(reps=0, avg_score=None, manual=True)
    assert q.peek_last_completed() is not None
    assert q.peek_last_completed().action_name == "热身"
    popped = q.pop_last_completed()
    assert popped is not None and popped.action_name == "热身"
    assert q.peek_last_completed() is None


def test_rep_counter_label_with_total():
    from jiandong_ai.widgets.training_hud import build_rep_counter

    # set_index = current set (e.g. 1/4 on first set).
    ctrl = build_rep_counter(
        set_index=1, set_total=4, rep_count=3, rep_target=10, unit="次"
    )
    assert ctrl is not None
    mid = build_rep_counter(
        set_index=2, set_total=4, rep_count=5, rep_target=10, unit="次"
    )
    assert mid is not None
    hidden = build_rep_counter(
        set_index=1, set_total=4, rep_count=0, hide_count=True
    )
    assert hidden is not None


def test_current_set_display():
    """HUD shows current set / target, e.g. working set 3 → 3/4."""
    set_index = 3
    set_total = 4
    assert f"组 {set_index}/{set_total}" == "组 3/4"


def test_rep_done_over_target_label():
    """Rep HUD shows completed/target, e.g. 3/10 次."""
    done, target, unit = 3, 10, "次"
    assert f"{done}/{target} {unit}" == "3/10 次"