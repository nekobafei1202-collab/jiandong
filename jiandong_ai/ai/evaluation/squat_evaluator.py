"""Cycle-based squat quality evaluation.

Scores only after a completed rep (or shallow abort). Never single-frame.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    SquatMachineState,
)
from ..action.squat_config import SquatConfig
from ..action.squat_frame_data import SquatFrameData, SquatRepTrajectory
from ..pose.pose_result import PoseResult
from .action_evaluator import ActionEvaluator, EvaluationResult, SquatEvaluationResult
from .personal_baseline import PersonalBaseline


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class SquatEvaluator(ActionEvaluator):
    def __init__(self) -> None:
        self._last_detail = SquatEvaluationResult(
            score=0,
            is_correct=False,
            feedback="等待开始训练",
            min_knee_angle=None,
            max_knee_angle=None,
            range_of_motion=None,
            movement_duration=0,
            stability_score=0,
            range_score=0,
            rhythm_score=0,
        )
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._rep_angles: list[float] = []
        self._side_deltas: list[float] = []
        self._rep_frames: list[SquatFrameData] = []
        self._rep_started_at: datetime | None = None
        self._prev_machine: SquatMachineState | None = None
        self._min_angle_in_rep: float | None = None
        self._max_angle_in_rep: float | None = None

    @property
    def last_result(self) -> EvaluationResult:
        return self._last

    @property
    def last_detail(self) -> SquatEvaluationResult:
        return self._last_detail

    def reset(self) -> None:
        self._last_detail = SquatEvaluationResult(
            score=0,
            is_correct=False,
            feedback="等待开始训练",
            min_knee_angle=None,
            max_knee_angle=None,
            range_of_motion=None,
            movement_duration=0,
            stability_score=0,
            range_score=0,
            rhythm_score=0,
        )
        self._last = self._last_detail.as_evaluation
        self._clear_rep_window()
        self._prev_machine = None

    def evaluate(
        self,
        *,
        action: ActionRecognitionResult,
        pose: PoseResult,
        baseline: PersonalBaseline | None = None,
        config: SquatConfig | None = None,
    ) -> EvaluationResult:
        if baseline is None:
            baseline = PersonalBaseline.defaults
        if config is None:
            config = SquatConfig.defaults

        if action.phase == ActionPhase.no_person or not action.has_reliable_pose:
            self._last = EvaluationResult(
                score=self._last.score,
                amplitude_score=self._last.amplitude_score,
                stability_score=self._last.stability_score,
                rhythm_score=self._last.rhythm_score,
                feedback="请调整位置，确保全身进入摄像头",
                is_correct=self._last.is_correct,
                knee_angle_min=self._last.knee_angle_min,
                knee_angle_max=self._last.knee_angle_max,
                range_of_motion=self._last.range_of_motion,
                movement_duration_ms=self._last.movement_duration_ms,
            )
            self._prev_machine = action.machine_state
            return self._last

        self._track_rep_samples(action=action)

        if action.just_completed_rep:
            traj = action.last_completed_trajectory
            self._absorb_trajectory(traj)
            self._last_detail = self._score_completed_rep(config=config)
            self._last = self._last_detail.as_evaluation
            self._clear_rep_window()
            self._prev_machine = action.machine_state
            return self._last

        # Returned to stand without counting ⇒ depth / ROM failed this cycle.
        aborted_shallow = (
            self._prev_machine is not None
            and self._prev_machine != SquatMachineState.standing
            and self._prev_machine != SquatMachineState.waiting_person
            and action.machine_state == SquatMachineState.standing
            and not action.just_completed_rep
            and self._min_angle_in_rep is not None
        )

        if aborted_shallow:
            traj = action.last_completed_trajectory
            self._absorb_trajectory(traj)
            rom = self._range_of_motion()
            self._last_detail = SquatEvaluationResult(
                score=self._last.score,
                is_correct=False,
                feedback="下蹲幅度可以再大一些",
                min_knee_angle=self._min_angle_in_rep,
                max_knee_angle=self._max_angle_in_rep,
                range_of_motion=rom,
                movement_duration=self._elapsed_ms(),
                stability_score=self._last.stability_score,
                range_score=self._last.amplitude_score,
                rhythm_score=self._last.rhythm_score,
            )
            self._last = self._last_detail.as_evaluation
            self._clear_rep_window()
            self._prev_machine = action.machine_state
            return self._last

        self._last = EvaluationResult(
            score=self._last.score,
            amplitude_score=self._last.amplitude_score,
            stability_score=self._last.stability_score,
            rhythm_score=self._last.rhythm_score,
            feedback=self._live_feedback(action, config),
            is_correct=self._last.is_correct,
            knee_angle_min=self._min_angle_in_rep or action.rep_min_knee_angle,
            knee_angle_max=self._max_angle_in_rep or action.rep_max_knee_angle,
            range_of_motion=self._range_of_motion() or action.range_of_motion,
            movement_duration_ms=self._elapsed_ms(),
        )
        self._prev_machine = action.machine_state
        return self._last

    def _absorb_trajectory(self, traj: SquatRepTrajectory | None) -> None:
        if traj is None or not traj.frames:
            return
        self._rep_frames.clear()
        self._rep_frames.extend(traj.frames)
        if traj.min_knee_angle is not None:
            self._min_angle_in_rep = traj.min_knee_angle
        if traj.max_knee_angle is not None:
            self._max_angle_in_rep = traj.max_knee_angle
        if traj.movement_duration_ms > 0:
            self._rep_started_at = datetime.now() - timedelta(
                milliseconds=traj.movement_duration_ms
            )
        self._rep_angles.clear()
        self._rep_angles.extend(
            f.primary_knee_angle
            for f in traj.frames
            if f.primary_knee_angle is not None
        )
        self._side_deltas.clear()
        for f in traj.frames:
            if f.left_knee_angle is not None and f.right_knee_angle is not None:
                self._side_deltas.append(abs(f.left_knee_angle - f.right_knee_angle))

    def _track_rep_samples(self, *, action: ActionRecognitionResult) -> None:
        angle = action.knee_angle
        entering_down = (
            self._prev_machine == SquatMachineState.standing
            and action.machine_state == SquatMachineState.down
        )

        if entering_down or (
            self._rep_started_at is None
            and action.machine_state
            in (
                SquatMachineState.down,
                SquatMachineState.bottom,
                SquatMachineState.up,
            )
        ):
            self._rep_angles.clear()
            self._side_deltas.clear()
            self._rep_frames.clear()
            self._rep_started_at = datetime.now()
            self._min_angle_in_rep = angle
            self._max_angle_in_rep = angle

        if angle is not None and (
            action.machine_state
            in (
                SquatMachineState.down,
                SquatMachineState.bottom,
                SquatMachineState.up,
            )
            or action.just_completed_rep
        ):
            self._rep_angles.append(angle)
            self._min_angle_in_rep = (
                angle
                if self._min_angle_in_rep is None
                else min(self._min_angle_in_rep, angle)
            )
            self._max_angle_in_rep = (
                angle
                if self._max_angle_in_rep is None
                else max(self._max_angle_in_rep, angle)
            )

        if action.left_knee_angle is not None and action.right_knee_angle is not None:
            self._side_deltas.append(
                abs(action.left_knee_angle - action.right_knee_angle)
            )

        if action.current_rep_frames:
            self._rep_frames.clear()
            self._rep_frames.extend(action.current_rep_frames)

    def _score_completed_rep(self, *, config: SquatConfig) -> SquatEvaluationResult:
        range_score = self._score_range(config)
        stability = self._score_stability()
        rhythm = self._score_rhythm(config)
        score = int(
            round(
                (range_score * config.range_score_weight)
                + (stability * config.stability_score_weight)
                + (rhythm * config.rhythm_score_weight)
            )
        )
        score = int(_clamp(score, 0, 100))
        rom = self._range_of_motion()
        deep_enough = (self._min_angle_in_rep or 999) <= config.bottom_knee_angle + 2
        rom_ok = (rom or 0) >= config.min_effective_range_of_motion * 0.75
        is_correct = score >= config.correct_score_threshold and deep_enough and rom_ok

        return SquatEvaluationResult(
            score=score,
            is_correct=is_correct,
            feedback=self._feedback_for(
                score=score,
                range_score=range_score,
                stability=stability,
                rhythm=rhythm,
                config=config,
            ),
            min_knee_angle=self._min_angle_in_rep,
            max_knee_angle=self._max_angle_in_rep,
            range_of_motion=rom,
            movement_duration=self._elapsed_ms(),
            stability_score=stability,
            range_score=range_score,
            rhythm_score=rhythm,
        )

    def _range_of_motion(self) -> float | None:
        min_a = self._min_angle_in_rep
        max_a = self._max_angle_in_rep
        if min_a is None or max_a is None:
            return None
        return max_a - min_a

    def _score_range(self, config: SquatConfig) -> int:
        """Amplitude from range-of-motion + absolute depth."""
        min_angle = self._min_angle_in_rep
        rom = self._range_of_motion()
        if min_angle is None:
            return 30

        # Depth component (reach bottom threshold).
        if min_angle <= config.bottom_knee_angle:
            depth_score = 100
        elif min_angle >= config.standing_knee_angle - 5:
            depth_score = 15
        else:
            span = config.standing_knee_angle - config.bottom_knee_angle
            achieved = config.standing_knee_angle - min_angle
            ratio = _clamp(achieved / span, 0.0, 1.0)
            depth_score = int(_clamp(round(20 + ratio * 80), 0, 100))

        # ROM component (max − min knee angle through the cycle).
        if rom is None:
            rom_score = depth_score
        else:
            target = config.min_effective_range_of_motion
            if rom >= target:
                rom_score = 100
            elif rom <= target * 0.35:
                rom_score = 20
            else:
                rom_score = int(_clamp(round(20 + (rom / target) * 80), 0, 100))

        return int(_clamp(round((depth_score * 0.55) + (rom_score * 0.45)), 0, 100))

    def _score_stability(self) -> int:
        """Stability from frame-to-frame jitter + left/right balance (not cycle std)."""
        if len(self._rep_angles) < 3:
            return 70

        sum_delta = 0.0
        spike_count = 0
        for i in range(1, len(self._rep_angles)):
            d = abs(self._rep_angles[i] - self._rep_angles[i - 1])
            sum_delta += d
            if d > 22:
                spike_count += 1
        avg_delta = sum_delta / (len(self._rep_angles) - 1)
        # Smooth squat ≈ 3–12°/frame at ~12 FPS; punish spikes / huge jumps.
        jitter_score = _clamp(
            100 - _clamp(avg_delta - 6, 0, 40) * 2.2 - spike_count * 8,
            20.0,
            100.0,
        )

        balance_score = 90.0
        if self._side_deltas:
            avg_side = sum(self._side_deltas) / len(self._side_deltas)
            balance_score = _clamp(100 - avg_side * 2.2, 25.0, 100.0)

        # Optional: hipY vs ankleY consistency from trajectory.
        posture_score = 90.0
        if len(self._rep_frames) >= 3:
            hip_ys = [f.hip_y for f in self._rep_frames if f.hip_y is not None]
            ankle_ys = [f.ankle_y for f in self._rep_frames if f.ankle_y is not None]
            if len(hip_ys) >= 3 and len(ankle_ys) >= 3:
                # Hip should generally drop then rise; ankle roughly stable.
                ankle_jitter = 0.0
                for i in range(1, len(ankle_ys)):
                    ankle_jitter += abs(ankle_ys[i] - ankle_ys[i - 1])
                ankle_jitter /= len(ankle_ys) - 1
                posture_score = _clamp(100 - ankle_jitter * 180, 30.0, 100.0)

        return int(
            _clamp(
                round(jitter_score * 0.55 + balance_score * 0.25 + posture_score * 0.20),
                0,
                100,
            )
        )

    def _score_rhythm(self, config: SquatConfig) -> int:
        elapsed = self._elapsed_ms()
        if elapsed <= 0:
            return 70
        if elapsed < config.minimum_movement_duration:
            return int(
                _clamp(
                    round(40 + (elapsed / config.minimum_movement_duration) * 40),
                    0,
                    100,
                )
            )
        if elapsed > config.maximum_movement_duration:
            over = (
                elapsed - config.maximum_movement_duration
            ) / config.ideal_movement_time_ms
            return int(_clamp(round(85 - over * 35), 25, 100))
        dist = abs(elapsed - config.ideal_movement_time_ms) / config.ideal_movement_time_ms
        return int(_clamp(round(100 - dist * 40), 0, 100))

    def _live_feedback(
        self, action: ActionRecognitionResult, config: SquatConfig
    ) -> str:
        state = action.machine_state
        if state == SquatMachineState.waiting_person:
            return "请调整位置，确保全身进入摄像头"
        if state == SquatMachineState.standing:
            return "站稳后开始下蹲"
        if state == SquatMachineState.down:
            min_a = action.rep_min_knee_angle or action.knee_angle
            if min_a is not None and min_a > config.bottom_knee_angle + 15:
                return "下蹲幅度可以再大一些"
            return "动作保持稳定一些"
        if state == SquatMachineState.bottom:
            return "动作标准"
        if state == SquatMachineState.up:
            return "动作保持稳定一些"
        return "动作保持稳定一些"

    def _feedback_for(
        self,
        *,
        score: int,
        range_score: int,
        stability: int,
        rhythm: int,
        config: SquatConfig,
    ) -> str:
        if score >= config.correct_score_threshold and range_score >= 75:
            return "动作标准"
        if range_score <= stability and range_score <= rhythm:
            return "下蹲幅度可以再大一些"
        if stability <= range_score and stability <= rhythm:
            return "动作保持稳定一些"
        if rhythm < 65:
            return "动作慢一些，保持稳定"
        return "动作标准"

    def _elapsed_ms(self) -> int:
        started = self._rep_started_at
        if started is None:
            return 0
        return int((datetime.now() - started).total_seconds() * 1000)

    def _clear_rep_window(self) -> None:
        self._rep_angles.clear()
        self._side_deltas.clear()
        self._rep_frames.clear()
        self._rep_started_at = None
        self._min_angle_in_rep = None
        self._max_angle_in_rep = None
