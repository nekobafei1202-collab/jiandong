from __future__ import annotations

from jiandong_ai.models import RecordAction, TrainingRecord
from jiandong_ai.services.mock_service import MockService
from jiandong_ai.widgets.muscle_map import activation_for_actions, render_muscle_svg
from jiandong_ai.widgets.training_hud import build_session_summary_text, posture_encouragement


def _record(id_: str, name: str = "深蹲") -> TrainingRecord:
    return TrainingRecord(
        id=id_,
        exercise_name=name,
        duration=10,
        score=80,
        date="2026-10-09T18:32:00",
        calories=100,
        total_reps=40,
        actions=(RecordAction(action_name="深蹲", reps=40, avg_score=80),),
    )


def test_delete_training_record_removes_and_saves(tmp_path) -> None:
    svc = MockService()
    svc.init(tmp_path)
    svc.add_training_record(_record("r_1"))
    svc.add_training_record(_record("r_2"))
    assert svc.delete_training_record("r_1") is True
    remaining = [r.id for r in svc.get_training_history()]
    assert remaining == ["r_2"]
    svc2 = MockService()
    svc2.init(tmp_path)
    assert [r.id for r in svc2.get_training_history()] == ["r_2"]


def test_delete_training_record_missing_id() -> None:
    svc = MockService()
    assert svc.delete_training_record("nope") is False


def test_session_summary_praises_best_and_flags_worst() -> None:
    text = build_session_summary_text(
        [
            {"name": "深蹲", "reps": 40, "avg_score": 92},
            {"name": "俯卧撑", "reps": 30, "avg_score": 65},
        ]
    )
    assert "深蹲" in text and "俯卧撑" in text
    assert "70" in text
    assert "表扬" in text and "下次重点" in text
    assert "92%" in text and "65%" in text


def test_session_summary_no_scores_generic() -> None:
    text = build_session_summary_text([{"name": "开合跳", "reps": 60, "avg_score": None}])
    assert "开合跳" in text
    assert "表扬" not in text


def test_session_summary_empty() -> None:
    assert build_session_summary_text([])


def test_posture_encouragement_tiers() -> None:
    assert posture_encouragement(95) == "非常棒！"
    assert posture_encouragement(90) == "非常棒！"
    assert posture_encouragement(70) == "很不错！"
    assert posture_encouragement(30) == "继续加油！"


def test_activation_for_actions_aggregates_and_skips_guide() -> None:
    act = activation_for_actions(["深蹲", "俯卧撑", "拉伸"])
    assert act["QUADS"] == 3
    assert act["CHEST"] == 3
    assert act["CORE"] == 2  # max of squat(1) / pushup(2)
    assert activation_for_actions(["热身"]) == {}


def test_render_muscle_svg_colors_by_intensity() -> None:
    svg = render_muscle_svg({"QUADS": 3, "CORE": 1}, view="front")
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "#1D4ED8" in svg  # 高强度
    assert "#BFDBFE" in svg  # 轻度
    assert "#E5E7EB" in svg  # 未激活
    back = render_muscle_svg({}, view="back")
    assert "#1D4ED8" not in back and "#60A5FA" not in back
