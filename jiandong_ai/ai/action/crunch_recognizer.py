"""Crunch: flat(standing) → curling(down) → curled(bottom) → lowering(up)
→ flat (+1).

Signal is the torso flexion angle shoulder→hip→knee, debounced with a 3-frame
median (single-frame confirm at 12fps). Timing uses pose.timestamp (bridge
cadence), not the wall clock.

Thresholds come from real footage (see crunch_config docstring): a bent-knee
flat baseline is only ~123-130°, so the machine must arm far below a "fully
open" hip. A shoulder-y displacement fallback was tried and rejected on real
video: after the threshold fix the angle machine carries both test videos,
while the fallback only added false positives on rest/talk segments.
"""

from __future__ import annotations

from datetime import datetime
from statistics import median

from ..pose.keypoint import BodySide
from ..pose.pose_result import PoseResult
from ..utils.angle_utils import AngleUtils
from .action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    ActionRecognizer,
    SquatMachineState,
)
from .crunch_config import CrunchConfig


def _ms_between(later: datetime, earlier: datetime) -> int:
    return int((later - earlier).total_seconds() * 1000)


class CrunchRecognizer(ActionRecognizer):
    def __init__(self, config: CrunchConfig | None = None) -> None:
        self._config = config or CrunchConfig.defaults
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
        self._reached_bottom = False
        self._form_cue: str | None = None
        self._angle_window: list[float] = []

    @property
    def config(self) -> CrunchConfig:
        return self._config

    def update_config(self, value: CrunchConfig) -> None:
        self._config = value

    @property
    def action_name(self) -> str:
        return "卷腹"

    @property
    def last_torso_angle(self) -> float | None:
        return self._last_angle

    def recognize(self, pose: PoseResult) -> ActionRecognitionResult:
        self._now = pose.timestamp
        reading = self._read_torso_angle(pose)

        if not reading[1] or reading[0] is None:
            self._clear_pending()
            self._angle_window.clear()
            self._state = SquatMachineState.waiting_person
            self._form_cue = "请侧对镜头仰卧，让肩、髋、膝进入画面"
            self._reset_cycle()
            return self._result(phase=ActionPhase.no_person, just_completed=False)

        angle = self._smooth(reading[0])
        self._last_angle = angle
        just_completed = False

        if self._state == SquatMachineState.waiting_person:
            # 提示保持到状态改变为止（12fps 下单帧提示用户看不见）。
            self._form_cue = (
                None
                if angle >= self._config.high_torso_angle
                else "先躺平，肩背贴地"
            )
            self._try_enter(
                SquatMachineState.standing, angle >= self._config.high_torso_angle
            )
        elif self._state == SquatMachineState.standing:
            self._reset_cycle()
            self._note(angle)
            if self._try_enter(
                SquatMachineState.down, angle <= self._config.down_torso_angle
            ):
                self._form_cue = None
                self._begin_cycle(angle)
        elif self._state == SquatMachineState.down:
            self._note(angle)
            if self._try_enter(
                SquatMachineState.bottom, angle <= self._config.bottom_torso_angle
            ):
                self._reached_bottom = True
            elif self._try_enter(
                SquatMachineState.standing, angle >= self._config.high_torso_angle
            ):
                self._form_cue = "卷起高度不足"
                self._reset_cycle()
        elif self._state == SquatMachineState.bottom:
            self._note(angle)
            self._reached_bottom = True
            self._try_enter(
                SquatMachineState.up,
                angle >= self._config.bottom_torso_angle
                + self._config.bottom_hysteresis,
            )
        elif self._state == SquatMachineState.up:
            self._note(angle)
            if self._try_enter(
                SquatMachineState.bottom, angle <= self._config.bottom_torso_angle
            ):
                self._reached_bottom = True
            elif self._try_enter(
                SquatMachineState.standing, angle >= self._config.high_torso_angle
            ):
                if self._should_count():
                    self._rep_count += 1
                    self._last_rep_at = self._now
                    just_completed = True
                    self._form_cue = None
                else:
                    self._form_cue = "卷起高度不足"

        return self._result(
            phase=(
                ActionPhase.completed_rep
                if just_completed
                else self._to_phase(self._state)
            ),
            just_completed=just_completed,
        )

    def _smooth(self, angle: float) -> float:
        window = self._angle_window
        window.append(angle)
        if len(window) > 3:
            window.pop(0)
        return float(median(window))

    def _begin_cycle(self, angle: float) -> None:
        self._min_angle_in_cycle = angle
        self._max_angle_in_cycle = angle
        self._reached_bottom = False

    def _note(self, angle: float) -> None:
        if angle < self._min_angle_in_cycle:
            self._min_angle_in_cycle = angle
        if angle > self._max_angle_in_cycle:
            self._max_angle_in_cycle = angle

    def _reset_cycle(self) -> None:
        self._min_angle_in_cycle = 180.0
        self._max_angle_in_cycle = 0.0
        self._reached_bottom = False

    def _should_count(self) -> bool:
        depth_ok = (
            self._reached_bottom
            and self._min_angle_in_cycle <= self._config.min_count_torso_angle
        )
        rom = self._max_angle_in_cycle - self._min_angle_in_cycle
        if not depth_ok or rom < self._config.min_effective_range_of_motion:
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
            reached_bottom=self._reached_bottom or just_completed,
            depth_ok=(
                (
                    self._reached_bottom
                    and self._min_angle_in_cycle
                    <= self._config.min_count_torso_angle
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

    def _read_torso_angle(
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
        self._angle_window.clear()
        self._reset_cycle()
