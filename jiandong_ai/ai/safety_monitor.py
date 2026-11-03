"""入镜自检与安全区域监控（纯逻辑，输入 PoseResult，输出播报文案）。

- 入镜自检：训练正式开始前检查 COCO-17 关键点可见性，缺脚/缺头/离镜过近
  给出对应引导语；连续 N 帧达标才通过；完全检测不到人时给兜底文案。
- 安全区域监控：人体中心横向漂移近边缘、肩宽占比过大（离手机过近）、
  帧间剧烈位移时输出警告文案；同类警告按冷却时间防刷屏。
"""

from __future__ import annotations

import time

from jiandong_ai.ai.pose.keypoint import Keypoint
from jiandong_ai.ai.pose.pose_result import PoseResult

_MIN_CONF = Keypoint.DEFAULT_MIN_CONFIDENCE


class SafetyMonitor:
    def __init__(
        self,
        *,
        pass_frames: int = 16,
        framing_timeout: float = 30.0,
        cooldown_seconds: float = 5.0,
        edge_margin: float = 0.12,
        close_shoulder_ratio: float = 0.55,
        jump_ratio: float = 0.35,
    ) -> None:
        self._pass_frames = max(1, int(pass_frames))
        self._framing_timeout = float(framing_timeout)
        self._cooldown = float(cooldown_seconds)
        self._edge_margin = float(edge_margin)
        self._close_ratio = float(close_shoulder_ratio)
        self._jump_ratio = float(jump_ratio)
        self._ok_frames = 0
        self._framing_passed = False
        self._framing_started_at: float | None = None
        self._timeout_hinted = False
        self._last_warn_at: dict[str, float] = {}
        self._last_center_x: float | None = None

    # ---- 内部工具 ----

    def _norm(self, pose: PoseResult, x: float, y: float) -> tuple[float, float]:
        """归一化坐标（像素坐标按画面宽高换算）。"""
        if pose.is_normalized:
            return x, y
        return x / pose.image_width, y / pose.image_height

    @staticmethod
    def _head_visible(pose: PoseResult) -> bool:
        for kp in (pose.nose, pose.left_eye, pose.right_eye, pose.left_ear, pose.right_ear):
            if kp is not None and kp.is_reliable(_MIN_CONF):
                return True
        return False

    @staticmethod
    def _feet_visible(pose: PoseResult) -> bool:
        for kp in (pose.left_ankle, pose.right_ankle):
            if kp is not None and kp.is_reliable(_MIN_CONF):
                return True
        return False

    def _shoulder_metrics(self, pose: PoseResult) -> tuple[float, float] | None:
        """返回 (肩宽占画面宽度比, 双肩中心归一化 x)；双肩不可靠时返回 None。"""
        ls, rs = pose.left_shoulder, pose.right_shoulder
        if (
            ls is None
            or rs is None
            or not ls.is_reliable(_MIN_CONF)
            or not rs.is_reliable(_MIN_CONF)
        ):
            return None
        lx, _ = self._norm(pose, ls.x, ls.y)
        rx, _ = self._norm(pose, rs.x, rs.y)
        width = abs(rx - lx)
        return width, (lx + rx) / 2.0

    # ---- 入镜自检 ----

    @property
    def framing_passed(self) -> bool:
        return self._framing_passed

    def reset_framing(self) -> None:
        self._ok_frames = 0
        self._framing_passed = False
        self._framing_started_at = None
        self._timeout_hinted = False

    def framing_check(self, pose: PoseResult, *, now: float | None = None) -> str | None:
        """每帧调用；返回需要播报的引导语，无需播报返回 None。"""
        now = time.time() if now is None else now
        if self._framing_started_at is None:
            self._framing_started_at = now
        if self._framing_passed:
            return None

        if not pose.has_person:
            self._ok_frames = 0
            if (
                not self._timeout_hinted
                and now - self._framing_started_at > self._framing_timeout
            ):
                self._timeout_hinted = True
                return "一直检测不到你，也可以请身边的人帮忙调整手机位置。"
            return "检测不到你，请站到手机正前方。"

        metrics = self._shoulder_metrics(pose)
        if metrics is not None and metrics[0] > self._close_ratio:
            self._ok_frames = 0
            return "请后退一步，让全身进入画面。"
        if not self._head_visible(pose):
            self._ok_frames = 0
            return "看不到头部，请把手机放高一点，或走近一点。"
        if not self._feet_visible(pose):
            self._ok_frames = 0
            return "看不到脚部，请后退一步，或把手机放低一点。"

        self._ok_frames += 1
        if self._ok_frames >= self._pass_frames:
            self._framing_passed = True
            return "位置很好，训练开始。"
        return None

    # ---- 安全区域监控 ----

    def reset_safety(self) -> None:
        self._last_warn_at = {}
        self._last_center_x = None

    def _cooled_down(self, category: str, now: float) -> bool:
        last = self._last_warn_at.get(category)
        if last is not None and now - last < self._cooldown:
            return False
        self._last_warn_at[category] = now
        return True

    def safety_check(self, pose: PoseResult, *, now: float | None = None) -> str | None:
        """训练中每帧调用；返回警告文案，无异常返回 None。"""
        now = time.time() if now is None else now
        if not pose.has_person:
            self._last_center_x = None
            return None
        metrics = self._shoulder_metrics(pose)
        if metrics is None:
            self._last_center_x = None
            return None
        width, center_x = metrics

        prev = self._last_center_x
        self._last_center_x = center_x
        if prev is not None and abs(center_x - prev) > self._jump_ratio:
            if self._cooled_down("jump", now):
                return "你还好吗？说「继续训练」恢复，或说「结束训练」停止。"
            return None
        if width > self._close_ratio:
            if self._cooled_down("close", now):
                return "离手机太近了，请后退一点。"
            return None
        if center_x < self._edge_margin or center_x > 1.0 - self._edge_margin:
            if self._cooled_down("edge", now):
                return "请回到中间位置。"
            return None
        return None
