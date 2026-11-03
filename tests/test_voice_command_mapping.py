from __future__ import annotations

from jiandong_ai.ai.session.voice_session import (
    TRAINING_COMMAND_MAP,
    map_voice_command,
    voice_help_text,
)


def test_training_command_mapping():
    assert TRAINING_COMMAND_MAP["开始训练"] == "begin"
    assert TRAINING_COMMAND_MAP["暂停训练"] == "pause"
    assert TRAINING_COMMAND_MAP["继续训练"] == "resume"
    assert TRAINING_COMMAND_MAP["结束训练"] == "stop"
    assert TRAINING_COMMAND_MAP["帮助"] == "voice_help"


def test_in_training_accepts_training_commands():
    assert map_voice_command("暂停训练", in_training=True) == "pause"
    assert map_voice_command("继续训练", in_training=True) == "resume"
    assert map_voice_command("结束训练", in_training=True) == "stop"
    assert map_voice_command("帮助", in_training=True) == "voice_help"


def test_in_training_ignores_course_keywords():
    # 场景防抖：训练中忽略部位/确认类口令。
    assert map_voice_command("腿部", in_training=True) is None
    assert map_voice_command("确认", in_training=True) is None
    assert map_voice_command("换一个", in_training=True) is None


def test_outside_training_accepts_course_keywords():
    assert map_voice_command("腿部", in_training=False) == "腿部"
    assert map_voice_command("核心", in_training=False) == "核心"
    assert map_voice_command("全身", in_training=False) == "全身"
    assert map_voice_command("确认", in_training=False) == "确认"
    assert map_voice_command("换一个", in_training=False) == "换一个"
    assert map_voice_command("开始训练", in_training=False) == "开始训练"


def test_outside_training_ignores_training_commands():
    # 未进训练页时忽略 pause/resume/stop 等训练口令。
    assert map_voice_command("暂停训练", in_training=False) is None
    assert map_voice_command("继续训练", in_training=False) is None
    assert map_voice_command("结束训练", in_training=False) is None
    assert map_voice_command("帮助", in_training=False) is None


def test_unknown_or_empty_keyword():
    assert map_voice_command("你好世界", in_training=False) is None
    assert map_voice_command("你好世界", in_training=True) is None
    assert map_voice_command("", in_training=False) is None
    assert map_voice_command("  ", in_training=True) is None


def test_voice_help_text_covers_commands():
    in_training = voice_help_text(in_training=True)
    assert "暂停训练" in in_training
    assert "继续训练" in in_training
    assert "结束训练" in in_training
    outside = voice_help_text(in_training=False)
    assert "腿部" in outside
    assert "确认" in outside
    assert "换一个" in outside
