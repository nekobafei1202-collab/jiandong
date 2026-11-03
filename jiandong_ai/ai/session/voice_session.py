"""无障碍语音选课会话：idle → ask_part → recommend → confirm → ready → 移交训练。

训练外口令经 Kotlin VoiceCommandBridge 原子写 ``voice_cmd.json``（seq + keyword），
本模块常驻轮询消费（seq 去重，模式同 AndroidBridgePoseSession 的 event.json）；
对话文本经 ``tts.json``（seq + text 原子写）交给原生 TtsAnnouncer 播报。
全部可注入：bridge_dir / speaker / on_start_training 均可传参，
桌面无 bridge 时 start() 直接返回 False，不抛异常。
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

from jiandong_ai.services.body_part_recommender import (
    PART_DISPLAY,
    BodyPartRecommender,
    resolve_part,
)

# 训练阶段口令 → 原生事件 type（Kotlin 侧 emitEvent 复用同一映射）。
TRAINING_COMMAND_MAP: dict[str, str] = {
    "开始训练": "begin",
    "暂停训练": "pause",
    "继续训练": "resume",
    "结束训练": "stop",
    "帮助": "voice_help",
    "再说一遍": "voice_repeat",
    "下一个动作": "action_next",
    "上一个动作": "action_prev",
}

_CONFIRM_KEYWORDS = {"确认", "好的", "可以"}
_CHANGE_KEYWORDS = {"换一个", "换一批", "换一换"}
_IGNORED_KEYWORDS = {"登录", "小健小健", "退出助手"}
_VOICE_SESSION_FLAG = "voice_session_active.flag"


def _atomic_write_text(path: Path, value: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value, encoding="utf-8")
    tmp.replace(path)


def _read_tts_seq(bridge_dir: Path) -> int:
    try:
        payload = json.loads((bridge_dir / "tts.json").read_text(encoding="utf-8"))
        return max(0, int(payload.get("seq", 0)))
    except Exception:
        return 0


def _write_tts(bridge_dir: Path, text: str, seq: int) -> None:
    payload = json.dumps({"seq": seq, "text": text}, ensure_ascii=False)
    _atomic_write_text(bridge_dir / "tts.json", payload)


def _activate_voice_session_flag(bridge_dir: Path, owner: str) -> None:
    _atomic_write_text(bridge_dir / _VOICE_SESSION_FLAG, owner)


def _deactivate_voice_session_flag(bridge_dir: Path, owner: str) -> None:
    """只删除自己写入的 flag，避免旧页面停用时关掉新会话的 TTS 通道。"""
    path = bridge_dir / _VOICE_SESSION_FLAG
    try:
        if path.read_text(encoding="utf-8").strip() != owner:
            return
        path.unlink(missing_ok=True)
    except FileNotFoundError:
        pass


def map_voice_command(keyword: str, *, in_training: bool) -> str | None:
    """口令场景防抖：训练中只接受训练口令（返回事件 type），
    训练外只接受选课口令（原样返回关键词）；不在当前场景返回 None。"""
    kw = (keyword or "").strip()
    if not kw:
        return None
    if in_training:
        return TRAINING_COMMAND_MAP.get(kw)
    if (
        resolve_part(kw) is not None
        or kw in _CONFIRM_KEYWORDS
        or kw in _CHANGE_KEYWORDS
        or kw == "开始训练"
    ):
        return kw
    return None


def voice_help_text(*, in_training: bool) -> str:
    """「帮助」口令播报文案。"""
    if in_training:
        return "训练中可以说：暂停训练、继续训练、结束训练、帮助。"
    return "可以说：腿部、核心、上肢、背部或全身来选择训练部位；推荐后说「确认」开始，说「换一个」调整。"


class VoiceCourseSession:
    """选课状态机 + 桥文件轮询。状态：idle/ask_part/recommend/confirm/ready。"""

    def __init__(
        self,
        *,
        bridge_dir: str | Path | None = None,
        on_start_training: Callable[[list[str], str], None] | None = None,
        speaker: Callable[[str], None] | None = None,
        recommender: BodyPartRecommender | None = None,
        poll_interval: float = 0.1,
    ) -> None:
        if bridge_dir is None:
            from jiandong_ai.ai.session.android_bridge_session import (
                _default_bridge_dir,
            )

            bridge_dir = _default_bridge_dir()
        self.bridge_dir = Path(bridge_dir)
        self._on_start_training = on_start_training
        self._speaker = speaker
        self._recommender = recommender or BodyPartRecommender()
        self._poll_interval = max(0.02, float(poll_interval))
        self.state = "idle"
        self._part: str | None = None
        self._actions: list[str] = []
        self._tts_seq = 0
        self._last_cmd_seq = -1
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._flag_owner = f"course-{id(self):x}-{time.time_ns()}"
        self._owns_voice_session_flag = False
        self._last_spoken = ""

    # ---- 状态机核心（无线程，可直接单测） ----

    def begin(self, greeting: str | None = None) -> None:
        """进入 ask_part 并播报开场引导。"""
        self.state = "ask_part"
        self._speak(greeting or "你好，想练哪个部位？可以说：腿部、核心、上肢、背部，或全身。")

    def handle_keyword(self, keyword: str) -> None:
        """消费一条选课口令；无效口令停留原状态并提示。"""
        raw = (keyword or "").strip()
        if raw in _IGNORED_KEYWORDS:
            return
        if raw == "再说一遍":
            self._speak(self._last_spoken or voice_help_text(in_training=False))
            return
        if raw == "帮助":
            self._speak(voice_help_text(in_training=False))
            return
        kw = map_voice_command(raw, in_training=False)
        with self._lock:
            if self.state in {"ask_part", "idle"}:
                part = resolve_part(kw or "")
                if part is None:
                    self._speak("没听清，可以说：腿部、核心、上肢、背部，或全身。")
                    return
                self._part = part
                self._announce_recommendation()
                return
            if self.state in {"recommend", "confirm"}:
                if kw in _CONFIRM_KEYWORDS:
                    self.state = "ready"
                    self._speak(
                        "好的。请把手机竖直放在正前方，距离约 2 到 3 米，"
                        "确保周围 2 米内没有障碍物。准备好后说「开始训练」。"
                    )
                    return
                if kw in _CHANGE_KEYWORDS:
                    self._announce_recommendation(reroll=True)
                    return
                part = resolve_part(kw or "")
                if part is not None:
                    # 用户直接改口换部位。
                    self._part = part
                    self._announce_recommendation()
                    return
                self._speak("请说「确认」开始，或说「换一个」调整推荐。")
                return
            if self.state == "ready":
                if kw == "开始训练":
                    self._hand_off()
                    return
                self._speak("准备好后请说「开始训练」。")
                return

    def _announce_recommendation(self, *, reroll: bool = False) -> None:
        actions = (
            self._recommender.reroll()
            if reroll
            else self._recommender.recommend(self._part or "full")
        )
        if not actions:
            self._speak("暂时没有合适的推荐，请换个部位试试。")
            return
        self._actions = actions
        self.state = "confirm"
        part_name = PART_DISPLAY.get(self._part or "", "全身")
        names = "、".join(actions)
        self._speak(
            f"为你推荐{part_name}训练：{names}，共 {len(actions)} 个动作。"
            "说「确认」开始，说「换一个」调整。"
        )

    def _hand_off(self) -> None:
        actions = list(self._actions)
        part_name = PART_DISPLAY.get(self._part or "", "全身")
        self.state = "idle"
        self._speak("收到，正在进入训练。")
        cb = self._on_start_training
        if cb is not None and actions:
            cb(actions, f"{part_name}训练")

    # ---- 播报通道 ----

    def _speak(self, text: str) -> None:
        self._last_spoken = text
        if self._speaker is not None:
            self._speaker(text)
            return
        try:
            self.bridge_dir.mkdir(parents=True, exist_ok=True)
            self._tts_seq += 1
            _write_tts(self.bridge_dir, text, self._tts_seq)
        except Exception:
            pass

    def speak(self, text: str) -> None:
        """供助手会话复用当前 TTS 通道，避免 tts.json seq 重置。"""
        self._speak(text)

    # ---- 常驻轮询（仅 start() 显式调用后启动） ----

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> bool:
        """开始轮询 voice_cmd.json；bridge 目录不可用时不报错。"""
        try:
            self.bridge_dir.mkdir(parents=True, exist_ok=True)
            cmd = self.bridge_dir / "voice_cmd.json"
            cmd.unlink(missing_ok=True)
            self._last_cmd_seq = -1
            self._tts_seq = _read_tts_seq(self.bridge_dir)
            _activate_voice_session_flag(self.bridge_dir, self._flag_owner)
            self._owns_voice_session_flag = True
        except Exception:
            return False
        self._running = True
        if self._thread is None or not self._thread.is_alive():
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
        if self._owns_voice_session_flag:
            try:
                _deactivate_voice_session_flag(self.bridge_dir, self._flag_owner)
            except Exception:
                pass
            self._owns_voice_session_flag = False

    def _loop(self) -> None:
        cmd_path = self.bridge_dir / "voice_cmd.json"
        while self._running:
            try:
                self._poll_command(cmd_path)
            except Exception:
                pass
            time.sleep(self._poll_interval)

    def _poll_command(self, cmd_path: Path) -> None:
        if not cmd_path.exists():
            return
        try:
            payload = json.loads(cmd_path.read_text(encoding="utf-8"))
            seq = int(payload.get("seq", -1))
            if seq == self._last_cmd_seq:
                return
            self._last_cmd_seq = seq
            keyword = str(payload.get("keyword", "")).strip()
        except Exception:
            return
        if keyword:
            self.handle_keyword(keyword)


class LoginVoiceGuide:
    """登录页轻量语音会话：播报到站提示，消费「登录」和「帮助」。"""

    GREETING = (
        "当前是登录页面。已为您填好演示账号，说'登录'，"
        "即表示您已阅读并同意用户协议和隐私政策，然后进入首页。"
    )

    def __init__(
        self,
        *,
        on_login: Callable[[], None],
        bridge_dir: str | Path | None = None,
        poll_interval: float = 0.1,
    ) -> None:
        if bridge_dir is None:
            from jiandong_ai.ai.session.android_bridge_session import (
                _default_bridge_dir,
            )

            bridge_dir = _default_bridge_dir()
        self.bridge_dir = Path(bridge_dir)
        self._on_login = on_login
        self._poll_interval = max(0.02, float(poll_interval))
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_cmd_seq = -1
        self._tts_seq = 0
        self._flag_owner = f"login-{id(self):x}-{time.time_ns()}"
        self._owns_voice_session_flag = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> bool:
        if self._running:
            return True
        try:
            self.bridge_dir.mkdir(parents=True, exist_ok=True)
            (self.bridge_dir / "voice_cmd.json").unlink(missing_ok=True)
            self._last_cmd_seq = -1
            self._tts_seq = _read_tts_seq(self.bridge_dir)
            _activate_voice_session_flag(self.bridge_dir, self._flag_owner)
            self._owns_voice_session_flag = True
        except Exception:
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._speak(self.GREETING)
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
        if self._owns_voice_session_flag:
            try:
                _deactivate_voice_session_flag(self.bridge_dir, self._flag_owner)
            except Exception:
                pass
            self._owns_voice_session_flag = False

    def _speak(self, text: str) -> None:
        try:
            self._tts_seq += 1
            _write_tts(self.bridge_dir, text, self._tts_seq)
        except Exception:
            pass

    def _loop(self) -> None:
        cmd_path = self.bridge_dir / "voice_cmd.json"
        while self._running:
            try:
                self._poll_command(cmd_path)
            except Exception:
                pass
            time.sleep(self._poll_interval)

    def _poll_command(self, cmd_path: Path) -> None:
        if not cmd_path.exists():
            return
        try:
            payload = json.loads(cmd_path.read_text(encoding="utf-8"))
            seq = int(payload.get("seq", -1))
            if seq == self._last_cmd_seq:
                return
            self._last_cmd_seq = seq
            keyword = str(payload.get("keyword", "")).strip()
        except Exception:
            return
        if keyword == "登录":
            self._on_login()
        elif keyword == "帮助":
            self._speak(self.GREETING)
