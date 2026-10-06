"""Glute bridge: flat → rise → hips extended → lower → flat (+1)."""

from __future__ import annotations

from datetime import datetime

from ..pose.keypoint import BodySide
from ..pose.pose_result import PoseResult
from ..utils.angle_utils import AngleUtils
from .action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    ActionRecognizer,
    SquatMachineState,
)
from .glute_bridge_config import GluteBridgeConfig


def _ms_between(later: datetime, earlier: datetime) -> int:
    return int((later - earlier).total_seconds() * 1000)


class GluteBridgeRecognizer(ActionRecognizer):
    """standing=flat, down=rising, bottom=hips up, up=lowering."""

    def __init__(self, config: GluteBridgeConfig | None = None) -> None:
        self._config = config or GluteBridgeConfig.defaults
        self._state = SquatMachineState.waiting_person
        self._rep_count = 0
        self._match_frames = 0
        self._pending_state: SquatMachineState | None = None
        self._state_entered_at: datetime | None = None
        self._last_rep_at: datetime | None = None
        self._now: datetime | None = None
        self._last_angle: float | None = None
        self._min_angle_in_cycle = 180.0
        self._max_angle_in_cycle = 0.0
        self._reached_top = False
        self._form_cue: str | None = None

    @property
    def config(self) -> GluteBridgeConfig:
        return self._config

    def update_config(self, value: GluteBridgeConfig) -> None:
        self._config = value

    @property
    def action_name(self) -> str:
        return "臀桥"

    @property
    def last_hip_angle(self) -> float | None:
        return self._last_angle

    def recognize(self, pose: PoseResult) -> ActionRecognitionResult:
        self._now = pose.timestamp
        reading = self._read_hip_angle(pose)
        self._last_angle = reading[0]

        if not reading[1] or reading[0] is None:
            self._clear_pending()
            self._state = SquatMachineState.waiting_person
            self._form_cue = "请侧对镜头，让肩、髋、膝进入画面"
            self._reset_cycle()
            return self._result(phase=ActionPhase.no_person, just_completed=False)

        angle = reading[0]
        just_completed = False
        self._form_cue = None

        if self._state == SquatMachineState.waiting_person:
            if angle > self._config.down_hip_angle:
                self._form_cue = "先仰卧屈膝，肩背贴地"
            self._try_enter(
                SquatMachineState.standing, angle <= self._config.down_hip_angle
            )
        elif self._state == SquatMachineState.standing:
            self._reset_cycle()
            self._note(angle)
            if self._try_enter(
                SquatMachineState.down,
                angle >= self._config.down_hip_angle + self._config.down_exit_hysteresis,
            ):
                self._begin_cycle(angle)
        elif self._state == SquatMachineState.down:
            self._note(angle)
            if self._try_enter(
                SquatMachineState.bottom, angle >= self._config.top_hip_angle
            ):
                self._reached_top = True
            elif self._try_enter(
                SquatMachineState.standing, angle <= self._config.down_hip_angle
            ):
                self._form_cue = "顶髋高度不足"
                self._reset_cycle()
        elif self._state == SquatMachineState.bottom:
            self._note(angle)
            self._reached_top = True
            if angle >= self._config.max_healthy_hip_angle:
                self._form_cue = "不要用腰过度顶起"
            self._try_enter(
                SquatMachineState.up,
                angle < self._config.top_hip_angle - self._config.top_hysteresis,
            )
        elif self._state == SquatMachineState.up:
            self._note(angle)
            if self._try_enter(
                SquatMachineState.bottom, angle >= self._config.top_hip_angle
            ):
                self._reached_top = True
            elif self._try_enter(
                SquatMachineState.standing, angle <= self._config.down_hip_angle
            ):
                if self._should_count():
                    self._rep_count += 1
                    self._last_rep_at = self._now
                    just_completed = True
                    if self._max_angle_in_cycle >= self._config.max_healthy_hip_angle:
                        self._form_cue = "不要用腰过度顶起"
                else:
                    self._form_cue = "顶髋高度不足"

        return self._result(
            phase=(
                ActionPhase.completed_rep
                if just_completed
                else self._to_phase(self._state)
            ),
            just_completed=just_completed,
        )

    def _begin_cycle(self, angle: float) -> None:
        self._min_angle_in_cycle = angle
        self._max_angle_in_cycle = angle
        self._reached_top = False

    def _note(self, angle: float) -> None:
        if angle < self._min_angle_in_cycle:
            self._min_angle_in_cycle = angle
        if angle > self._max_angle_in_cycle:
            self._max_angle_in_cycle = angle

    def _reset_cycle(self) -> None:
        self._min_angle_in_cycle = 180.0
        self._max_angle_in_cycle = 0.0
        self._reached_top = False

    def _should_count(self) -> bool:
        peak_ok = (
            self._reached_top
            and self._max_angle_in_cycle >= self._config.min_count_hip_angle
        )
        rom = self._max_angle_in_cycle - self._min_angle_in_cycle
        if not peak_ok or rom < self._config.min_effective_range_of_motion:
            return False
        last = self._last_rep_at
        now = self._now
        if last is None or now is None:
            return True
        return _ms_between(now, last) >= self._config.min_rep_interval_ms

    def _try_enter(self, next_state: SquatMachineState, condition: bool) -> bool:
        now = self._now
        entered = self._state_entered_at
        if (
            entered is not None
            and now is not None
            and _ms_between(now, entered) < self._config.min_state_duration_ms
        ):
            return False
        if not condition:
            if self._pending_state == next_state:
                self._clear_pending()
            return False
        if self._pending_state != next_state:
            self._pending_state = next_state
            self._match_frames = 1
        else:
            self._match_frames += 1
        if self._match_frames >= self._config.state_confirm_frames:
            self._state = next_state
            self._state_entered_at = now
            self._clear_pending()
            return True
        return False

    def _clear_pending(self) -> None:
        self._pending_state = None
        self._match_frames = 0

    def _to_phase(self, state: SquatMachineState) -> ActionPhase:
        if state == SquatMachineState.waiting_person:
            return ActionPhase.preparing
        if state == SquatMachineState.standing:
            return ActionPhase.standing
        if state in (SquatMachineState.down, SquatMachineState.bottom):
            return ActionPhase.squatting
        return ActionPhase.rising

    def _result(
        self, *, phase: ActionPhase, just_completed: bool
    ) -> ActionRecognitionResult:
        min_a = (
            self._min_angle_in_cycle
            if self._min_angle_in_cycle < 180
            else self._last_angle
        )
        max_a = (
            self._max_angle_in_cycle
            if self._max_angle_in_cycle > 0
            else self._last_angle
        )
        rom = (max_a - min_a) if min_a is not None and max_a is not None else None
        return ActionRecognitionResult(
            phase=phase,
            machine_state=self._state,
            rep_count=self._rep_count,
            knee_angle=self._last_angle,
            just_completed_rep=just_completed,
            reached_bottom=self._reached_top or just_completed,
            depth_ok=(
                (
                    self._reached_top
                    and self._max_angle_in_cycle >= self._config.min_count_hip_angle
                )
                or just_completed
            ),
            has_reliable_pose=self._last_angle is not None
            and phase != ActionPhase.no_person,
            rep_min_knee_angle=min_a,
            rep_max_knee_angle=max_a,
            range_of_motion=rom,
            form_cue=self._form_cue,
        )

    def _read_hip_angle(
        self, pose: PoseResult
    ) -> tuple[float | None, bool]:
        left = self._side_angle(pose, BodySide.left)
        right = self._side_angle(pose, BodySide.right)
        if left is None and right is None:
            return (None, False)
        if left is not None and right is not None:
            return ((left[0] + right[0]) / 2, True)
        single = left if left is not None else right
        return (None if single is None else single[0], single is not None)

    def _side_angle(
        self, pose: PoseResult, side: BodySide
    ) -> tuple[float, float] | None:
        shoulder = (
            pose.left_shoulder if side == BodySide.left else pose.right_shoulder
        )
        hip = pose.left_hip if side == BodySide.left else pose.right_hip
        knee = pose.left_knee if side == BodySide.left else pose.right_knee
        if shoulder is None or hip is None or knee is None:
            return None
        conf = self._config.minimum_confidence
        if (
            shoulder.confidence < conf
            or hip.confidence < conf
            or knee.confidence < conf
        ):
            return None
        angle = AngleUtils.calculate_angle(shoulder, hip, knee)
        confidence = shoulder.confidence + hip.confidence + knee.confidence
        return (angle, confidence)

    def reset(self) -> None:
        self._state = SquatMachineState.waiting_person
        self._rep_count = 0
        self._clear_pending()
        self._state_entered_at = None
        self._last_rep_at = None
        self._now = None
        self._last_angle = None
        self._form_cue = None
        self._reset_cycle()
