"""Push-up recognizer: WAITING → HIGH → DOWN → BOTTOM → UP → HIGH (+1).

High plank reuses SquatMachineState.standing. A rep counts only after
BOTTOM (elbow ≤ 90°) with hard rules held: body line ±15°, flare ≤ 70°,
shoulder and hip travelling together. Severe violations abort with no count.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median

from ..pose.keypoint import BodySide, Keypoint
from ..pose.pose_result import PoseResult
from ..utils.angle_utils import AngleUtils
from .action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    ActionRecognizer,
    SquatMachineState,
)
from .pushup_config import PushupConfig
from .pushup_frame_data import PushupFrameData, PushupRepTrajectory


@dataclass(frozen=True)
class _PushupMetrics:
    left_elbow: float | None
    right_elbow: float | None
    primary_elbow: float | None
    body_line: float | None
    flare: float | None
    hip_offset: float | None
    hip_y: float | None
    shoulder_y: float | None
    neck_reach: bool
    shrugged: bool
    reliable: bool


class PushupRecognizer(ActionRecognizer):
    def __init__(self, config: PushupConfig | None = None) -> None:
        self._config = config if config is not None else PushupConfig.defaults
        self._state = SquatMachineState.waiting_person
        self._rep_count = 0
        self._match_frames = 0
        self._pending_state: SquatMachineState | None = None
        self._state_entered_at: datetime | None = None
        self._last_rep_at: datetime | None = None
        self._cycle_started_at: datetime | None = None
        self._last_elbow: float | None = None
        self._left_elbow: float | None = None
        self._right_elbow: float | None = None
        self._last_body_line: float | None = None
        self._last_flare: float | None = None
        self._form_cue: str | None = None
        self._form_abort = False
        self._violation_frames = 0
        self._pending_violation: str | None = None
        self._min_angle_in_cycle = 180.0
        self._max_angle_in_cycle = 0.0
        self._min_hip_y = 1e9
        self._max_hip_y = -1e9
        self._min_shoulder_y = 1e9
        self._max_shoulder_y = -1e9
        self._reached_bottom = False
        self._recording_cycle = False
        self._current_frames: list[PushupFrameData] = []
        self._last_trajectory: PushupRepTrajectory | None = None
        self._angle_window: list[float] = []
        self._fb_peak_y: float | None = None
        self._fb_trough_y: float | None = None
        self._fb_at_bottom = False
        self._fb_machine_engaged = False

    @property
    def config(self) -> PushupConfig:
        return self._config

    def update_config(self, value: PushupConfig) -> None:
        self._config = value

    @property
    def action_name(self) -> str:
        return "俯卧撑"

    @property
    def current_rep_frames(self) -> list[PushupFrameData]:
        return list(self._current_frames)

    @property
    def last_completed_trajectory(self) -> PushupRepTrajectory | None:
        return self._last_trajectory

    def recognize(self, pose: PoseResult) -> ActionRecognitionResult:
        metrics = self._read_metrics(pose)
        self._left_elbow = metrics.left_elbow
        self._right_elbow = metrics.right_elbow
        self._last_elbow = metrics.primary_elbow
        self._last_body_line = metrics.body_line
        self._last_flare = metrics.flare

        if not metrics.reliable:
            self._clear_pending()
            self._angle_window.clear()
            self._reset_shoulder_fallback(None)
            if self._recording_cycle:
                if self._form_cue is None:
                    self._form_cue = "请调整位置，确保全身进入摄像头"
                self._seal_trajectory(completed=False)
            self._state = SquatMachineState.waiting_person
            self._reset_cycle_tracking()
            return self._result(
                phase=ActionPhase.no_person,
                just_completed=False,
            )

        angle = metrics.primary_elbow
        assert angle is not None
        if not self._config.strict:
            # 轻松模式单帧确认，改用 3 帧中值防抖；_last_elbow 同步为平滑值，
            # 保证 HUD 与轨迹所见即状态机所用。
            angle = self._smooth_angle(angle)
            self._last_elbow = angle
        just_completed = False

        self._sample_frame(pose, angle, metrics)

        if self._state == SquatMachineState.waiting_person:
            self._form_cue = None
            if self._try_enter(
                SquatMachineState.standing,
                angle >= self._config.high_elbow_angle,
            ):
                self._reset_cycle_tracking()
                self._note_angle(angle)
                self._note_travel(metrics)
        elif self._state == SquatMachineState.standing:
            self._note_angle(angle)
            self._reached_bottom = False
            self._form_cue = self._severe_cue(metrics)
            if self._try_enter(
                SquatMachineState.down,
                angle <= self._config.down_elbow_angle,
            ):
                self._begin_cycle(angle)
                self._note_travel(metrics)
        elif self._state == SquatMachineState.down:
            self._note_angle(angle)
            self._note_travel(metrics)
            if not self._maybe_abort(metrics):
                if self._try_enter(
                    SquatMachineState.bottom,
                    angle <= self._config.bottom_elbow_angle,
                ):
                    self._reached_bottom = True
                elif self._try_enter(
                    SquatMachineState.standing,
                    angle >= self._config.high_elbow_angle,
                ):
                    self._form_cue = (
                        self._form_cue if self._form_abort else "半程偷懒"
                    )
                    self._form_abort = True
                    self._seal_trajectory(completed=False)
                    self._reset_cycle_tracking()
        elif self._state == SquatMachineState.bottom:
            self._note_angle(angle)
            self._note_travel(metrics)
            self._reached_bottom = True
            if not self._maybe_abort(metrics):
                if self._try_enter(
                    SquatMachineState.up,
                    angle >= self._config.bottom_elbow_angle + 8,
                ):
                    pass  # rising
        elif self._state == SquatMachineState.up:
            self._note_angle(angle)
            self._note_travel(metrics)
            if not self._maybe_abort(metrics):
                if self._try_enter(
                    SquatMachineState.bottom,
                    angle <= self._config.bottom_elbow_angle,
                ):
                    self._reached_bottom = True
                elif self._try_enter(
                    SquatMachineState.standing,
                    angle >= self._config.high_elbow_angle,
                ):
                    if self._should_count_rep():
                        self._rep_count += 1
                        self._last_rep_at = datetime.now()
                        just_completed = True
                        self._form_cue = None
                        self._seal_trajectory(completed=True)
                    else:
                        if self._form_cue is None:
                            self._form_cue = "半程偷懒"
                        self._seal_trajectory(completed=False)
                    self._reset_cycle_tracking(keep_extremes_for_result=True)

        if not self._config.strict:
            if just_completed:
                # 肘角状态机已计数，肩线滞回同步回顶部，避免同一次重复计。
                self._reset_shoulder_fallback(metrics.shoulder_y)
            else:
                just_completed = self._shoulder_fallback(metrics)

        return self._result(
            phase=(
                ActionPhase.completed_rep
                if just_completed
                else self._to_phase(self._state)
            ),
            just_completed=just_completed,
        )

    def _reset_shoulder_fallback(self, shoulder_y: float | None) -> None:
        self._fb_peak_y = shoulder_y
        self._fb_trough_y = shoulder_y
        self._fb_at_bottom = False
        self._fb_machine_engaged = False

    def _shoulder_fallback(self, metrics: _PushupMetrics) -> bool:
        """轻松模式兜底：肘角被拍摄角度压扁时，用肩点 y 的滞回往复计数。

        仅在肘角状态机本次 excursion 未介入（始终停在 standing/waiting）
        时才允许计数，避免与状态机重复计同一次。
        """
        sy = metrics.shoulder_y
        if sy is None:
            return False
        travel = self._config.lenient_shoulder_travel
        if self._fb_peak_y is None or self._fb_trough_y is None:
            self._reset_shoulder_fallback(sy)
            return False
        if self._state in (
            SquatMachineState.down,
            SquatMachineState.bottom,
            SquatMachineState.up,
        ):
            self._fb_machine_engaged = True
        if not self._fb_at_bottom:
            self._fb_peak_y = min(self._fb_peak_y, sy)
            if sy - self._fb_peak_y >= travel:
                self._fb_at_bottom = True
                self._fb_trough_y = sy
            return False
        self._fb_trough_y = max(self._fb_trough_y, sy)
        if self._fb_trough_y - sy < travel * 0.6:
            return False
        # 已回升足够：一次 excursion 结束。
        engaged = self._fb_machine_engaged
        amplitude = self._fb_trough_y - self._fb_peak_y
        self._reset_shoulder_fallback(sy)
        if engaged or amplitude < travel:
            return False
        last = self._last_rep_at
        if last is not None and (
            int((datetime.now() - last).total_seconds() * 1000)
            < self._config.min_rep_interval_ms
        ):
            return False
        self._rep_count += 1
        self._last_rep_at = datetime.now()
        self._form_cue = None
        return True

    def _smooth_angle(self, angle: float) -> float:
        window = self._angle_window
        window.append(angle)
        if len(window) > 3:
            window.pop(0)
        return float(median(window))

    def _begin_cycle(self, angle: float) -> None:
        self._recording_cycle = True
        self._cycle_started_at = datetime.now()
        self._min_angle_in_cycle = angle
        self._max_angle_in_cycle = angle
        self._reached_bottom = False
        self._form_abort = False
        self._violation_frames = 0
        self._pending_violation = None
        self._min_hip_y = 1e9
        self._max_hip_y = -1e9
        self._min_shoulder_y = 1e9
        self._max_shoulder_y = -1e9

    def _sample_frame(
        self,
        pose: PoseResult,
        primary_angle: float,
        metrics: _PushupMetrics,
    ) -> None:
        if not self._recording_cycle and self._state != SquatMachineState.standing:
            return
        line = pose.preferred_body_line
        arm = pose.preferred_upper_body
        shoulder_y = None
        if arm is not None:
            shoulder_y = arm.shoulder.y
        elif line is not None:
            shoulder_y = line.shoulder.y
        hip_y = None
        if line is not None:
            hip_y = line.hip.y
        elif pose.left_hip is not None:
            hip_y = pose.left_hip.y
        elif pose.right_hip is not None:
            hip_y = pose.right_hip.y
        frame = PushupFrameData(
            timestamp=pose.timestamp,
            left_elbow_angle=self._left_elbow,
            right_elbow_angle=self._right_elbow,
            primary_elbow_angle=primary_angle,
            body_line_angle=metrics.body_line,
            elbow_flare_angle=metrics.flare,
            shoulder_torso_angle=metrics.flare,
            shoulder_y=shoulder_y,
            hip_y=hip_y,
            ankle_y=line.ankle.y if line is not None else None,
            hip_offset=metrics.hip_offset,
            neck_reach=metrics.neck_reach,
            shrugged=metrics.shrugged,
        )

        if self._recording_cycle:
            self._current_frames.append(frame)
            return

        self._current_frames.append(frame)
        while len(self._current_frames) > 6:
            self._current_frames.pop(0)

    def _note_angle(self, angle: float) -> None:
        if angle < self._min_angle_in_cycle:
            self._min_angle_in_cycle = angle
        if angle > self._max_angle_in_cycle:
            self._max_angle_in_cycle = angle

    def _note_travel(self, metrics: _PushupMetrics) -> None:
        hip = metrics.hip_y
        shoulder = metrics.shoulder_y
        if hip is not None:
            if hip < self._min_hip_y:
                self._min_hip_y = hip
            if hip > self._max_hip_y:
                self._max_hip_y = hip
        if shoulder is not None:
            if shoulder < self._min_shoulder_y:
                self._min_shoulder_y = shoulder
            if shoulder > self._max_shoulder_y:
                self._max_shoulder_y = shoulder

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
        min_body: float | None = None
        for f in self._current_frames:
            b = f.body_line_angle
            if b is None:
                continue
            min_body = b if min_body is None else (b if b < min_body else min_body)
        self._last_trajectory = PushupRepTrajectory(
            frames=list(self._current_frames),
            completed=completed,
            min_elbow_angle=min_a,
            max_elbow_angle=max_a,
            range_of_motion=rom,
            movement_duration_ms=duration,
            min_body_line_angle=min_body,
            abort_reason=None if completed else self._form_cue,
        )
        self._current_frames.clear()
        self._recording_cycle = False
        self._cycle_started_at = None

    def _maybe_abort(self, metrics: _PushupMetrics) -> bool:
        cue = self._severe_cue(metrics)
        if not self._config.strict:
            # 轻松模式：永不中止计数，违规只作为 HUD 提示。
            if cue is not None:
                self._form_cue = cue
            return False
        if cue is None:
            self._violation_frames = 0
            self._pending_violation = None
            return False
        if self._pending_violation != cue:
            self._pending_violation = cue
            self._violation_frames = 1
        else:
            self._violation_frames += 1
        if self._violation_frames < self._config.state_confirm_frames:
            self._form_cue = cue
            return False
        self._form_cue = cue
        self._form_abort = True
        self._seal_trajectory(completed=False)
        self._apply_state(SquatMachineState.standing)
        self._reset_cycle_tracking()
        return True

    def _severe_cue(self, m: _PushupMetrics) -> str | None:
        if m.flare is not None and m.flare > self._config.max_elbow_flare_degrees:
            return "飞肘"
        if m.body_line is not None:
            deviation = abs(self._config.ideal_body_line_angle - m.body_line)
            if deviation > self._config.body_line_tolerance_degrees:
                if (m.hip_offset or 0) < 0:
                    return "撅臀"
                return "塌腰"
        if m.shrugged:
            return "耸肩"
        if m.neck_reach:
            return "伸颈够低"
        return None

    def _static_hips(self) -> bool:
        if self._max_hip_y < -1e8 or self._min_hip_y > 1e8:
            return False
        if self._max_shoulder_y < -1e8 or self._min_shoulder_y > 1e8:
            return False
        hip_travel = self._max_hip_y - self._min_hip_y
        shoulder_travel = self._max_shoulder_y - self._min_shoulder_y
        rom = self._max_angle_in_cycle - self._min_angle_in_cycle
        if rom < self._config.min_effective_range_of_motion * 0.45:
            return False
        needed = max(
            self._config.min_hip_travel,
            shoulder_travel * self._config.min_hip_travel_ratio,
        )
        return hip_travel < needed

    def _should_count_rep(self) -> bool:
        if self._form_abort:
            return False
        if self._config.strict and self._static_hips():
            self._form_cue = "半程偷懒"
            self._form_abort = True
            return False
        depth_ok = (
            self._reached_bottom
            and self._min_angle_in_cycle <= self._config.bottom_elbow_angle + 2
        )
        rom = self._max_angle_in_cycle - self._min_angle_in_cycle
        rom_ok = rom >= (self._config.min_effective_range_of_motion * 0.6)
        if not depth_ok or not rom_ok:
            self._form_cue = "半程偷懒"
            return False
        if self._config.strict:
            for f in self._current_frames:
                cue = self._severe_cue(
                    _PushupMetrics(
                        left_elbow=f.left_elbow_angle,
                        right_elbow=f.right_elbow_angle,
                        primary_elbow=f.primary_elbow_angle,
                        body_line=f.body_line_angle,
                        flare=f.elbow_flare_angle,
                        hip_offset=f.hip_offset,
                        hip_y=f.hip_y,
                        shoulder_y=f.shoulder_y,
                        neck_reach=f.neck_reach,
                        shrugged=f.shrugged,
                        reliable=True,
                    )
                )
                if cue is not None:
                    self._form_cue = cue
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
        self._violation_frames = 0
        self._pending_violation = None
        if not keep_extremes_for_result:
            self._min_angle_in_cycle = 180
            self._max_angle_in_cycle = 0
            self._current_frames.clear()
            self._cycle_started_at = None
            self._min_hip_y = 1e9
            self._max_hip_y = -1e9
            self._min_shoulder_y = 1e9
            self._max_shoulder_y = -1e9
            self._form_abort = False

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
            else self._last_elbow
        )
        max_a = (
            self._max_angle_in_cycle
            if self._max_angle_in_cycle > 0
            else self._last_elbow
        )
        rom = (max_a - min_a) if (min_a is not None and max_a is not None) else None
        depth_ok = (
            self._min_angle_in_cycle <= self._config.bottom_elbow_angle + 2
            and self._reached_bottom
        )
        return ActionRecognitionResult(
            phase=phase,
            machine_state=self._state,
            rep_count=self._rep_count,
            knee_angle=self._last_elbow,
            left_knee_angle=self._left_elbow,
            right_knee_angle=self._right_elbow,
            just_completed_rep=just_completed,
            reached_bottom=self._reached_bottom or just_completed,
            depth_ok=depth_ok or just_completed,
            has_reliable_pose=self._last_elbow is not None,
            rep_min_knee_angle=min_a,
            rep_max_knee_angle=max_a,
            range_of_motion=rom,
            elbow_angle=self._last_elbow,
            left_elbow_angle=self._left_elbow,
            right_elbow_angle=self._right_elbow,
            body_line_angle=self._last_body_line,
            elbow_flare_angle=self._last_flare,
            current_pushup_frames=list(self._current_frames),
            last_pushup_trajectory=self._last_trajectory,
            form_cue=self._form_cue,
        )

    def _read_metrics(self, pose: PoseResult) -> _PushupMetrics:
        left_chain = pose.upper_body(BodySide.left)
        right_chain = pose.upper_body(BodySide.right)

        left: float | None = None
        right: float | None = None
        left_conf = 0.0
        right_conf = 0.0

        if (
            left_chain is not None
            and left_chain.shoulder.confidence >= self._config.minimum_confidence
            and left_chain.elbow.confidence >= self._config.minimum_confidence
            and left_chain.wrist.confidence >= self._config.minimum_confidence
        ):
            left = AngleUtils.calculate_angle(
                left_chain.shoulder,
                left_chain.elbow,
                left_chain.wrist,
            )
            left_conf = (
                left_chain.shoulder.confidence
                + left_chain.elbow.confidence
                + left_chain.wrist.confidence
            )
        if (
            right_chain is not None
            and right_chain.shoulder.confidence >= self._config.minimum_confidence
            and right_chain.elbow.confidence >= self._config.minimum_confidence
            and right_chain.wrist.confidence >= self._config.minimum_confidence
        ):
            right = AngleUtils.calculate_angle(
                right_chain.shoulder,
                right_chain.elbow,
                right_chain.wrist,
            )
            right_conf = (
                right_chain.shoulder.confidence
                + right_chain.elbow.confidence
                + right_chain.wrist.confidence
            )

        primary: float | None = None
        arms_ok = False
        if left is not None and right is not None:
            if not self._config.strict and abs(left - right) > 30:
                # 轻松模式：两臂角度严重分歧时，低置信臂（侧拍遮挡臂）多半是
                # 垃圾值，会拉偏加权平均；直接信任高置信臂。
                primary = left if left_conf >= right_conf else right
            else:
                primary = (left * left_conf + right * right_conf) / (
                    left_conf + right_conf
                )
            arms_ok = True
        elif left is not None or right is not None:
            primary = left if left is not None else right
            arms_ok = True

        left_hip = pose.left_hip
        right_hip = pose.right_hip
        hip_ok = (
            left_hip is not None
            and left_hip.confidence >= self._config.minimum_confidence
        ) or (
            right_hip is not None
            and right_hip.confidence >= self._config.minimum_confidence
        )

        body_line: float | None = None
        line_samples: list[float] = []
        left_line = pose.body_line(BodySide.left)
        right_line = pose.body_line(BodySide.right)
        if (
            left_line is not None
            and left_line.shoulder.confidence >= self._config.minimum_confidence
            and left_line.hip.confidence >= self._config.minimum_confidence
            and left_line.ankle.confidence >= self._config.minimum_confidence
        ):
            line_samples.append(
                AngleUtils.calculate_angle(
                    left_line.shoulder, left_line.hip, left_line.ankle
                )
            )
        if (
            right_line is not None
            and right_line.shoulder.confidence >= self._config.minimum_confidence
            and right_line.hip.confidence >= self._config.minimum_confidence
            and right_line.ankle.confidence >= self._config.minimum_confidence
        ):
            line_samples.append(
                AngleUtils.calculate_angle(
                    right_line.shoulder, right_line.hip, right_line.ankle
                )
            )
        if line_samples:
            body_line = sum(line_samples) / len(line_samples)

        flare: float | None = None
        flare_samples: list[float] = []

        def add_flare(
            hip: Keypoint | None,
            shoulder: Keypoint | None,
            elbow: Keypoint | None,
        ) -> None:
            if hip is None or shoulder is None or elbow is None:
                return
            if (
                hip.confidence < self._config.minimum_confidence
                or shoulder.confidence < self._config.minimum_confidence
                or elbow.confidence < self._config.minimum_confidence
            ):
                return
            flare_samples.append(AngleUtils.calculate_angle(hip, shoulder, elbow))

        add_flare(pose.left_hip, pose.left_shoulder, pose.left_elbow)
        add_flare(pose.right_hip, pose.right_shoulder, pose.right_elbow)
        if flare_samples:
            flare = sum(flare_samples) / len(flare_samples)

        hip_offset: float | None = None
        line = pose.preferred_body_line
        if (
            line is not None
            and line.shoulder.confidence >= self._config.minimum_confidence
            and line.hip.confidence >= self._config.minimum_confidence
            and line.ankle.confidence >= self._config.minimum_confidence
        ):
            sx = line.shoulder.x
            sy = line.shoulder.y
            hip_offset = (line.ankle.x - sx) * (line.hip.y - sy) - (
                line.ankle.y - sy
            ) * (line.hip.x - sx)

        shoulder = None
        preferred_arm = pose.preferred_upper_body
        if preferred_arm is not None:
            shoulder = preferred_arm.shoulder
        elif pose.left_shoulder is not None:
            shoulder = pose.left_shoulder
        elif pose.right_shoulder is not None:
            shoulder = pose.right_shoulder
        hip = left_hip if left_hip is not None else right_hip
        nose = pose.nose
        neck_reach = False
        if (
            nose is not None
            and shoulder is not None
            and nose.confidence >= self._config.minimum_confidence
            and shoulder.confidence >= self._config.minimum_confidence
        ):
            neck_reach = (nose.y - shoulder.y) > self._config.neck_reach_y

        shrugged = False
        if shoulder is not None and shoulder.confidence >= self._config.minimum_confidence:
            ears: list[Keypoint] = []
            if pose.left_ear is not None:
                ears.append(pose.left_ear)
            if pose.right_ear is not None:
                ears.append(pose.right_ear)
            for ear in ears:
                if ear.confidence < self._config.minimum_confidence:
                    continue
                if shoulder.distance_to(ear) < self._config.shrug_ear_distance:
                    shrugged = True
                    break

        return _PushupMetrics(
            left_elbow=left,
            right_elbow=right,
            primary_elbow=primary,
            body_line=body_line,
            flare=flare,
            hip_offset=hip_offset,
            hip_y=hip.y if hip is not None else (line.hip.y if line is not None else None),
            shoulder_y=shoulder.y if shoulder is not None else None,
            neck_reach=neck_reach,
            shrugged=shrugged,
            # 严格模式要求髋部可见；轻松模式手臂可信即可（正面拍/髋部出画也能识别）。
            reliable=arms_ok and (hip_ok if self._config.strict else True),
        )

    def reset(self) -> None:
        self._state = SquatMachineState.waiting_person
        self._rep_count = 0
        self._clear_pending()
        self._state_entered_at = None
        self._last_rep_at = None
        self._last_elbow = None
        self._left_elbow = None
        self._right_elbow = None
        self._last_body_line = None
        self._last_flare = None
        self._form_cue = None
        self._last_trajectory = None
        self._angle_window.clear()
        self._reset_shoulder_fallback(None)
        self._reset_cycle_tracking()
