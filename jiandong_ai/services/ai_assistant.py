"""DeepSeek 意图层：把 ASR 文本转成结构化助手动作。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_CONFIG_PATH = Path.home() / ".jiandong_ai" / "ai_config.json"
_configured_config_path: Path | None = None

_ALLOWED_ACTIONS = {
    "recommend",
    "start",
    "pause",
    "resume",
    "stop",
    "query_plan",
    "chat",
}

_SYSTEM_PROMPT = """你是健动 AI 的语音助手“小健”。请根据用户的话输出严格 JSON，不要输出 Markdown。

你可以执行的动作：
- recommend：用户想练某个部位；body_part 只能是 腿部/核心/上肢/背部/全身 之一，reply 用来简短说明将推荐什么。
- start：开始今日训练或已确认的训练。
- pause/resume/stop：暂停/继续/结束当前训练。
- query_plan：查询今日训练计划。
- chat：普通健身问答或无法确定动作时的回答。

输出格式：
{"action":"recommend|start|pause|resume|stop|query_plan|chat","body_part":"腿部|核心|上肢|背部|全身（仅 recommend 需要）","reply":"给用户的中文口播回复，简短自然"}
"""


@dataclass(frozen=True)
class AssistantReply:
    action: str
    reply: str
    body_part: str | None = None
    error: str | None = None


def configure_deepseek_config_path(config_path: Path | None) -> None:
    """Point key storage at the runtime app-data directory (not packaged assets)."""
    global _configured_config_path
    _configured_config_path = config_path


def _resolve_config_path(config_path: Path | None = None) -> Path:
    return config_path or _configured_config_path or DEFAULT_CONFIG_PATH


def load_deepseek_api_key(config_path: Path | None = None) -> str | None:
    path = _resolve_config_path(config_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    key = payload.get("deepseek_api_key")
    if not isinstance(key, str):
        return None
    key = key.strip()
    return key or None


def save_deepseek_api_key(api_key: str, config_path: Path | None = None) -> None:
    """Persist the API key in the app-local config directory."""
    key = (api_key or "").strip()
    if not key:
        raise ValueError("API Key 不能为空")
    path = _resolve_config_path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(
            json.dumps({"deepseek_api_key": key}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def clear_deepseek_api_key(config_path: Path | None = None) -> None:
    """Remove the local API key without touching other app settings."""
    _resolve_config_path(config_path).unlink(missing_ok=True)


def mask_deepseek_api_key(api_key: str | None) -> str:
    key = (api_key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "••••••••"
    return f"{key[:3]}••••{key[-4:]}"


def get_deepseek_api_key_status(config_path: Path | None = None) -> str:
    masked = mask_deepseek_api_key(load_deepseek_api_key(config_path))
    return f"已配置（{masked}）" if masked else "未配置"


def parse_assistant_reply(content: str) -> AssistantReply:
    """解析模型输出；非 JSON/缺字段时给可播报兜底。"""
    text = (content or "").strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.startswith("```")]
        text = "\n".join(lines).strip()
    try:
        payload: Any = json.loads(text)
    except Exception:
        return AssistantReply(
            action="chat",
            reply="我没太明白，可以换个说法吗？",
            error="invalid_json",
        )
    if not isinstance(payload, dict):
        return AssistantReply(
            action="chat",
            reply="我没太明白，可以换个说法吗？",
            error="invalid_json",
        )
    action = str(payload.get("action") or "chat")
    if action not in _ALLOWED_ACTIONS:
        action = "chat"
    body_part = payload.get("body_part")
    if body_part is not None:
        body_part = str(body_part).strip() or None
    reply = str(payload.get("reply") or "").strip()
    if not reply:
        reply = "我没太明白，可以换个说法吗？" if action == "chat" else "好的。"
    return AssistantReply(action=action, body_part=body_part, reply=reply)


class DeepSeekAssistant:
    """DeepSeek chat/completions 客户端；缺 key 或网络失败时静默降级。"""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        config_path: Path | None = None,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        retries: int = 0,
    ) -> None:
        self.api_key = api_key if api_key is not None else load_deepseek_api_key(config_path)
        self.timeout = timeout
        self.retries = max(0, retries)
        self._session = session or requests.Session()
        self._history: list[dict[str, str]] = []

    def reset_context(self) -> None:
        self._history.clear()

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, text: str) -> AssistantReply:
        user_text = (text or "").strip()[:1000]
        if not user_text:
            return AssistantReply(action="chat", reply="我没听到内容，可以再说一次吗？")
        if not self.api_key:
            return AssistantReply(
                action="chat",
                reply="语音助手还没有配置 API Key，请在 ai_config.json 中配置后再试。",
                error="missing_api_key",
            )
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                *self._history,
                {"role": "user", "content": user_text},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
            "max_tokens": 256,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error = "request_failed"
        for _ in range(self.retries + 1):
            try:
                response = self._session.post(
                    DEEPSEEK_URL,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                reply = parse_assistant_reply(str(content))
                if not reply.error:
                    self._history.extend([
                        {"role": "user", "content": user_text},
                        {"role": "assistant", "content": json.dumps({"action": reply.action, "body_part": reply.body_part, "reply": reply.reply[:600]}, ensure_ascii=False)},
                    ])
                    self._history = self._history[-6:]
                return reply
            except requests.RequestException:
                last_error = "network_error"
            except (ValueError, KeyError, IndexError, TypeError):
                last_error = "bad_response"
        return AssistantReply(
            action="chat",
            reply="网络不太好，请稍后再试。",
            error=last_error,
        )
