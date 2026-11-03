"""“小健”自由对话助手会话：KWS 唤醒 → ASR 文本 → DeepSeek 意图 → 口播/动作。"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

from jiandong_ai.ai.session.voice_session import (
    _atomic_write_text,
    _read_tts_seq,
    _write_tts,
)
from jiandong_ai.services.ai_assistant import AssistantReply, DeepSeekAssistant
from jiandong_ai.services.body_part_recommender import resolve_part

ASSISTANT_ACTIVE_FLAG = "assistant_active.flag"
_ASSISTANT_WAKE_FLAG = "assistant_wake.flag"
_ASR_RESULT_FILE = "asr_result.json"
_TRAINING_FLAG = "training_active.flag"


class AssistantSession:
    """常驻 dormant 轮询；只在唤醒后短暂进入 listening/respond。"""

    def __init__(
        self,
        *,
        bridge_dir: str | Path | None = None,
        ai_client: DeepSeekAssistant | None = None,
        speaker: Callable[[str], None] | None = None,
        on_recommend: Callable[[str], str | None] | None = None,
        on_control: Callable[[str], str | None] | None = None,
        on_query_plan: Callable[[], str] | None = None,
        on_navigate: Callable[[str], str] | None = None,
        poll_interval: float = 0.1,
        idle_timeout: float = 60.0,
    ) -> None:
        if bridge_dir is None:
            from jiandong_ai.ai.session.android_bridge_session import (
                _default_bridge_dir,
            )

            bridge_dir = _default_bridge_dir()
        self.bridge_dir = Path(bridge_dir)
        self._ai = ai_client or DeepSeekAssistant()
        self._speaker = speaker
        self._on_recommend = on_recommend
        self._on_control = on_control
        self._on_query_plan = on_query_plan
        self._on_navigate = on_navigate
        self._pending_tts_seq = 0
        self._poll_interval = max(0.02, float(poll_interval))
        self._idle_timeout = max(0.1, float(idle_timeout))
        self.state = "dormant"
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_asr_seq = -1
        self._last_input_at = 0.0
        self._tts_seq = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_active(self) -> bool:
        return self.state != "dormant"

    def start(self) -> bool:
        if self._running:
            return True
        try:
            self.bridge_dir.mkdir(parents=True, exist_ok=True)
            (self.bridge_dir / _ASSISTANT_WAKE_FLAG).unlink(missing_ok=True)
            (self.bridge_dir / _ASR_RESULT_FILE).unlink(missing_ok=True)
            (self.bridge_dir / ASSISTANT_ACTIVE_FLAG).unlink(missing_ok=True)
            self._tts_seq = _read_tts_seq(self.bridge_dir)
        except Exception:
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if (
            self._thread
            and self._thread.is_alive()
            and self._thread is not threading.current_thread()
        ):
            self._thread.join(timeout=1.0)
        self._thread = None
        self.state = "dormant"
        (self.bridge_dir / "assistant_thinking.flag").unlink(missing_ok=True)
        (self.bridge_dir / ASSISTANT_ACTIVE_FLAG).unlink(missing_ok=True)

    def _loop(self) -> None:
        while self._running:
            try:
                self._tick()
            except Exception:
                pass
            time.sleep(self._poll_interval)

    def _tick(self) -> None:
        training_active = (self.bridge_dir / _TRAINING_FLAG).exists()
        if training_active and self.is_active:
            self._deactivate()
            return
        if self.state == "dormant":
            self._poll_wake(training_active=training_active)
            return
        if self.state == "woken":
            if time.monotonic() - self._last_input_at > 90:
                self._speak("语音识别暂时没有准备好，请稍后再叫我。")
                self._deactivate()
                return
            if (self.bridge_dir / "asr_ready.flag").exists():
                self._speak("我在，你说。")
                self.state = "listening"
                self._last_input_at = time.monotonic()
            return
        if self._playback_pending():
            self._last_input_at = time.monotonic()
            return
        self._poll_asr_result()
        if self.is_active and time.monotonic() - self._last_input_at >= self._idle_timeout:
            self._speak("好的，随时叫我。")
            self._deactivate()

    def _poll_wake(self, *, training_active: bool) -> None:
        wake = self.bridge_dir / _ASSISTANT_WAKE_FLAG
        if not wake.exists():
            return
        wake.unlink(missing_ok=True)
        if training_active:
            return
        (self.bridge_dir / _ASR_RESULT_FILE).unlink(missing_ok=True)
        self._last_asr_seq = -1
        self._tts_seq = _read_tts_seq(self.bridge_dir)
        _atomic_write_text(self.bridge_dir / ASSISTANT_ACTIVE_FLAG, "1")
        self.state = "woken"
        self._last_input_at = time.monotonic()
        reset = getattr(self._ai, "reset_context", None)
        if reset is not None:
            reset()

    def _poll_asr_result(self) -> None:
        path = self.bridge_dir / _ASR_RESULT_FILE
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            seq = int(payload.get("seq", -1))
            if seq == self._last_asr_seq:
                return
            self._last_asr_seq = seq
            text = str(payload.get("text", "")).strip()
        except Exception:
            return
        if text:
            self.handle_utterance(text)

    def handle_utterance(self, text: str) -> None:
        """消费一条 ASR 文本；可直接单测，无需线程。"""
        if self.state == "dormant":
            return
        self._last_input_at = time.monotonic()
        if text.strip(" 。！!，,？?") in {"退出", "退出助手", "请退出助手", "结束对话", "不用了", "再见"}:
            self._speak("好的，随时叫我。")
            self._deactivate()
            return
        self.state = "thinking"
        destinations = {"首页": "home", "课程": "courses", "计划": "plan", "个人中心": "profile"}
        normalized = text.strip(" 。！!，,？?")
        destination = next((value for name, value in destinations.items()
                            if normalized in {name, "打开" + name, "进入" + name, "去" + name, "返回" + name, "回到" + name}), None)
        if destination and self._on_navigate:
            spoken = self._on_navigate(destination)
            if spoken:
                self._speak(spoken)
            self.state = "listening"
            self._last_input_at = time.monotonic()
            return
        busy = self.bridge_dir / "assistant_thinking.flag"
        _atomic_write_text(busy, "1")
        try:
            reply = self._ai.chat(text)
        finally:
            busy.unlink(missing_ok=True)
        spoken = self._dispatch(reply)
        self._pending_tts_seq = _read_tts_seq(self.bridge_dir)
        if spoken:
            self._speak(spoken)
        self.state = "listening"
        self._last_input_at = time.monotonic()

    def _dispatch(self, reply: AssistantReply) -> str:
        if reply.error in {"missing_api_key", "network_error", "bad_response"}:
            return reply.reply
        if reply.action == "recommend":
            part = resolve_part(reply.body_part or "")
            if part is not None and self._on_recommend is not None:
                spoken = self._on_recommend(part)
                return reply.reply if spoken is None else spoken
            return reply.reply
        if reply.action in {"start", "pause", "resume", "stop"}:
            if self._on_control is not None:
                return self._on_control(reply.action) or reply.reply
            return reply.reply
        if reply.action == "query_plan":
            if self._on_query_plan is not None:
                return self._on_query_plan()
            return reply.reply
        return reply.reply

    def _deactivate(self) -> None:
        self.state = "dormant"
        (self.bridge_dir / "assistant_thinking.flag").unlink(missing_ok=True)
        (self.bridge_dir / ASSISTANT_ACTIVE_FLAG).unlink(missing_ok=True)

    def _playback_pending(self) -> bool:
        if not self._pending_tts_seq:
            return False
        try:
            status = json.loads((self.bridge_dir / "tts_status.json").read_text(encoding="utf-8"))
            pending = int(status.get("seq", -1)) < self._pending_tts_seq or bool(status.get("busy"))
            if not pending:
                self._pending_tts_seq = 0
                self._last_input_at = time.monotonic()
            return pending
        except (OSError, ValueError, TypeError):
            return True

    def _speak(self, text: str) -> None:
        if self._speaker is not None:
            self._speaker(text)
            self._pending_tts_seq = _read_tts_seq(self.bridge_dir)
            return
        try:
            self._tts_seq += 1
            _write_tts(self.bridge_dir, text, self._tts_seq)
            self._pending_tts_seq = self._tts_seq
        except Exception:
            pass
