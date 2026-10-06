from __future__ import annotations

from jiandong_ai.services.mock_service import MockService
from jiandong_ai.models import TrainingRecord


def test_mock_service_plan_persist(tmp_path):
    MockService._instance = None
    svc = MockService.instance()
    svc.init(tmp_path)
    svc.set_today_plan_actions(["深蹲", "俯卧撑"])
    assert svc.get_today_plan_actions() == ["深蹲", "俯卧撑"]
    svc.mark_plan_done("深蹲")
    plan = svc.get_today_plan()
    assert plan[0] == ("深蹲", True)
    assert plan[1] == ("俯卧撑", False)

    # reload
    MockService._instance = None
    svc2 = MockService.instance()
    svc2.init(tmp_path)
    assert svc2.get_today_plan_actions() == ["深蹲", "俯卧撑"]
    assert svc2.get_today_plan()[0][1] is True


def test_add_history(tmp_path):
    MockService._instance = None
    svc = MockService.instance()
    svc.init(tmp_path)
    before = len(svc.get_training_history())
    svc.add_training_record(
        TrainingRecord(
            id="t1",
            exercise_name="深蹲",
            duration=5,
            score=90,
            date="2026-01-01T10:00:00",
            total_reps=12,
        )
    )
    assert len(svc.get_training_history()) == before + 1
    assert svc.get_training_history()[0].exercise_name == "深蹲"
