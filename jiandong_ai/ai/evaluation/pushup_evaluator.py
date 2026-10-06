"""Cycle-based push-up quality: depth, body alignment, tempo.

EvaluationResult.stability_score is body-alignment (塌腰 / 塌肩 / 外展).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    SquatMachineState,
)
from ..action.pushup_config import PushupConfig
from ..action.pushup_frame_data import PushupFrameData, PushupRepTrajectory
from ..action.squat_config import SquatConfig
from ..pose.pose_result import PoseResult
from .action_evaluator import ActionEvaluator, EvaluationResult
from .personal_baseline import PersonalBaseline


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class PushupEvaluator(ActionEvaluator):
    def __init__(self, config: PushupConfig | None = None) -> None:
        self._config = config if config is not None else PushupConfig.defaults
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._rep_angles: list[float] = []
        self._body_lines: list[float] = []
        self._flares: list[float] = []
        self._rep_frames: list[PushupFrameData] = []
        self._rep_started_at: datetime | None = None
        self._prev_machine: SquatMachineState | None = None
        self._min_angle_in_rep: float | None = None
        self._max_angle_in_rep: float | None = None

    @property
    def config(self) -> PushupConfig:
        return self._config

    def update_config(self, value: PushupConfig) -> None:
        self._config = value

    @property
    def last_result(self) -> EvaluationResult:
        return self._last

    def reset(self) -> None:
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
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
        # baseline / config kept for ActionEvaluator interface parity with Dart.
        _ = baseline if baseline is not None else PersonalBaseline.defaults
        _ = config if config is not None else SquatConfig.defaults

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
            traj = action.last_pushup_trajectory
            self._absorb_trajectory(traj)
            self._last = self._score_completed_rep()
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
            traj = action.last_pushup_trajectory
            self._absorb_trajectory(traj)
            self._last = EvaluationResult(
                score=self._last.score,
                amplitude_score=self._last.amplitude_score,
                stability_score=self._last.stability_score,
                rhythm_score=self._last.rhythm_score,
                feedback=(
                    (traj.abort_reason if traj is not None else None)
                    or action.form_cue
                    or "半程偷懒"
                ),
                is_correct=False,
                knee_angle_min=self._min_angle_in_rep,
                knee_angle_max=self._max_angle_in_rep,
                range_of_motion=self._range_of_motion(),
                movement_duration_ms=self._elapsed_ms(),
            )
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

    def _absorb_trajectory(self, traj: PushupRepTrajectory | None) -> None:
        if traj is None or not traj.frames:
            return
        self._rep_frames.clear()
        self._rep_frames.extend(traj.frames)
        if traj.min_elbow_angle is not None:
            self._min_angle_in_rep = traj.min_elbow_angle
        if traj.max_elbow_angle is not None:
            self._max_angle_in_rep = traj.max_elbow_angle
        if traj.movement_duration_ms > 0:
            self._rep_started_at = datetime.now() - timedelta(
                milliseconds=traj.movement_duration_ms
            )
        self._rep_angles.clear()
        self._rep_angles.extend(
            f.primary_elbow_angle
            for f in traj.frames
            if f.primary_elbow_angle is not None
        )
        self._body_lines.clear()
        self._body_lines.extend(
            f.body_line_angle for f in traj.frames if f.body_line_angle is not None
        )
        self._flares.clear()
        self._flares.extend(
            f.elbow_flare_angle for f in traj.frames if f.elbow_flare_angle is not None
        )

    def _track_rep_samples(self, *, action: ActionRecognitionResult) -> None:
        angle = action.elbow_angle if action.elbow_angle is not None else action.knee_angle
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
            self._body_lines.clear()
            self._flares.clear()
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

        body = action.body_line_angle
        if body is not None:
            self._body_lines.append(body)
        flare = action.elbow_flare_angle
        if flare is not None:
            self._flares.append(flare)

        if action.current_pushup_frames:
            self._rep_frames.clear()
            self._rep_frames.extend(action.current_pushup_frames)

    def _score_completed_rep(self) -> EvaluationResult:
        range_score = self._score_range()
        alignment = self._score_alignment()
        rhythm = self._score_rhythm()
        score = int(
            round(
                (range_score * self._config.range_score_weight)
                + (alignment * self._config.alignment_score_weight)
                + (rhythm * self._config.rhythm_score_weight)
            )
        )
        score = int(_clamp(score, 0, 100))
        rom = self._range_of_motion()
        deep_enough = (self._min_angle_in_rep or 999) <= self._config.bottom_elbow_angle + 2
        rom_ok = (rom or 0) >= self._config.min_effective_range_of_motion * 0.75
        is_correct = (
            score >= self._config.correct_score_threshold and deep_enough and rom_ok
        )

        return EvaluationResult(
            score=score,
            amplitude_score=range_score,
            stability_score=alignment,
            rhythm_score=rhythm,
            feedback=self._feedback_for(
                score=score,
                range_score=range_score,
                alignment=alignment,
                rhythm=rhythm,
            ),
            is_correct=is_correct,
            knee_angle_min=self._min_angle_in_rep,
            knee_angle_max=self._max_angle_in_rep,
            range_of_motion=rom,
            movement_duration_ms=self._elapsed_ms(),
        )

    def _range_of_motion(self) -> float | None:
        min_a = self._min_angle_in_rep
        max_a = self._max_angle_in_rep
        if min_a is None or max_a is None:
            return None
        return max_a - min_a

    def _score_range(self) -> int:
        min_angle = self._min_angle_in_rep
        rom = self._range_of_motion()
        if min_angle is None:
            return 30

        if min_angle <= self._config.bottom_elbow_angle:
            depth_score = 100
        elif min_angle >= self._config.high_elbow_angle - 5:
            depth_score = 15
        else:
            span = self._config.high_elbow_angle - self._config.bottom_elbow_angle
            achieved = self._config.high_elbow_angle - min_angle
            ratio = _clamp(achieved / span, 0.0, 1.0)
            depth_score = int(_clamp(round(20 + ratio * 80), 0, 100))

        if rom is None:
            rom_score = depth_score
        else:
            target = self._config.min_effective_range_of_motion
            if rom >= target:
                rom_score = 100
            elif rom <= target * 0.35:
                rom_score = 20
            else:
                rom_score = int(_clamp(round(20 + (rom / target) * 80), 0, 100))

        return int(_clamp(round((depth_score * 0.55) + (rom_score * 0.45)), 0, 100))

    def _score_alignment(self) -> int:
        """Alignment from body line (塌腰), shoulder stack (塌肩), elbow flare (外展)."""
        line_score = 90.0
        if self._body_lines:
            min_line = min(self._body_lines)
            if min_line >= self._config.ideal_body_line_angle:
                line_score = 100
            elif min_line <= 140:
                line_score = 25
            else:
                span = self._config.ideal_body_line_angle - 140
                achieved = min_line - 140
                line_score = _clamp(25 + (achieved / span) * 75, 25.0, 100.0)

        flare_score = 90.0
        if self._flares:
            max_flare = max(self._flares)
            if max_flare <= self._config.max_elbow_flare_degrees:
                flare_score = 100
            else:
                over = max_flare - self._config.max_elbow_flare_degrees
                flare_score = _clamp(100 - over * 2.5, 25.0, 100.0)

        shoulder_score = 90.0
        if self._flares:
            # Closed elbow–shoulder–hip while not at the bottom ⇒ 塌肩.
            min_shoulder = min(self._flares)
            if (
                min_shoulder <= self._config.collapsed_shoulder_angle
                and (self._min_angle_in_rep or 180) > self._config.bottom_elbow_angle + 15
            ):
                shoulder_score = _clamp(
                    min_shoulder / self._config.collapsed_shoulder_angle * 80,
                    30.0,
                    80.0,
                )
        if len(self._rep_frames) >= 2:
            drop_sum = 0.0
            drop_n = 0
            for f in self._rep_frames:
                s = f.shoulder_y
                h = f.hip_y
                if s is None or h is None:
                    continue
                drop_sum += s - h
                drop_n += 1
            if drop_n > 0 and drop_sum / drop_n > 0.08:
                shoulder_score = min(shoulder_score, 55)

        return int(
            _clamp(
                round(line_score * 0.55 + flare_score * 0.25 + shoulder_score * 0.20),
                0,
                100,
            )
        )

    def _score_rhythm(self) -> int:
        elapsed = self._elapsed_ms()
        if elapsed <= 0:
            return 70
        if elapsed < self._config.minimum_movement_duration:
            return int(
                _clamp(
                    round(
                        40 + (elapsed / self._config.minimum_movement_duration) * 40
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
        cue = action.form_cue
        if cue is not None and cue != "":
            return cue
        if self._is_flared(action):
            return "飞肘"
        if self._is_piked(action):
            return "撅臀"
        if self._is_sagging(action):
            return "塌腰"
        if self._is_shoulder_collapsed(action):
            return "耸肩"
        if action.form_cue == "伸颈够低":
            return "伸颈够低"

        state = action.machine_state
        if state == SquatMachineState.waiting_person:
            return "请调整位置，确保全身进入摄像头"
        if state == SquatMachineState.standing:
            return "保持平板支撑后开始下压"
        if state == SquatMachineState.down:
            min_a = (
                action.rep_min_knee_angle
                or action.elbow_angle
                or action.knee_angle
            )
            if min_a is not None and min_a > self._config.bottom_elbow_angle + 5:
                return "半程偷懒"
            return "身体保持一条直线"
        if state == SquatMachineState.bottom:
            return "动作标准"
        if state == SquatMachineState.up:
            return "身体保持一条直线"
        return "身体保持一条直线"

    def _feedback_for(
        self,
        *,
        score: int,
        range_score: int,
        alignment: int,
        rhythm: int,
    ) -> str:
        max_flare = self._max_flare()
        if max_flare is not None and max_flare > self._config.max_elbow_flare_degrees:
            return "飞肘"
        min_body = self._min_body_line()
        if (
            min_body is not None
            and abs(self._config.ideal_body_line_angle - min_body)
            > self._config.body_line_tolerance_degrees
        ):
            return "塌腰"
        min_flare = self._min_flare()
        if (
            min_flare is not None
            and min_flare <= self._config.collapsed_shoulder_angle
            and alignment < range_score
        ):
            return "耸肩"
        if score >= self._config.correct_score_threshold and range_score >= 75:
            return "动作标准"
        if range_score <= alignment and range_score <= rhythm:
            return "半程偷懒"
        if alignment <= range_score and alignment <= rhythm:
            return "塌腰"
        if rhythm < 65:
            return "动作慢一些，保持稳定"
        return "动作标准"

    def _is_sagging(self, action: ActionRecognitionResult) -> bool:
        line = (
            action.body_line_angle
            if action.body_line_angle is not None
            else self._min_body_line()
        )
        if line is None:
            return False
        return (self._config.ideal_body_line_angle - line) > (
            self._config.body_line_tolerance_degrees
        )

    def _is_piked(self, action: ActionRecognitionResult) -> bool:
        line = (
            action.body_line_angle
            if action.body_line_angle is not None
            else self._min_body_line()
        )
        if line is None:
            return False
        frames = action.current_pushup_frames
        offset = None if not frames else frames[-1].hip_offset
        return (
            abs(self._config.ideal_body_line_angle - line)
            > self._config.body_line_tolerance_degrees
            and (offset or 0) < 0
        )

    def _is_flared(self, action: ActionRecognitionResult) -> bool:
        flare = (
            action.elbow_flare_angle
            if action.elbow_flare_angle is not None
            else self._max_flare()
        )
        return flare is not None and flare > self._config.max_elbow_flare_degrees

    def _is_shoulder_collapsed(self, action: ActionRecognitionResult) -> bool:
        flare = (
            action.elbow_flare_angle
            if action.elbow_flare_angle is not None
            else self._min_flare()
        )
        elbow = (
            action.elbow_angle if action.elbow_angle is not None else action.knee_angle
        )
        if flare is None or elbow is None:
            return False
        return (
            flare <= self._config.collapsed_shoulder_angle
            and elbow > self._config.bottom_elbow_angle + 15
        )

    def _min_body_line(self) -> float | None:
        if not self._body_lines:
            return None
        return min(self._body_lines)

    def _max_flare(self) -> float | None:
        if not self._flares:
            return None
        return max(self._flares)

    def _min_flare(self) -> float | None:
        if not self._flares:
            return None
        return min(self._flares)

    def _elapsed_ms(self) -> int:
        started = self._rep_started_at
        if started is None:
            return 0
        return int((datetime.now() - started).total_seconds() * 1000)

    def _clear_rep_window(self) -> None:
        self._rep_angles.clear()
        self._body_lines.clear()
        self._flares.clear()
        self._rep_frames.clear()
        self._rep_started_at = None
        self._min_angle_in_rep = None
        self._max_angle_in_rep = None
