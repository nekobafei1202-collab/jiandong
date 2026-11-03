from __future__ import annotations

import json

import pytest
import requests

from jiandong_ai.services.ai_assistant import (
    DeepSeekAssistant,
    clear_deepseek_api_key,
    configure_deepseek_config_path,
    get_deepseek_api_key_status,
    load_deepseek_api_key,
    mask_deepseek_api_key,
    parse_assistant_reply,
    save_deepseek_api_key,
)


class _Response:
    def __init__(self, payload=None, *, error: Exception | None = None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error

    def json(self):
        return self.payload


class _Session:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _deepseek_payload(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_api_key_save_load_mask_status_and_clear(tmp_path):
    path = tmp_path / "nested" / "ai_config.json"
    save_deepseek_api_key("  sk-1234567890  ", path)

    assert load_deepseek_api_key(path) == "sk-1234567890"
    assert mask_deepseek_api_key("sk-1234567890") == "sk-••••7890"
    assert get_deepseek_api_key_status(path) == "已配置（sk-••••7890）"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "deepseek_api_key": "sk-1234567890"
    }

    clear_deepseek_api_key(path)
    assert load_deepseek_api_key(path) is None
    assert get_deepseek_api_key_status(path) == "未配置"


def test_api_key_invalid_files_and_empty_value(tmp_path):
    path = tmp_path / "ai_config.json"
    assert load_deepseek_api_key(path) is None
    path.write_text("{broken", encoding="utf-8")
    assert load_deepseek_api_key(path) is None
    path.write_text('{"deepseek_api_key": 123}', encoding="utf-8")
    assert load_deepseek_api_key(path) is None
    assert mask_deepseek_api_key("short") == "••••••••"
    with pytest.raises(ValueError, match="不能为空"):
        save_deepseek_api_key(" ", path)


def test_runtime_config_path_override(tmp_path):
    path = tmp_path / "app-storage" / "ai_config.json"
    configure_deepseek_config_path(path)
    try:
        save_deepseek_api_key("runtime-secret")
        assert load_deepseek_api_key() == "runtime-secret"
        assert path.exists()
        clear_deepseek_api_key()
        assert not path.exists()
    finally:
        configure_deepseek_config_path(None)


@pytest.mark.parametrize(
    ("content", "action", "body_part", "reply", "error"),
    [
        (
            '{"action":"recommend","body_part":" 腿部 ","reply":"练腿"}',
            "recommend",
            "腿部",
            "练腿",
            None,
        ),
        ('{"action":"unknown","reply":"回答"}', "chat", None, "回答", None),
        ('{"action":"chat"}', "chat", None, "我没太明白，可以换个说法吗？", None),
        ("not json", "chat", None, "我没太明白，可以换个说法吗？", "invalid_json"),
        ("[]", "chat", None, "我没太明白，可以换个说法吗？", "invalid_json"),
    ],
)
def test_parse_assistant_reply(content, action, body_part, reply, error):
    parsed = parse_assistant_reply(content)
    assert (parsed.action, parsed.body_part, parsed.reply, parsed.error) == (
        action,
        body_part,
        reply,
        error,
    )


def test_parse_fenced_json():
    parsed = parse_assistant_reply('```json\n{"action":"pause","reply":"暂停"}\n```')
    assert parsed.action == "pause"
    assert parsed.reply == "暂停"


def test_deepseek_chat_success_builds_expected_request():
    response = _Response(
        _deepseek_payload('{"action":"query_plan","reply":"看看计划"}')
    )
    http = _Session(response)
    client = DeepSeekAssistant(api_key="secret", session=http)

    reply = client.chat("今天练什么")

    assert reply.action == "query_plan"
    assert client.available
    assert len(http.calls) == 1
    url, kwargs = http.calls[0]
    assert url.endswith("/chat/completions")
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    assert kwargs["json"]["model"] == "deepseek-chat"
    assert kwargs["json"]["response_format"] == {"type": "json_object"}
    assert kwargs["timeout"] == 30.0


def test_deepseek_missing_key_and_empty_input():
    client = DeepSeekAssistant(api_key="")
    missing = client.chat("练腿")
    assert missing.error == "missing_api_key"
    assert "API Key" in missing.reply
    assert not client.available

    empty = client.chat(" ")
    assert empty.error is None
    assert "没听到" in empty.reply


def test_deepseek_network_error_retries_and_degrades():
    http = _Session(
        requests.Timeout("slow"),
        _Response(error=requests.HTTPError("500")),
    )
    client = DeepSeekAssistant(api_key="secret", session=http, retries=1)

    reply = client.chat("练腿")

    assert reply.error == "network_error"
    assert reply.reply == "网络不太好，请稍后再试。"
    assert len(http.calls) == 2


def test_deepseek_bad_response_retries_and_degrades():
    http = _Session(_Response({}), _Response({"choices": []}))
    client = DeepSeekAssistant(api_key="secret", session=http, retries=1)

    reply = client.chat("练腿")

    assert reply.error == "bad_response"
    assert len(http.calls) == 2


def test_history_is_bounded_and_reset_without_extra_requests():
    http = _Session(*[_Response(_deepseek_payload('{"action":"chat","reply":"收紧核心"}')) for _ in range(5)])
    client = DeepSeekAssistant(api_key="fake", session=http)
    for index in range(5):
        client.chat(f"问题{index}")
    assert len(http.calls) == 5
    messages = http.calls[-1][1]["json"]["messages"]
    assert len(messages) == 8
    assert messages[1]["content"] == "问题1"
    assert http.calls[-1][1]["json"]["max_tokens"] == 256
    client.reset_context()
    assert client._history == []


def test_default_timeout_does_not_retry():
    http = _Session(requests.Timeout("slow"))
    reply = DeepSeekAssistant(api_key="fake", session=http).chat("如何热身")
    assert reply.error == "network_error"
    assert len(http.calls) == 1
