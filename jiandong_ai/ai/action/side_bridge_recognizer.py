"""Side bridge (侧桥) hold monitor — no rep cycles, posture-keeping only.

Mirrors plank_recognizer's hold pattern: good body line accumulates hold
time; sagging/piking pauses it with a cue. Deliberately lenient — this is a
timer, not a rep counter.
"""

from __future__ import annotations

from datetime import datetime

from ..pose.pose_result import PoseResult
from ..utils.angle_utils import AngleUtils
from .action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    ActionRecognizer,
    SquatMachineState,
)
from .side_bridge_config import SideBridgeConfig


def _ms_between(later: datetime, earlier: datetime) -> int:
    return max(0, int((later - earlier).total_seconds() * 1000))


class SideBridgeRecognizer(ActionRecognizer):
    """WAITING / STANDING(保持中) / BOTTOM(髋下沉) / UP(髋过高); hold completes set."""

    def __init__(self, config: SideBridgeConfig | None = None) -> None:
        self._config = config or SideBridgeConfig.defaults
        self._state = SquatMachineState.waiting_person
        self._pending_state: SquatMachineState | None = None
        self._match_frames = 0
        self._state_entered_at: datetime | None = None
        self._last_frame_at: datetime | None = None
        self._last_completed_at: datetime | None = None
        self._rep_count = 0
        self._hold_completed = False
        self._good_ms = 0
        self._total_ms = 0
        self._current_hold_ms = 0
        self._last_angle: float | None = None

    @property
    def config(self) -> SideBridgeConfig:
        return self._config

    def update_config(self, value: SideBridgeConfig) -> None:
        self._config = value

    @property
    def action_name(self) -> str:
        return "侧桥"

    @property
    def good_hold_ms(self) -> int:
        return self._good_ms

    @property
    def total_monitored_ms(self) -> int:
        return self._total_ms

    @property
    def current_hold_ms(self) -> int:
        return self._current_hold_ms

    @property
    def last_body_line_angle(self) -> float | None:
        return self._last_angle

    def recognize(self, pose: PoseResult) -> ActionRecognitionResult:
        angle = self._read_signed_body_line_angle(pose)
        self._last_angle = angle

        if angle is None:
            self._clear_pending()
            self._state = SquatMachineState.waiting_person
            self._state_entered_at = None
            self._last_frame_at = None
            self._current_hold_ms = 0
            self._hold_completed = False
            return self._result(phase=ActionPhase.no_person, just_completed=False)

        now = pose.timestamp
        last = self._last_frame_at
        delta = 0 if last is None else _ms_between(now, last)
        self._last_frame_at = now
        self._total_ms += delta

        in_good_range = self._config.is_good_angle(angle)
        if in_good_range:
            self._good_ms += delta

        target = self._target_for(angle)
        if target != self._state and self._can_leave_current_state(now):
            self._confirm_target(target, now)
        elif target == self._state:
            self._clear_pending()

        just_completed = False
        if self._state == SquatMachineState.standing:
            self._current_hold_ms += delta
            if (
                not self._hold_completed
                and self._current_hold_ms >= self._config.target_hold_ms
                and self._can_complete(now)
            ):
                self._hold_completed = True
                self._rep_count = 1
                self._last_completed_at = now
                just_completed = True
        else:
            self._current_hold_ms = 0
            self._hold_completed = False

        return self._result(
            phase=(
                ActionPhase.completed_rep
                if just_completed
                else self._to_phase(self._state)
            ),
            just_completed=just_completed,
        )

    def _target_for(self, angle: float) -> SquatMachineState:
        if self._config.is_good_angle(angle):
            return SquatMachineState.standing
        return (
            SquatMachineState.bottom
            if angle < self._config.good_min_body_line_angle
            else SquatMachineState.up
        )

    def _can_complete(self, now: datetime) -> bool:
        last_done = self._last_completed_at
        if last_done is None:
            return True
        return _ms_between(now, last_done) >= self._config.min_rep_interval_ms

    def _can_leave_current_state(self, now: datetime) -> bool:
        entered = self._state_entered_at
        if entered is None:
            return True
        return _ms_between(now, entered) >= self._config.min_state_duration_ms

    def _confirm_target(self, target: SquatMachineState, now: datetime) -> bool:
        if self._pending_state != target:
            self._pending_state = target
            self._match_frames = 1
        else:
            self._match_frames += 1
        if self._match_frames >= self._config.state_confirm_frames:
            self._apply_state(target, now)
            return True
        return False

    def _apply_state(self, next_state: SquatMachineState, now: datetime) -> None:
        self._state = next_state
        self._state_entered_at = now
        self._clear_pending()

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
        cue = None
        if self._state == SquatMachineState.bottom:
            cue = "髋部不要下沉"
        elif self._state == SquatMachineState.up:
            cue = "髋部不要抬太高"
        return ActionRecognitionResult(
            phase=phase,
            machine_state=self._state,
            rep_count=self._rep_count,
            knee_angle=None,
            just_completed_rep=just_completed,
            has_reliable_pose=self._last_angle is not None,
            body_line_angle=self._last_angle,
            form_cue=cue,
        )

    def _read_signed_body_line_angle(self, pose: PoseResult) -> float | None:
        chain = pose.preferred_body_line
        if chain is None:
            return None
        conf = self._config.minimum_confidence
        if (
            chain.shoulder.confidence < conf
            or chain.hip.confidence < conf
            or chain.ankle.confidence < conf
        ):
            return None

        interior = AngleUtils.calculate_angle(
            chain.shoulder, chain.hip, chain.ankle
        )
        s = chain.shoulder
        a = chain.ankle
        h = chain.hip
        dx = a.x - s.x
        if abs(dx) < 1e-6:
            line_y = (s.y + a.y) / 2
        else:
            line_y = s.y + ((h.x - s.x) / dx) * (a.y - s.y)
        sagging = h.y > line_y
        return interior if sagging else 360 - interior

    def reset(self) -> None:
        self._state = SquatMachineState.waiting_person
        self._rep_count = 0
        self._clear_pending()
        self._state_entered_at = None
        self._last_frame_at = None
        self._last_completed_at = None
        self._hold_completed = False
        self._good_ms = 0
        self._total_ms = 0
        self._current_hold_ms = 0
        self._last_angle = None
