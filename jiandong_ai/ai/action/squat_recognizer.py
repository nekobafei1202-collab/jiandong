"""Squat recognizer with STANDING → DOWN → BOTTOM → UP → STANDING.

Only a full cycle that visited BOTTOM with sufficient depth can count +1.
All decisions use multi-frame confirmation + minimum state duration.
"""

from __future__ import annotations

from dataclasses import dataclass
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
from .squat_config import SquatConfig
from .squat_frame_data import SquatFrameData, SquatRepTrajectory


@dataclass(frozen=True)
class _KneeAngles:
    left: float | None
    right: float | None
    primary: float | None
    reliable: bool


class SquatRecognizer(ActionRecognizer):
    def __init__(self, config: SquatConfig | None = None) -> None:
        self._config = config if config is not None else SquatConfig.defaults
        self._state = SquatMachineState.waiting_person
        self._rep_count = 0
        self._match_frames = 0
        self._pending_state: SquatMachineState | None = None
        self._state_entered_at: datetime | None = None
        self._last_rep_at: datetime | None = None
        self._cycle_started_at: datetime | None = None
        self._last_angle: float | None = None
        self._left_angle: float | None = None
        self._right_angle: float | None = None
        self._min_angle_in_cycle = 180.0
        self._max_angle_in_cycle = 0.0
        self._reached_bottom = False
        self._recording_cycle = False
        self._current_frames: list[SquatFrameData] = []
        self._last_trajectory: SquatRepTrajectory | None = None

    @property
    def config(self) -> SquatConfig:
        return self._config

    def update_config(self, value: SquatConfig) -> None:
        self._config = value

    @property
    def action_name(self) -> str:
        return "深蹲"

    @property
    def current_rep_frames(self) -> list[SquatFrameData]:
        return list(self._current_frames)

    @property
    def last_completed_trajectory(self) -> SquatRepTrajectory | None:
        return self._last_trajectory

    def recognize(self, pose: PoseResult) -> ActionRecognitionResult:
        angles = self._read_knee_angles(pose)
        self._left_angle = angles.left
        self._right_angle = angles.right
        self._last_angle = angles.primary

        if not angles.reliable:
            self._clear_pending()
            if self._recording_cycle:
                self._seal_trajectory(completed=False)
            self._state = SquatMachineState.waiting_person
            self._reset_cycle_tracking()
            return self._result(
                phase=ActionPhase.no_person,
                just_completed=False,
            )

        angle = angles.primary
        assert angle is not None
        just_completed = False

        self._sample_frame(pose, angle)

        if self._state == SquatMachineState.waiting_person:
            if self._try_enter(
                SquatMachineState.standing,
                angle >= self._config.standing_knee_angle,
            ):
                self._reset_cycle_tracking()
                self._note_angle(angle)
        elif self._state == SquatMachineState.standing:
            self._note_angle(angle)
            self._reached_bottom = False
            if self._try_enter(
                SquatMachineState.down,
                angle <= self._config.down_knee_angle,
            ):
                self._begin_cycle(angle)
        elif self._state == SquatMachineState.down:
            self._note_angle(angle)
            if self._try_enter(
                SquatMachineState.bottom,
                angle <= self._config.bottom_knee_angle,
            ):
                self._reached_bottom = True
            elif self._try_enter(
                SquatMachineState.standing,
                angle >= self._config.standing_knee_angle,
            ):
                # Aborted early — no count.
                self._seal_trajectory(completed=False)
                self._reset_cycle_tracking()
        elif self._state == SquatMachineState.bottom:
            self._note_angle(angle)
            self._reached_bottom = True
            if self._try_enter(
                SquatMachineState.up,
                angle >= self._config.bottom_knee_angle + 8,
            ):
                pass  # rising
        elif self._state == SquatMachineState.up:
            self._note_angle(angle)
            if self._try_enter(
                SquatMachineState.bottom,
                angle <= self._config.bottom_knee_angle,
            ):
                self._reached_bottom = True
            elif self._try_enter(
                SquatMachineState.standing,
                angle >= self._config.standing_knee_angle,
            ):
                if self._should_count_rep():
                    self._rep_count += 1
                    self._last_rep_at = datetime.now()
                    just_completed = True
                    self._seal_trajectory(completed=True)
                else:
                    self._seal_trajectory(completed=False)
                self._reset_cycle_tracking(keep_extremes_for_result=True)

        return self._result(
            phase=(
                ActionPhase.completed_rep
                if just_completed
                else self._to_phase(self._state)
            ),
            just_completed=just_completed,
        )

    def _begin_cycle(self, angle: float) -> None:
        self._recording_cycle = True
        self._cycle_started_at = datetime.now()
        self._min_angle_in_cycle = angle
        self._max_angle_in_cycle = angle
        self._reached_bottom = False
        # Keep recent standing samples if any; otherwise start fresh.

    def _sample_frame(self, pose: PoseResult, primary_angle: float) -> None:
        if not self._recording_cycle and self._state != SquatMachineState.standing:
            return
        # Always keep a short standing buffer so cycle start has context;
        # once recording, append every reliable frame.
        chain = pose.preferred_lower_body
        frame = SquatFrameData(
            timestamp=pose.timestamp,
            left_knee_angle=self._left_angle,
            right_knee_angle=self._right_angle,
            hip_y=chain.hip.y if chain is not None else None,
            knee_y=chain.knee.y if chain is not None else None,
            ankle_y=chain.ankle.y if chain is not None else None,
            primary_knee_angle=primary_angle,
        )

        if self._recording_cycle:
            self._current_frames.append(frame)
            return

        # Standing: keep last few frames as pre-roll.
        self._current_frames.append(frame)
        while len(self._current_frames) > 6:
            self._current_frames.pop(0)

    def _note_angle(self, angle: float) -> None:
        if angle < self._min_angle_in_cycle:
            self._min_angle_in_cycle = angle
        if angle > self._max_angle_in_cycle:
            self._max_angle_in_cycle = angle

    def _seal_trajectory(self, *, completed: bool) -> None:
        min_a = (
            self._min_angle_in_cycle if self._min_angle_in_cycle < 180 else None
        )
        max_a = self._max_angle_in_cycle if self._max_angle_in_cycle > 0 else None
        rom = (max_a - min_a) if (min_a is not None and max_a is not None) else None
        started = self._cycle_started_at
        duration = (
            0
            if started is None
            else int((datetime.now() - started).total_seconds() * 1000)
        )
        self._last_trajectory = SquatRepTrajectory(
            frames=list(self._current_frames),
            completed=completed,
            min_knee_angle=min_a,
            max_knee_angle=max_a,
            range_of_motion=rom,
            movement_duration_ms=duration,
        )
        self._current_frames.clear()
        self._recording_cycle = False
        self._cycle_started_at = None

    def _should_count_rep(self) -> bool:
        depth_ok = (
            self._reached_bottom
            and self._min_angle_in_cycle <= self._config.bottom_knee_angle + 2
        )
        rom = self._max_angle_in_cycle - self._min_angle_in_cycle
        rom_ok = rom >= (self._config.min_effective_range_of_motion * 0.6)
        if not depth_ok or not rom_ok:
            return False
        last = self._last_rep_at
        if last is None:
            return True
        return (
            int((datetime.now() - last).total_seconds() * 1000)
            >= self._config.min_rep_interval_ms
        )

    def _try_enter(self, next_state: SquatMachineState, condition: bool) -> bool:
        if not self._can_leave_current_state():
            return False
        return self._confirm(condition, next_state)

    def _can_leave_current_state(self) -> bool:
        entered = self._state_entered_at
        if entered is None:
            return True
        return (
            int((datetime.now() - entered).total_seconds() * 1000)
            >= self._config.min_state_duration_ms
        )

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
        self._reached_bottom = False
        self._recording_cycle = False
        if not keep_extremes_for_result:
            self._min_angle_in_cycle = 180
            self._max_angle_in_cycle = 0
            self._current_frames.clear()
            self._cycle_started_at = None

    def _to_phase(self, state: SquatMachineState) -> ActionPhase:
        if state == SquatMachineState.waiting_person:
            return ActionPhase.preparing
        if state == SquatMachineState.standing:
            return ActionPhase.standing
        if state in (SquatMachineState.down, SquatMachineState.bottom):
            return ActionPhase.squatting
        if state == SquatMachineState.up:
            return ActionPhase.rising
        return ActionPhase.preparing

    def _result(
        self,
        *,
        phase: ActionPhase,
        just_completed: bool,
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
        rom = (max_a - min_a) if (min_a is not None and max_a is not None) else None
        depth_ok = (
            self._min_angle_in_cycle <= self._config.bottom_knee_angle + 2
            and self._reached_bottom
        )
        return ActionRecognitionResult(
            phase=phase,
            machine_state=self._state,
            rep_count=self._rep_count,
            knee_angle=self._last_angle,
            left_knee_angle=self._left_angle,
            right_knee_angle=self._right_angle,
            just_completed_rep=just_completed,
            reached_bottom=self._reached_bottom or just_completed,
            depth_ok=depth_ok or just_completed,
            has_reliable_pose=self._last_angle is not None,
            rep_min_knee_angle=min_a,
            rep_max_knee_angle=max_a,
            range_of_motion=rom,
            current_rep_frames=list(self._current_frames),
            last_completed_trajectory=self._last_trajectory,
        )

    def _read_knee_angles(self, pose: PoseResult) -> _KneeAngles:
        """Prefer higher-confidence side; average when both sides are reliable."""
        left_chain = pose.lower_body(BodySide.left)
        right_chain = pose.lower_body(BodySide.right)

        left: float | None = None
        right: float | None = None
        left_conf = 0.0
        right_conf = 0.0

        if (
            left_chain is not None
            and left_chain.hip.confidence >= self._config.minimum_confidence
            and left_chain.knee.confidence >= self._config.minimum_confidence
            and left_chain.ankle.confidence >= self._config.minimum_confidence
        ):
            left = AngleUtils.calculate_angle(
                left_chain.hip,
                left_chain.knee,
                left_chain.ankle,
            )
            left_conf = (
                left_chain.hip.confidence
                + left_chain.knee.confidence
                + left_chain.ankle.confidence
            )
        if (
            right_chain is not None
            and right_chain.hip.confidence >= self._config.minimum_confidence
            and right_chain.knee.confidence >= self._config.minimum_confidence
            and right_chain.ankle.confidence >= self._config.minimum_confidence
        ):
            right = AngleUtils.calculate_angle(
                right_chain.hip,
                right_chain.knee,
                right_chain.ankle,
            )
            right_conf = (
                right_chain.hip.confidence
                + right_chain.knee.confidence
                + right_chain.ankle.confidence
            )

        if left is None and right is None:
            return _KneeAngles(left=None, right=None, primary=None, reliable=False)
        if left is not None and right is not None:
            primary = (left * left_conf + right * right_conf) / (left_conf + right_conf)
            return _KneeAngles(left=left, right=right, primary=primary, reliable=True)
        return _KneeAngles(
            left=left,
            right=right,
            primary=left if left is not None else right,
            reliable=True,
        )

    def reset(self) -> None:
        self._state = SquatMachineState.waiting_person
        self._rep_count = 0
        self._clear_pending()
        self._state_entered_at = None
        self._last_rep_at = None
        self._last_angle = None
        self._left_angle = None
        self._right_angle = None
        self._last_trajectory = None
        self._reset_cycle_tracking()

    @property
    def last_knee_angle(self) -> float | None:
        return self._last_angle
