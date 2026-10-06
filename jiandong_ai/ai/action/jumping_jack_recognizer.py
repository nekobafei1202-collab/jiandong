"""Jumping-jack recognizer: WAITING → CLOSED → OPEN → CLOSED (+1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..pose.pose_result import PoseResult
from .action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    ActionRecognizer,
    SquatMachineState,
)
from .jumping_jack_config import JumpingJackConfig


def _ms_between(later: datetime, earlier: datetime) -> int:
    return int((later - earlier).total_seconds() * 1000)


@dataclass(frozen=True)
class JumpingJackPoseMetrics:
    reliable: bool
    arms_up: bool
    arms_down: bool
    legs_apart: bool
    legs_together: bool
    leg_spread_ratio: float | None
    arm_raise_ratio: float | None
    average_confidence: float
    shoulder_width: float
    shoulder_center_x: float
    shoulder_center_y: float

    @property
    def is_open(self) -> bool:
        return self.arms_up and self.legs_apart

    @property
    def is_closed(self) -> bool:
        return self.arms_down and self.legs_together

    @classmethod
    def unreliable(cls) -> JumpingJackPoseMetrics:
        return cls(
            reliable=False,
            arms_up=False,
            arms_down=False,
            legs_apart=False,
            legs_together=False,
            leg_spread_ratio=None,
            arm_raise_ratio=None,
            average_confidence=0,
            shoulder_width=0,
            shoulder_center_x=0,
            shoulder_center_y=0,
        )

    @classmethod
    def read(
        cls, pose: PoseResult, config: JumpingJackConfig
    ) -> JumpingJackPoseMetrics:
        ls = pose.left_shoulder
        rs = pose.right_shoulder
        lw = pose.left_wrist
        rw = pose.right_wrist
        la = pose.left_ankle
        ra = pose.right_ankle
        points = [ls, rs, lw, rw, la, ra]
        usable = all(
            p is not None and p.confidence >= config.minimum_confidence
            for p in points
        )
        if not usable:
            return cls.unreliable()
        assert ls and rs and lw and rw and la and ra

        shoulder_width = abs(ls.x - rs.x)
        if shoulder_width < config.min_shoulder_width:
            return cls.unreliable()

        leg_spread_ratio = abs(la.x - ra.x) / shoulder_width
        raise_l = (ls.y - lw.y) / shoulder_width
        raise_r = (rs.y - rw.y) / shoulder_width
        down_margin = config.arm_down_shoulder_margin * shoulder_width
        confidence = sum(p.confidence for p in points) / len(points)  # type: ignore[union-attr]

        return cls(
            reliable=True,
            arms_up=lw.y < ls.y and rw.y < rs.y,
            arms_down=lw.y > ls.y + down_margin and rw.y > rs.y + down_margin,
            legs_apart=leg_spread_ratio > config.apart_leg_ratio,
            legs_together=leg_spread_ratio < config.together_leg_ratio,
            leg_spread_ratio=leg_spread_ratio,
            arm_raise_ratio=(raise_l + raise_r) / 2,
            average_confidence=confidence,
            shoulder_width=shoulder_width,
            shoulder_center_x=(ls.x + rs.x) / 2,
            shoulder_center_y=(ls.y + rs.y) / 2,
        )


@dataclass(frozen=True)
class JumpingJackFrameData:
    timestamp: datetime
    leg_spread_ratio: float | None = None
    arm_raise_ratio: float | None = None
    confidence: float = 0


@dataclass(frozen=True)
class JumpingJackRepTrajectory:
    frames: list[JumpingJackFrameData]
    completed: bool
    max_leg_spread_ratio: float | None = None
    max_arm_raise_ratio: float | None = None
    movement_duration_ms: int = 0


class JumpingJackRecognizer(ActionRecognizer):
    def __init__(self, config: JumpingJackConfig | None = None) -> None:
        self._config = config or JumpingJackConfig.defaults
        self._state = SquatMachineState.waiting_person
        self._rep_count = 0
        self._match_frames = 0
        self._pending_state: SquatMachineState | None = None
        self._state_entered_at: datetime | None = None
        self._last_rep_at: datetime | None = None
        self._cycle_started_at: datetime | None = None
        self._last_timestamp: datetime | None = None
        self._reached_open = False
        self._recording_cycle = False
        self._last_reliable = False
        self._last_leg_spread: float | None = None
        self._last_arm_raise: float | None = None
        self._max_leg_ratio_in_cycle = 0.0
        self._max_arm_raise_in_cycle = -1e9
        self._form_cue: str | None = None
        self._current_frames: list[JumpingJackFrameData] = []
        self._last_trajectory: JumpingJackRepTrajectory | None = None

    @property
    def config(self) -> JumpingJackConfig:
        return self._config

    def update_config(self, value: JumpingJackConfig) -> None:
        self._config = value

    @property
    def action_name(self) -> str:
        return "开合跳"

    @property
    def current_rep_frames(self) -> list[JumpingJackFrameData]:
        return list(self._current_frames)

    @property
    def last_completed_trajectory(self) -> JumpingJackRepTrajectory | None:
        return self._last_trajectory

    @property
    def rep_count(self) -> int:
        return self._rep_count

    def recognize(self, pose: PoseResult) -> ActionRecognitionResult:
        self._last_timestamp = pose.timestamp
        metrics = JumpingJackPoseMetrics.read(pose, self._config)
        self._last_reliable = metrics.reliable
        self._last_leg_spread = metrics.leg_spread_ratio
        self._last_arm_raise = metrics.arm_raise_ratio

        if not metrics.reliable:
            self._clear_pending()
            if self._recording_cycle:
                self._seal_trajectory(completed=False)
            self._state = SquatMachineState.waiting_person
            self._form_cue = None
            self._reset_cycle_tracking()
            return self._result(phase=ActionPhase.no_person, just_completed=False)

        just_completed = False
        self._sample_frame(pose, metrics)

        if self._state == SquatMachineState.waiting_person:
            if self._try_enter(SquatMachineState.standing, metrics.is_closed):
                self._reset_cycle_tracking()
        elif self._state == SquatMachineState.standing:
            self._update_form_cue(metrics)
            if self._try_enter(SquatMachineState.bottom, metrics.is_open):
                self._begin_cycle(metrics)
        elif self._state == SquatMachineState.bottom:
            self._form_cue = None
            self._note_metrics(metrics)
            if self._try_enter(SquatMachineState.standing, metrics.is_closed):
                if self._should_count_rep():
                    self._rep_count += 1
                    self._last_rep_at = self._now()
                    just_completed = True
                    self._seal_trajectory(completed=True)
                else:
                    self._seal_trajectory(completed=False)
                self._reset_cycle_tracking(keep_extremes_for_result=True)
        # down / up unused

        return self._result(
            phase=(
                ActionPhase.completed_rep
                if just_completed
                else self._to_phase(self._state)
            ),
            just_completed=just_completed,
        )

    def _now(self) -> datetime:
        return self._last_timestamp or datetime.now()

    def _update_form_cue(self, m: JumpingJackPoseMetrics) -> None:
        if m.arms_up and not m.legs_apart:
            self._form_cue = "双腿分开"
        elif m.legs_apart and not m.arms_up:
            self._form_cue = "双臂举过头顶"
        else:
            self._form_cue = None

    def _begin_cycle(self, m: JumpingJackPoseMetrics) -> None:
        self._recording_cycle = True
        self._cycle_started_at = self._now()
        self._reached_open = True
        self._max_leg_ratio_in_cycle = m.leg_spread_ratio or 0
        self._max_arm_raise_in_cycle = (
            m.arm_raise_ratio if m.arm_raise_ratio is not None else -1e9
        )

    def _sample_frame(
        self, pose: PoseResult, m: JumpingJackPoseMetrics
    ) -> None:
        if (
            not self._recording_cycle
            and self._state != SquatMachineState.standing
        ):
            return
        frame = JumpingJackFrameData(
            timestamp=pose.timestamp,
            leg_spread_ratio=m.leg_spread_ratio,
            arm_raise_ratio=m.arm_raise_ratio,
            confidence=m.average_confidence,
        )
        if self._recording_cycle:
            self._current_frames.append(frame)
            return
        self._current_frames.append(frame)
        while len(self._current_frames) > 6:
            self._current_frames.pop(0)

    def _note_metrics(self, m: JumpingJackPoseMetrics) -> None:
        leg = m.leg_spread_ratio
        if leg is not None and leg > self._max_leg_ratio_in_cycle:
            self._max_leg_ratio_in_cycle = leg
        raise_ = m.arm_raise_ratio
        if raise_ is not None and raise_ > self._max_arm_raise_in_cycle:
            self._max_arm_raise_in_cycle = raise_

    def _seal_trajectory(self, *, completed: bool) -> None:
        started = self._cycle_started_at
        duration = (
            0 if started is None else _ms_between(self._now(), started)
        )
        self._last_trajectory = JumpingJackRepTrajectory(
            frames=list(self._current_frames),
            completed=completed,
            max_leg_spread_ratio=(
                self._max_leg_ratio_in_cycle
                if self._max_leg_ratio_in_cycle > 0
                else None
            ),
            max_arm_raise_ratio=(
                self._max_arm_raise_in_cycle
                if self._max_arm_raise_in_cycle > -1e8
                else None
            ),
            movement_duration_ms=duration,
        )
        self._current_frames.clear()
        self._recording_cycle = False
        self._cycle_started_at = None

    def _should_count_rep(self) -> bool:
        open_ok = (
            self._reached_open
            and self._max_leg_ratio_in_cycle >= self._config.apart_leg_ratio
            and self._max_arm_raise_in_cycle > 0
        )
        if not open_ok:
            return False
        last = self._last_rep_at
        if last is None:
            return True
        return _ms_between(self._now(), last) >= self._config.min_rep_interval_ms

    def _try_enter(self, next_state: SquatMachineState, condition: bool) -> bool:
        if not self._can_leave_current_state():
            return False
        return self._confirm(condition, next_state)

    def _can_leave_current_state(self) -> bool:
        entered = self._state_entered_at
        if entered is None:
            return True
        return _ms_between(self._now(), entered) >= self._config.min_state_duration_ms

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
        self._state_entered_at = self._now()
        self._clear_pending()

    def _clear_pending(self) -> None:
        self._pending_state = None
        self._match_frames = 0

    def _reset_cycle_tracking(self, *, keep_extremes_for_result: bool = False) -> None:
        self._reached_open = False
        self._recording_cycle = False
        if not keep_extremes_for_result:
            self._max_leg_ratio_in_cycle = 0.0
            self._max_arm_raise_in_cycle = -1e9
            self._current_frames.clear()
            self._cycle_started_at = None

    def _to_phase(self, state: SquatMachineState) -> ActionPhase:
        if state == SquatMachineState.waiting_person:
            return ActionPhase.preparing
        if state == SquatMachineState.standing:
            return ActionPhase.standing
        if state == SquatMachineState.bottom:
            return ActionPhase.squatting
        return ActionPhase.rising

    def _result(
        self, *, phase: ActionPhase, just_completed: bool
    ) -> ActionRecognitionResult:
        return ActionRecognitionResult(
            phase=phase,
            machine_state=self._state,
            rep_count=self._rep_count,
            knee_angle=None,
            just_completed_rep=just_completed,
            reached_bottom=self._reached_open or just_completed,
            depth_ok=(
                (self._reached_open and self._max_leg_ratio_in_cycle >= self._config.apart_leg_ratio)
                or just_completed
            ),
            has_reliable_pose=self._last_reliable,
            last_completed_trajectory=None,
            form_cue=self._form_cue,
            leg_spread_ratio=(
                (
                    self._max_leg_ratio_in_cycle
                    if self._max_leg_ratio_in_cycle > 0
                    else self._last_leg_spread
                )
                if just_completed
                else self._last_leg_spread
            ),
            arm_raise_ratio=(
                (
                    self._max_arm_raise_in_cycle
                    if self._max_arm_raise_in_cycle > -1e8
                    else self._last_arm_raise
                )
                if just_completed
                else self._last_arm_raise
            ),
        )

    def reset(self) -> None:
        self._state = SquatMachineState.waiting_person
        self._rep_count = 0
        self._clear_pending()
        self._state_entered_at = None
        self._last_rep_at = None
        self._last_timestamp = None
        self._last_reliable = False
        self._last_leg_spread = None
        self._last_arm_raise = None
        self._last_trajectory = None
        self._form_cue = None
        self._reset_cycle_tracking()
