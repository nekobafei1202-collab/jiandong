from __future__ import annotations

from datetime import datetime

from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.ai.session.course_action_queue import CourseActionQueue
from jiandong_ai.models import RecordAction, TrainingRecord
from jiandong_ai.services.mock_service import MockService


def test_guide_only_detection():
    assert ExerciseKind.is_guide_only("热身")
    assert ExerciseKind.is_guide_only("拉伸")
    assert ExerciseKind.is_manual_complete("热身")
    assert not ExerciseKind.supports_auto_detect("热身")
    assert not ExerciseKind.is_guide_only("深蹲")
    assert not ExerciseKind.is_guide_only("开合跳")


def test_queue_aggregates_multi_action_and_skips_guide():
    q = CourseActionQueue(["热身", "深蹲", "俯卧撑", "拉伸"])
    assert q.complete_current_and_advance(reps=0, avg_score=None, manual=True)
    assert q.complete_current_and_advance(reps=10, avg_score=88, manual=False)
    assert q.complete_current_and_advance(reps=8, avg_score=76, manual=False)
    assert not q.complete_current_and_advance(reps=0, avg_score=None, manual=True)

    assert q.completed_count == 4
    assert q.total_reps == 18
    assert q.average_score == 82
    assert [c.action_name for c in q.completed] == ["热身", "深蹲", "俯卧撑", "拉伸"]


def test_early_stop_records_partial_current():
    q = CourseActionQueue(["深蹲", "俯卧撑"])
    q.complete_current_and_advance(reps=10, avg_score=90, manual=False)
    q.record_current_only(reps=3, avg_score=70, manual=False)
    assert q.completed_count == 2
    assert q.total_reps == 13
    assert q.average_score == 80


def test_history_starts_empty_and_today_uses_calories(tmp_path):
    MockService._instance = None
    svc = MockService.instance()
    svc.init(tmp_path)
    assert svc.get_training_history() == []

    today = datetime.now().isoformat()
    svc.add_training_record(
        TrainingRecord(
            id="r_live",
            exercise_name="下肢力量训练",
            duration=2,
            score=85,
            date=today,
            calories=48,
            total_reps=18,
            actions=(
                RecordAction(action_name="热身", reps=0),
                RecordAction(action_name="深蹲", reps=10, avg_score=88),
                RecordAction(action_name="俯卧撑", reps=8, avg_score=82),
            ),
        )
    )
    stats = svc.get_today_stats()
    assert stats["durationMinutes"] == 2
    assert stats["todayCalories"] == 48
    assert stats["sessionCount"] == 1
    hist = svc.get_training_history()
    assert len(hist) == 1
    assert hist[0].exercise_name == "下肢力量训练"
    assert len(hist[0].actions) == 3
