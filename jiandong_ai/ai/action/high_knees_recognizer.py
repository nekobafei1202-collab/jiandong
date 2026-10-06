"""High-knees (高抬腿) recognizer."""

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
from .high_knees_config import HighKneesConfig


def _ms_between(later: datetime, earlier: datetime) -> int:
    return int((later - earlier).total_seconds() * 1000)


class HighKneesRecognizer(ActionRecognizer):
    """WAITING → IDLE → KNEE_UP → DOWN → IDLE (+1); either leg counts."""

    def __init__(self, config: HighKneesConfig | None = None) -> None:
        self._config = config or HighKneesConfig.defaults
        self._state = SquatMachineState.waiting_person
        self._rep_count = 0
        self._match_frames = 0
        self._pending_state: SquatMachineState | None = None
        self._state_entered_at: datetime | None = None
        self._last_rep_at: datetime | None = None
        self._active_side: BodySide | None = None
        self._left_lift: float | None = None
        self._right_lift: float | None = None
        self._primary_lift: float | None = None
        self._body_line_angle: float | None = None
        self._max_lift_in_cycle = 0.0
        self._min_lift_in_cycle = 0.0
        self._reached_high = False

    @property
    def config(self) -> HighKneesConfig:
        return self._config

    def update_config(self, value: HighKneesConfig) -> None:
        self._config = value

    @property
    def action_name(self) -> str:
        return "高抬腿"

    @property
    def active_side(self) -> BodySide | None:
        return self._active_side

    @property
    def last_lift_percent(self) -> float | None:
        if self._primary_lift is None:
            return None
        return self._primary_lift * 100

    def recognize(self, pose: PoseResult) -> ActionRecognitionResult:
        lifts = self._read_lifts(pose)
        self._left_lift = lifts[0]
        self._right_lift = lifts[1]

        if not lifts[2]:
            self._clear_pending()
            self._state = SquatMachineState.waiting_person
            self._reset_cycle_tracking()
            self._primary_lift = None
            self._body_line_angle = None
            return self._result(phase=ActionPhase.no_person, just_completed=False)

        self._body_line_angle = AngleUtils.body_line_angle_from_pose(pose)
        left = lifts[0]
        right = lifts[1]
        max_lift = self._max_of(left, right)
        just_completed = False

        if self._state == SquatMachineState.waiting_person:
            self._try_enter(SquatMachineState.standing, True)
        elif self._state == SquatMachineState.standing:
            self._primary_lift = max_lift
            if self._try_enter(
                SquatMachineState.bottom,
                max_lift is not None and max_lift >= self._config.high_knee_lift_ratio,
            ):
                self._active_side = (
                    BodySide.left
                    if (left if left is not None else -1)
                    >= (right if right is not None else -1)
                    else BodySide.right
                )
                assert max_lift is not None
                self._begin_cycle(max_lift)
                self._primary_lift = max_lift
        elif self._state == SquatMachineState.bottom:
            pair = self._active_pair(left, right)
            lift = pair[0]
            other = pair[1]
            if lift is None and other is not None:
                self._switch_active_side()
                lift = other
                other = None
            if lift is not None:
                self._primary_lift = lift
                self._note_lift(lift)
                if lift < self._config.high_knee_lift_ratio:
                    if (
                        other is not None
                        and other >= self._config.high_knee_lift_ratio
                    ):
                        just_completed = self._count_if_eligible(
                            lift <= self._config.handoff_count_max_lift
                        )
                        self._switch_active_side()
                        self._begin_cycle(other)
                        self._apply_state(SquatMachineState.bottom)
                        self._primary_lift = other
                    else:
                        self._try_enter(SquatMachineState.up, True)
                elif (
                    other is not None
                    and other > lift
                    and other >= self._config.high_knee_lift_ratio
                ):
                    self._switch_active_side()
                    self._primary_lift = other
        elif self._state == SquatMachineState.up:
            pair = self._active_pair(left, right)
            lift = pair[0]
            other = pair[1]
            if lift is None and other is not None:
                self._switch_active_side()
                lift = other
                other = None
            if lift is not None:
                self._primary_lift = lift
                self._note_lift(lift)
                if (
                    other is not None
                    and other >= self._config.high_knee_lift_ratio
                    and lift < self._config.high_knee_lift_ratio
                ):
                    just_completed = self._count_if_eligible(
                        lift <= self._config.handoff_count_max_lift
                    )
                    self._switch_active_side()
                    self._begin_cycle(other)
                    self._apply_state(SquatMachineState.bottom)
                    self._primary_lift = other
                elif lift >= self._config.high_knee_lift_ratio:
                    self._try_enter(SquatMachineState.bottom, True)
                elif lift <= self._config.idle_knee_lift_ratio and self._try_enter(
                    SquatMachineState.standing, True
                ):
                    just_completed = self._count_if_eligible(True)
                    self._active_side = None
                    self._reset_cycle_tracking(keep_extremes_for_result=True)
        elif self._state == SquatMachineState.down:
            self._try_enter(SquatMachineState.up, True)

        return self._result(
            phase=(
                ActionPhase.completed_rep
                if just_completed
                else self._to_phase(self._state)
            ),
            just_completed=just_completed,
        )

    def _active_pair(
        self, left: float | None, right: float | None
    ) -> tuple[float | None, float | None]:
        if self._active_side == BodySide.right:
            return (right, left)
        return (left, right)

    def _switch_active_side(self) -> None:
        self._active_side = (
            BodySide.left
            if self._active_side == BodySide.right
            else BodySide.right
        )

    def _max_of(self, a: float | None, b: float | None) -> float | None:
        if a is None:
            return b
        if b is None:
            return a
        return a if a >= b else b

    def _begin_cycle(self, lift: float) -> None:
        self._max_lift_in_cycle = lift
        self._min_lift_in_cycle = lift
        self._reached_high = lift >= self._config.high_knee_lift_ratio

    def _note_lift(self, lift: float) -> None:
        if lift > self._max_lift_in_cycle:
            self._max_lift_in_cycle = lift
        if lift < self._min_lift_in_cycle:
            self._min_lift_in_cycle = lift
        if lift >= self._config.high_knee_lift_ratio:
            self._reached_high = True

    def _count_if_eligible(self, extra_ok: bool) -> bool:
        if not extra_ok or not self._should_count_rep():
            return False
        self._rep_count += 1
        self._last_rep_at = datetime.now()
        return True

    def _should_count_rep(self) -> bool:
        height_ok = (
            self._reached_high
            and self._max_lift_in_cycle >= self._config.high_knee_lift_ratio
        )
        rom = self._max_lift_in_cycle - self._min_lift_in_cycle
        rom_ok = rom >= self._config.min_effective_lift_range * 0.6
        if not height_ok or not rom_ok:
            return False
        last = self._last_rep_at
        if last is None:
            return True
        return _ms_between(datetime.now(), last) >= self._config.min_rep_interval_ms

    def _try_enter(self, next_state: SquatMachineState, condition: bool) -> bool:
        if not self._can_leave_current_state():
            return False
        return self._confirm(condition, next_state)

    def _can_leave_current_state(self) -> bool:
        entered = self._state_entered_at
        if entered is None:
            return True
        return _ms_between(datetime.now(), entered) >= self._config.min_state_duration_ms

    def _confirm(self, condition: bool, next_state: SquatMachineState) -> bool:
        needed = self._config.state_confirm_frames
        if not condition:
            if self._pending_state == next_state:
                self._match_frames = 0
                self._pending_state = None
            return False
        if self._pending_state != next_state:
            self._pending_state = next_state
            self._match_frames = 1
            if needed <= 1:
                self._apply_state(next_state)
                return True
            return False
        self._match_frames += 1
        if self._match_frames >= needed:
            self._apply_state(next_state)
            return True
        return False

    def _apply_state(self, next_state: SquatMachineState) -> None:
        self._state = next_state
        self._state_entered_at = datetime.now()
        self._clear_pending()

    def _clear_pending(self) -> None:
        self._pending_state = None
        self._match_frames = 0

    def _reset_cycle_tracking(self, *, keep_extremes_for_result: bool = False) -> None:
        if not keep_extremes_for_result:
            self._active_side = None
            self._max_lift_in_cycle = 0.0
            self._min_lift_in_cycle = 0.0
            self._reached_high = False

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
            self._min_lift_in_cycle * 100 if self._min_lift_in_cycle > 0 else None
        )
        max_a = (
            self._max_lift_in_cycle * 100 if self._max_lift_in_cycle > 0 else None
        )
        rom = (max_a - min_a) if min_a is not None and max_a is not None else None
        depth_ok = (
            self._reached_high
            and self._max_lift_in_cycle >= self._config.high_knee_lift_ratio
        )
        return ActionRecognitionResult(
            phase=phase,
            machine_state=self._state,
            rep_count=self._rep_count,
            knee_angle=(
                None if self._primary_lift is None else self._primary_lift * 100
            ),
            left_knee_angle=(
                None if self._left_lift is None else self._left_lift * 100
            ),
            right_knee_angle=(
                None if self._right_lift is None else self._right_lift * 100
            ),
            just_completed_rep=just_completed,
            reached_bottom=self._reached_high or just_completed,
            depth_ok=depth_ok or just_completed,
            has_reliable_pose=(
                self._primary_lift is not None
                or self._left_lift is not None
                or self._right_lift is not None
            ),
            rep_min_knee_angle=min_a
            if min_a is not None
            else (
                None if self._primary_lift is None else self._primary_lift * 100
            ),
            rep_max_knee_angle=max_a
            if max_a is not None
            else (
                None if self._primary_lift is None else self._primary_lift * 100
            ),
            range_of_motion=rom,
            body_line_angle=self._body_line_angle,
            form_cue=self._form_cue(),
        )

    def _form_cue(self) -> str | None:
        line = self._body_line_angle
        if line is None:
            return None
        if abs(self._config.ideal_body_line_angle - line) > self._config.body_line_tolerance_degrees:
            return "身体保持直立，不要后仰"
        return None

    def _read_lifts(
        self, pose: PoseResult
    ) -> tuple[float | None, float | None, bool]:
        left = self._lift_for(pose, BodySide.left)
        right = self._lift_for(pose, BodySide.right)
        return (left, right, left is not None or right is not None)

    def _lift_for(self, pose: PoseResult, side: BodySide) -> float | None:
        chain = pose.lower_body(side)
        if chain is None:
            return None
        hip = chain.hip
        knee = chain.knee
        ankle = chain.ankle
        conf = self._config.minimum_confidence
        if (
            hip.confidence < conf
            or knee.confidence < conf
            or ankle.confidence < conf
        ):
            return None
        leg_len = ankle.y - hip.y
        if leg_len <= 0.01:
            return None
        shoulder = (
            pose.left_shoulder if side == BodySide.left else pose.right_shoulder
        )
        if shoulder is not None and shoulder.confidence >= conf:
            torso_len = hip.y - shoulder.y
            if torso_len > 0.01 and leg_len < torso_len * self._config.min_leg_to_torso_ratio:
                return None
        return (hip.y - knee.y) / leg_len + self._config.knee_rest_offset

    def reset(self) -> None:
        self._state = SquatMachineState.waiting_person
        self._rep_count = 0
        self._clear_pending()
        self._state_entered_at = None
        self._last_rep_at = None
        self._left_lift = None
        self._right_lift = None
        self._primary_lift = None
        self._body_line_angle = None
        self._reset_cycle_tracking()
