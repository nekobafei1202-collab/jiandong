"""Scores a finished jumping jack: leg spread, arm raise, and tempo."""

from __future__ import annotations

from datetime import datetime

from ..action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    SquatMachineState,
)
from ..action.jumping_jack_config import JumpingJackConfig
from ..action.squat_config import SquatConfig
from ..pose.pose_result import PoseResult
from .action_evaluator import ActionEvaluator, EvaluationResult
from .personal_baseline import PersonalBaseline


def _ms_between(later: datetime, earlier: datetime) -> int:
    return max(0, int((later - earlier).total_seconds() * 1000))


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class JumpingJackEvaluator(ActionEvaluator):
    def __init__(self, config: JumpingJackConfig | None = None) -> None:
        self._config = config or JumpingJackConfig.defaults
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._cycle_started_at: datetime | None = None
        self._max_leg = 0.0
        self._max_arm = 0.0
        self._leg_samples: list[float] = []

    @property
    def config(self) -> JumpingJackConfig:
        return self._config

    def reset(self) -> None:
        self._last = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._clear_cycle()

    def evaluate(
        self,
        *,
        action: ActionRecognitionResult,
        pose: PoseResult,
        baseline: PersonalBaseline | None = None,
        config: SquatConfig | None = None,
    ) -> EvaluationResult:
        if action.phase == ActionPhase.no_person or not action.has_reliable_pose:
            self._cycle_started_at = None
            return self._hold(feedback="请调整位置，确保全身进入摄像头")

        open_ = action.machine_state == SquatMachineState.bottom
        if open_ and self._cycle_started_at is None:
            self._cycle_started_at = pose.timestamp
            self._max_leg = 0.0
            self._max_arm = 0.0
            self._leg_samples.clear()

        leg = action.leg_spread_ratio
        arm = action.arm_raise_ratio
        if leg is not None and (open_ or action.just_completed_rep):
            self._max_leg = max(self._max_leg, leg)
            self._leg_samples.append(leg)
        if arm is not None and (open_ or action.just_completed_rep):
            self._max_arm = max(self._max_arm, arm)

        if not action.just_completed_rep:
            if action.machine_state == SquatMachineState.standing and not open_:
                if not action.reached_bottom:
                    self._clear_cycle()
            return self._hold(feedback=action.form_cue or self._live(action))

        range_ = self._score_range()
        stability = self._score_stability()
        rhythm = self._score_rhythm(self._elapsed(pose.timestamp))
        score = int(
            _clamp(
                round(
                    range_ * self._config.range_score_weight
                    + stability * self._config.stability_score_weight
                    + rhythm * self._config.rhythm_score_weight
                ),
                0,
                100,
            )
        )
        full_enough = self._max_leg >= self._config.apart_leg_ratio and self._max_arm > 0

        self._last = EvaluationResult(
            score=score,
            amplitude_score=range_,
            stability_score=stability,
            rhythm_score=rhythm,
            feedback=self._feedback(
                score=score,
                range_=range_,
                stability=stability,
                rhythm=rhythm,
                full_enough=full_enough,
            ),
            is_correct=score >= self._config.correct_score_threshold and full_enough,
            range_of_motion=self._max_leg if self._max_leg > 0 else None,
            movement_duration_ms=self._elapsed(pose.timestamp),
        )
        self._clear_cycle()
        return self._last

    def _elapsed(self, now: datetime) -> int:
        start = self._cycle_started_at
        if start is None:
            return 0
        return _ms_between(now, start)

    def _score_range(self) -> int:
        leg = self._band(
            value=self._max_leg,
            low=self._config.together_leg_ratio,
            high=self._config.full_leg_spread_ratio,
        )
        arm = self._band(
            value=max(0.0, self._max_arm),
            low=0,
            high=self._config.full_arm_raise_ratio,
        )
        return int(_clamp(round((leg + arm) / 2), 0, 100))

    def _band(self, *, value: float, low: float, high: float) -> int:
        if high <= low:
            return 100 if value > 0 else 20
        if value >= high:
            return 100
        if value <= low:
            return 20
        t = _clamp((value - low) / (high - low), 0.0, 1.0)
        return int(_clamp(round(20 + t * 80), 0, 100))

    def _score_stability(self) -> int:
        if len(self._leg_samples) < 3:
            return 80
        total = 0.0
        for i in range(1, len(self._leg_samples)):
            total += abs(self._leg_samples[i] - self._leg_samples[i - 1])
        avg = total / (len(self._leg_samples) - 1)
        return int(_clamp(round(100 - avg * 80), 25, 100))

    def _score_rhythm(self, elapsed: int) -> int:
        if elapsed <= 0:
            return 70
        min_ms = self._config.min_cycle_duration_ms
        max_ms = self._config.max_cycle_duration_ms
        ideal = round((min_ms + max_ms) / 2)
        if elapsed < min_ms:
            return int(_clamp(round(40 + (elapsed / min_ms) * 40), 0, 100))
        if elapsed > max_ms:
            over = (elapsed - max_ms) / ideal
            return int(_clamp(round(85 - over * 35), 25, 100))
        dist = abs(elapsed - ideal) / ideal
        return int(_clamp(round(100 - dist * 40), 0, 100))

    def _live(self, action: ActionRecognitionResult) -> str:
        state = action.machine_state
        if state == SquatMachineState.waiting_person:
            return "请面对镜头站好"
        if state == SquatMachineState.standing:
            return "手脚同时打开，再收回并拢"
        if state == SquatMachineState.bottom:
            return "保持打开"
        return "手脚同时打开，再收回并拢"

    def _feedback(
        self,
        *,
        score: int,
        range_: int,
        stability: int,
        rhythm: int,
        full_enough: bool,
    ) -> str:
        leg = self._band(
            value=self._max_leg,
            low=self._config.together_leg_ratio,
            high=self._config.full_leg_spread_ratio,
        )
        arm = self._band(
            value=max(0.0, self._max_arm),
            low=0,
            high=self._config.full_arm_raise_ratio,
        )
        if not full_enough or (range_ < 75 and leg <= arm):
            return "双腿再分开一些"
        if range_ < 75 and arm < leg:
            return "双臂举过头顶"
        if score >= self._config.correct_score_threshold and range_ >= 75:
            return "动作标准"
        if stability <= range_ and stability <= rhythm and stability < 70:
            return "落地时站稳一些"
        if rhythm < 65:
            return "节奏放稳一些"
        return "动作标准"

    def _hold(self, *, feedback: str) -> EvaluationResult:
        self._last = EvaluationResult(
            score=self._last.score,
            amplitude_score=self._last.amplitude_score,
            stability_score=self._last.stability_score,
            rhythm_score=self._last.rhythm_score,
            feedback=feedback,
            is_correct=self._last.is_correct,
            knee_angle_min=self._last.knee_angle_min,
            knee_angle_max=self._last.knee_angle_max,
            range_of_motion=self._last.range_of_motion,
            movement_duration_ms=self._last.movement_duration_ms,
        )
        return self._last

    def _clear_cycle(self) -> None:
        self._cycle_started_at = None
        self._max_leg = 0.0
        self._max_arm = 0.0
        self._leg_samples.clear()
