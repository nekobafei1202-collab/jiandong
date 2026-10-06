"""Cycle-based reverse-lunge quality evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from ..action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    SquatMachineState,
)
from ..action.reverse_lunge_config import ReverseLungeConfig
from ..action.squat_config import SquatConfig
from ..action.squat_frame_data import SquatRepTrajectory
from ..pose.pose_result import PoseResult
from .action_evaluator import ActionEvaluator, EvaluationResult
from .personal_baseline import PersonalBaseline


def _ms_between(later: datetime, earlier: datetime) -> int:
    return int((later - earlier).total_seconds() * 1000)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class LungeEvaluationResult:
    score: int
    is_correct: bool
    feedback: str
    min_knee_angle: float | None
    max_knee_angle: float | None
    range_of_motion: float | None
    hip_drop_ratio: float | None
    avg_torso_lean_angle: float | None
    movement_duration: int
    depth_score: int
    posture_score: int
    stability_score: int
    rhythm_score: int

    @property
    def as_evaluation(self) -> EvaluationResult:
        return EvaluationResult(
            score=self.score,
            amplitude_score=self.depth_score,
            stability_score=self.stability_score,
            rhythm_score=self.rhythm_score,
            feedback=self.feedback,
            is_correct=self.is_correct,
            knee_angle_min=self.min_knee_angle,
            knee_angle_max=self.max_knee_angle,
            range_of_motion=self.range_of_motion,
            movement_duration_ms=self.movement_duration,
        )


class ReverseLungeEvaluator(ActionEvaluator):
    def __init__(self, config: ReverseLungeConfig | None = None) -> None:
        self._config = config or ReverseLungeConfig.defaults
        self._last_detail = LungeEvaluationResult(
            score=0,
            is_correct=False,
            feedback="等待开始训练",
            min_knee_angle=None,
            max_knee_angle=None,
            range_of_motion=None,
            hip_drop_ratio=None,
            avg_torso_lean_angle=None,
            movement_duration=0,
            depth_score=0,
            posture_score=0,
            stability_score=0,
            rhythm_score=0,
        )
        self._last = self._last_detail.as_evaluation
        self._rep_angles: list[float] = []
        self._lean_samples: list[float] = []
        self._hip_x_norm_samples: list[float] = []
        self._rep_started_at: datetime | None = None
        self._prev_machine: SquatMachineState | None = None
        self._min_angle_in_rep: float | None = None
        self._max_angle_in_rep: float | None = None
        self._hip_drop_ratio_in_rep: float | None = None
        self._traj_duration_ms = 0

    @property
    def config(self) -> ReverseLungeConfig:
        return self._config

    def update_config(self, value: ReverseLungeConfig) -> None:
        self._config = value

    @property
    def last_result(self) -> EvaluationResult:
        return self._last

    @property
    def last_detail(self) -> LungeEvaluationResult:
        return self._last_detail

    def reset(self) -> None:
        self._last_detail = LungeEvaluationResult(
            score=0,
            is_correct=False,
            feedback="等待开始训练",
            min_knee_angle=None,
            max_knee_angle=None,
            range_of_motion=None,
            hip_drop_ratio=None,
            avg_torso_lean_angle=None,
            movement_duration=0,
            depth_score=0,
            posture_score=0,
            stability_score=0,
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

        self._track_rep_samples(action=action, pose=pose)

        if action.just_completed_rep:
            self._absorb_trajectory(action.last_completed_trajectory)  # type: ignore[arg-type]
            self._last_detail = self._score_completed_rep()
            self._last = self._last_detail.as_evaluation
            self._clear_rep_window()
            self._prev_machine = action.machine_state
            return self._last

        aborted_shallow = (
            self._prev_machine is not None
            and self._prev_machine != SquatMachineState.standing
            and self._prev_machine != SquatMachineState.waiting_person
            and action.machine_state == SquatMachineState.standing
            and not action.just_completed_rep
            and self._min_angle_in_rep is not None
        )

        if aborted_shallow:
            self._absorb_trajectory(action.last_completed_trajectory)  # type: ignore[arg-type]
            self._last_detail = LungeEvaluationResult(
                score=self._last.score,
                is_correct=False,
                feedback="下蹲深度不足，髋部再往下沉一些",
                min_knee_angle=self._min_angle_in_rep,
                max_knee_angle=self._max_angle_in_rep,
                range_of_motion=self._range_of_motion(),
                hip_drop_ratio=self._hip_drop_ratio_in_rep,
                avg_torso_lean_angle=self._avg_lean(),
                movement_duration=self._elapsed_ms(),
                depth_score=self._last.amplitude_score,
                posture_score=self._last_detail.posture_score,
                stability_score=self._last.stability_score,
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
            feedback=self._live_feedback(action),
            is_correct=self._last.is_correct,
            knee_angle_min=self._min_angle_in_rep or action.rep_min_knee_angle,
            knee_angle_max=self._max_angle_in_rep or action.rep_max_knee_angle,
            range_of_motion=self._range_of_motion() or action.range_of_motion,
            movement_duration_ms=self._elapsed_ms(),
        )
        self._prev_machine = action.machine_state
        return self._last

    def _track_rep_samples(
        self, *, action: ActionRecognitionResult, pose: PoseResult
    ) -> None:
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
            self._clear_rep_window()
            self._rep_started_at = datetime.now()
            self._min_angle_in_rep = angle
            self._max_angle_in_rep = angle

        in_rep = (
            action.machine_state
            in (
                SquatMachineState.down,
                SquatMachineState.bottom,
                SquatMachineState.up,
            )
            or action.just_completed_rep
        )

        if angle is not None and in_rep:
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

        if in_rep:
            lean = self._torso_lean_from_pose(pose)
            if lean is not None:
                self._lean_samples.append(lean)
            hip_x_norm = self._normalized_hip_x(pose)
            if hip_x_norm is not None:
                self._hip_x_norm_samples.append(hip_x_norm)

    def _torso_lean_from_pose(self, pose: PoseResult) -> float | None:
        chain = pose.preferred_body_line
        if chain is None or not chain.is_reliable:
            return None
        dy = chain.hip.y - chain.shoulder.y
        if dy <= 0.01:
            return None
        return math.atan2(abs(chain.shoulder.x - chain.hip.x), dy) * 180 / math.pi

    def _normalized_hip_x(self, pose: PoseResult) -> float | None:
        ls = pose.left_shoulder
        rs = pose.right_shoulder
        chain = pose.preferred_lower_body
        if ls is None or rs is None or chain is None:
            return None
        if not ls.is_reliable() or not rs.is_reliable():
            return None
        width = abs(ls.x - rs.x)
        if width < 0.02:
            return None
        return chain.hip.x / width

    def _absorb_trajectory(self, traj: SquatRepTrajectory | None) -> None:
        if traj is None or not traj.frames:
            return
        if traj.min_knee_angle is not None:
            self._min_angle_in_rep = traj.min_knee_angle
        if traj.max_knee_angle is not None:
            self._max_angle_in_rep = traj.max_knee_angle
        if traj.movement_duration_ms > 0:
            self._traj_duration_ms = traj.movement_duration_ms
        self._rep_angles = [
            f.primary_knee_angle
            for f in traj.frames
            if f.primary_knee_angle is not None
        ]
        spans = [
            abs(f.ankle_y - f.hip_y)
            for f in traj.frames
            if f.hip_y is not None and f.ankle_y is not None
        ]
        if len(spans) >= 2:
            baseline = max(spans)
            min_span = min(spans)
            if baseline > 0.05:
                self._hip_drop_ratio_in_rep = _clamp(
                    (baseline - min_span) / baseline, 0.0, 1.0
                )

    def _score_completed_rep(self) -> LungeEvaluationResult:
        depth = self._score_depth()
        posture = self._score_posture()
        stability = self._score_stability()
        rhythm = self._score_rhythm()
        score = int(
            round(
                depth * self._config.depth_score_weight
                + posture * self._config.posture_score_weight
                + stability * self._config.stability_score_weight
                + rhythm * self._config.rhythm_score_weight
            )
        )
        score = int(_clamp(score, 0, 100))
        rom = self._range_of_motion()
        deep_enough = (self._min_angle_in_rep or 999) <= self._config.bottom_knee_angle + 2
        rom_ok = (rom or 0) >= self._config.min_effective_range_of_motion * 0.75
        hip_drop_ok = (self._hip_drop_ratio_in_rep or 0) >= self._config.min_hip_drop_ratio
        is_correct = (
            score >= self._config.correct_score_threshold
            and deep_enough
            and rom_ok
            and hip_drop_ok
        )
        return LungeEvaluationResult(
            score=score,
            is_correct=is_correct,
            feedback=self._feedback_for(
                score=score,
                depth=depth,
                posture=posture,
                stability=stability,
                rhythm=rhythm,
            ),
            min_knee_angle=self._min_angle_in_rep,
            max_knee_angle=self._max_angle_in_rep,
            range_of_motion=rom,
            hip_drop_ratio=self._hip_drop_ratio_in_rep,
            avg_torso_lean_angle=self._avg_lean(),
            movement_duration=self._elapsed_ms(),
            depth_score=depth,
            posture_score=posture,
            stability_score=stability,
            rhythm_score=rhythm,
        )

    def _range_of_motion(self) -> float | None:
        min_a = self._min_angle_in_rep
        max_a = self._max_angle_in_rep
        if min_a is None or max_a is None:
            return None
        return max_a - min_a

    def _avg_lean(self) -> float | None:
        if not self._lean_samples:
            return None
        return sum(self._lean_samples) / len(self._lean_samples)

    def _score_depth(self) -> int:
        min_angle = self._min_angle_in_rep
        rom = self._range_of_motion()
        if min_angle is None:
            return 30

        if min_angle <= self._config.bottom_knee_angle:
            angle_score = 100
        elif min_angle >= self._config.standing_knee_angle - 5:
            angle_score = 15
        else:
            span = self._config.standing_knee_angle - self._config.bottom_knee_angle
            achieved = self._config.standing_knee_angle - min_angle
            ratio = _clamp(achieved / span, 0.0, 1.0)
            angle_score = int(_clamp(round(20 + ratio * 80), 0, 100))

        if rom is None:
            rom_score = angle_score
        else:
            target = self._config.min_effective_range_of_motion
            if rom >= target:
                rom_score = 100
            elif rom <= target * 0.35:
                rom_score = 20
            else:
                rom_score = int(_clamp(round(20 + (rom / target) * 80), 0, 100))

        drop = self._hip_drop_ratio_in_rep
        if drop is None:
            drop_score = angle_score
        elif drop >= self._config.good_hip_drop_ratio:
            drop_score = 100
        elif drop <= 0.05:
            drop_score = 10
        else:
            span = self._config.good_hip_drop_ratio - 0.05
            drop_score = int(
                _clamp(round(10 + ((drop - 0.05) / span) * 90), 0, 100)
            )

        return int(
            _clamp(
                round(angle_score * 0.45 + rom_score * 0.25 + drop_score * 0.30),
                0,
                100,
            )
        )

    def _score_posture(self) -> int:
        lean = self._avg_lean()
        if lean is None:
            return 75
        if lean <= self._config.torso_upright_lean_angle:
            return 100
        if lean >= self._config.torso_bad_lean_angle:
            return 10
        span = self._config.torso_bad_lean_angle - self._config.torso_upright_lean_angle
        return int(
            _clamp(
                round(
                    100
                    - ((lean - self._config.torso_upright_lean_angle) / span) * 90
                ),
                10,
                100,
            )
        )

    def _score_stability(self) -> int:
        jitter_score = 70.0
        if len(self._rep_angles) >= 3:
            sum_delta = 0.0
            spike_count = 0
            for i in range(1, len(self._rep_angles)):
                d = abs(self._rep_angles[i] - self._rep_angles[i - 1])
                sum_delta += d
                if d > 22:
                    spike_count += 1
            avg_delta = sum_delta / (len(self._rep_angles) - 1)
            jitter_score = _clamp(
                100 - _clamp(avg_delta - 6, 0, 40) * 2.2 - spike_count * 8,
                20.0,
                100.0,
            )

        sway_score = 85.0
        if len(self._hip_x_norm_samples) >= 2:
            lo = min(self._hip_x_norm_samples)
            hi = max(self._hip_x_norm_samples)
            sway = hi - lo
            if sway <= self._config.max_hip_sway_ratio:
                sway_score = 100
            elif sway >= self._config.bad_hip_sway_ratio:
                sway_score = 20
            else:
                span = self._config.bad_hip_sway_ratio - self._config.max_hip_sway_ratio
                sway_score = _clamp(
                    100 - ((sway - self._config.max_hip_sway_ratio) / span) * 80,
                    20.0,
                    100.0,
                )

        return int(_clamp(round(jitter_score * 0.5 + sway_score * 0.5), 0, 100))

    def _score_rhythm(self) -> int:
        elapsed = self._elapsed_ms()
        if elapsed <= 0:
            return 70
        if elapsed < self._config.minimum_movement_duration:
            return int(
                _clamp(
                    round(
                        40
                        + (elapsed / self._config.minimum_movement_duration) * 40
                    ),
                    0,
                    100,
                )
            )
        if elapsed > self._config.maximum_movement_duration:
            over = (
                elapsed - self._config.maximum_movement_duration
            ) / self._config.ideal_movement_time_ms
            return int(_clamp(round(85 - over * 35), 25, 100))
        dist = (
            abs(elapsed - self._config.ideal_movement_time_ms)
            / self._config.ideal_movement_time_ms
        )
        return int(_clamp(round(100 - dist * 40), 0, 100))

    def _live_feedback(self, action: ActionRecognitionResult) -> str:
        state = action.machine_state
        if state == SquatMachineState.waiting_person:
            return "请调整位置，确保全身进入摄像头"
        if state == SquatMachineState.standing:
            return "站稳后开始向后撤步下蹲"
        if state == SquatMachineState.down:
            min_a = action.rep_min_knee_angle or action.knee_angle
            if min_a is not None and min_a > self._config.bottom_knee_angle + 15:
                return "下蹲深度不足，髋部再往下沉一些"
            return "动作保持稳定一些"
        if state == SquatMachineState.bottom:
            lean = self._avg_lean()
            if lean is not None and lean > self._config.torso_upright_lean_angle:
                return "保持躯干直立，避免前倾"
            return "动作标准"
        return "动作保持稳定一些"

    def _feedback_for(
        self,
        *,
        score: int,
        depth: int,
        posture: int,
        stability: int,
        rhythm: int,
    ) -> str:
        if (
            score >= self._config.correct_score_threshold
            and depth >= 75
            and posture >= 75
        ):
            return "动作标准"
        if depth <= posture and depth <= stability and depth <= rhythm:
            return "下蹲深度不足，髋部再往下沉一些"
        if posture <= depth and posture <= stability and posture <= rhythm:
            return "保持躯干直立，避免前倾"
        if stability <= depth and stability <= posture and stability <= rhythm:
            return "保持身体稳定，减少左右晃动"
        if rhythm < 65:
            return "控制动作节奏，避免过快或过慢"
        return "动作标准"

    def _elapsed_ms(self) -> int:
        if self._traj_duration_ms > 0:
            return self._traj_duration_ms
        started = self._rep_started_at
        if started is None:
            return 0
        return _ms_between(datetime.now(), started)

    def _clear_rep_window(self) -> None:
        self._rep_angles.clear()
        self._lean_samples.clear()
        self._hip_x_norm_samples.clear()
        self._rep_started_at = None
        self._min_angle_in_rep = None
        self._max_angle_in_rep = None
        self._hip_drop_ratio_in_rep = None
        self._traj_duration_ms = 0
