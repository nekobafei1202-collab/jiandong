"""Dead bug (死虫式) hold monitor — no rep cycles, visibility-keeping only.

Deliberately lenient: shoulder + hip + at least one wrist or ankle visible at
minimum confidence means the practitioner is in frame and the timer runs.
Posture coaching copy ("保持腰部贴地") comes from the evaluator / feedback
layer, not from gating the timer.
"""

from __future__ import annotations

from datetime import datetime

from ..pose.keypoint import Keypoint
from ..pose.pose_result import PoseResult
from .action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    ActionRecognizer,
    SquatMachineState,
)
from .dead_bug_config import DeadBugConfig


def _ms_between(later: datetime, earlier: datetime) -> int:
    return max(0, int((later - earlier).total_seconds() * 1000))


class DeadBugRecognizer(ActionRecognizer):
    """WAITING / STANDING(保持中); hold completes set."""

    def __init__(self, config: DeadBugConfig | None = None) -> None:
        self._config = config or DeadBugConfig.defaults
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
        self._visible = False

    @property
    def config(self) -> DeadBugConfig:
        return self._config

    def update_config(self, value: DeadBugConfig) -> None:
        self._config = value

    @property
    def action_name(self) -> str:
        return "死虫式"

    @property
    def good_hold_ms(self) -> int:
        return self._good_ms

    @property
    def total_monitored_ms(self) -> int:
        return self._total_ms

    @property
    def current_hold_ms(self) -> int:
        return self._current_hold_ms

    def recognize(self, pose: PoseResult) -> ActionRecognitionResult:
        self._visible = self._is_visible(pose)

        if not self._visible:
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
        self._good_ms += delta

        if self._state != SquatMachineState.standing and self._can_leave(now):
            self._confirm_standing(now)

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

        return self._result(
            phase=(
                ActionPhase.completed_rep
                if just_completed
                else self._to_phase(self._state)
            ),
            just_completed=just_completed,
        )

    def _is_visible(self, pose: PoseResult) -> bool:
        conf = self._config.minimum_confidence

        def ok(kp: Keypoint | None) -> bool:
            return kp is not None and kp.confidence >= conf

        shoulder = ok(pose.left_shoulder) or ok(pose.right_shoulder)
        hip = ok(pose.left_hip) or ok(pose.right_hip)
        limb = (
            ok(pose.left_wrist)
            or ok(pose.right_wrist)
            or ok(pose.left_ankle)
            or ok(pose.right_ankle)
        )
        return shoulder and hip and limb

    def _can_leave(self, now: datetime) -> bool:
        entered = self._state_entered_at
        if entered is None:
            return True
        return _ms_between(now, entered) >= self._config.min_state_duration_ms

    def _confirm_standing(self, now: datetime) -> bool:
        if self._pending_state != SquatMachineState.standing:
            self._pending_state = SquatMachineState.standing
            self._match_frames = 1
        else:
            self._match_frames += 1
        if self._match_frames >= self._config.state_confirm_frames:
            self._state = SquatMachineState.standing
            self._state_entered_at = now
            self._clear_pending()
            return True
        return False

    def _can_complete(self, now: datetime) -> bool:
        last_done = self._last_completed_at
        if last_done is None:
            return True
        return _ms_between(now, last_done) >= self._config.min_rep_interval_ms

    def _clear_pending(self) -> None:
        self._pending_state = None
        self._match_frames = 0

    def _to_phase(self, state: SquatMachineState) -> ActionPhase:
        if state == SquatMachineState.standing:
            return ActionPhase.standing
        return ActionPhase.preparing

    def _result(
        self, *, phase: ActionPhase, just_completed: bool
    ) -> ActionRecognitionResult:
        return ActionRecognitionResult(
            phase=phase,
            machine_state=self._state,
            rep_count=self._rep_count,
            knee_angle=None,
            just_completed_rep=just_completed,
            has_reliable_pose=self._visible,
            form_cue=(
                None
                if self._visible
                else "请仰卧在画面中，让肩、髋和手脚都进入镜头"
            ),
        )

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
        self._visible = False
