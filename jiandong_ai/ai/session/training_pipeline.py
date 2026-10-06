"""Orchestrates PoseResult → recognize → evaluate → feedback each frame.

Live path: camera → PoseDetector → PoseResult → process_pose.
Test path: tick may call an internal Mock / Real detector.

exercise_id selects the recognizer. Unknown ids stay on squat.
"""

from __future__ import annotations

from enum import Enum

from ..action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    ActionRecognizer,
    SquatMachineState,
)
from ..action.exercise_kind import ExerciseKind
from ..action.glute_bridge_recognizer import GluteBridgeRecognizer
from ..action.high_knees_recognizer import HighKneesRecognizer
from ..action.jumping_jack_recognizer import JumpingJackRecognizer
from ..action.plank_config import PlankConfig
from ..action.plank_recognizer import PlankRecognizer
from ..action.pushup_config import PushupConfig
from ..action.pushup_frame_data import PushupFrameData, PushupRepTrajectory
from ..action.pushup_recognizer import PushupRecognizer
from ..action.reverse_lunge_recognizer import ReverseLungeRecognizer
from ..action.squat_config import SquatConfig
from ..action.squat_frame_data import SquatFrameData, SquatRepTrajectory
from ..action.squat_recognizer import SquatRecognizer
from ..evaluation.action_evaluator import ActionEvaluator, EvaluationResult, SquatEvaluationResult
from ..evaluation.glute_bridge_evaluator import GluteBridgeEvaluator
from ..evaluation.high_knees_evaluator import HighKneesEvaluator
from ..evaluation.jumping_jack_evaluator import JumpingJackEvaluator
from ..evaluation.personal_baseline import PersonalBaseline
from ..evaluation.plank_evaluator import PlankEvaluator
from ..evaluation.pushup_evaluator import PushupEvaluator
from ..evaluation.reverse_lunge_evaluator import ReverseLungeEvaluator
from ..evaluation.squat_evaluator import SquatEvaluator
from ..feedback.feedback_service import CoachFeedback, FeedbackService
from ..pose.mock_pose_detector import MockPoseDetector
from ..pose.pose_detector import PoseDetector
from ..pose.pose_result import PoseResult

try:
    from ..pose.mediapipe_detector import MediaPipePoseDetector as RealPoseDetector
except ImportError:  # pragma: no cover
    RealPoseDetector = None  # type: ignore[misc, assignment]


class PoseBackendMode(str, Enum):
    mock = "mock"
    real = "real"
    external = "external"


class TrainingPipeline:
    def __init__(
        self,
        *,
        mode: PoseBackendMode = PoseBackendMode.external,
        baseline: PersonalBaseline | None = None,
        config: SquatConfig | None = None,
        pushup_config: PushupConfig | None = None,
        exercise_id: str | None = None,
    ) -> None:
        self._mode = mode
        self._baseline = baseline or PersonalBaseline.defaults
        self._exercise_id = ExerciseKind.normalize(exercise_id)
        self._squat_config = config or SquatConfig.defaults
        self._pushup_config = pushup_config or PushupConfig.defaults
        self._detector: PoseDetector | None = None
        self._recognizer = self._build_recognizer(
            self._exercise_id, self._squat_config, self._pushup_config
        )
        self._evaluator = self._build_evaluator(
            self._exercise_id, self._pushup_config
        )
        self._feedback = FeedbackService()
        self._running = False
        self._paused = False
        self._pose = PoseResult.empty()
        self._action = ActionRecognitionResult(
            phase=ActionPhase.preparing,
            machine_state=SquatMachineState.waiting_person,
            rep_count=0,
            knee_angle=None,
        )
        self._evaluation = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback="等待开始训练",
        )
        self._coach = CoachFeedback(
            status_text="准备开始",
            message="请站到摄像头前，点击开始训练",
        )
        if mode != PoseBackendMode.external:
            self._detector = self._create_detector(mode)

    @staticmethod
    def _build_recognizer(
        exercise_id: str,
        squat_config: SquatConfig,
        pushup_config: PushupConfig,
    ) -> ActionRecognizer:
        if ExerciseKind.is_pushup(exercise_id):
            return PushupRecognizer(config=pushup_config)
        if ExerciseKind.is_reverse_lunge(exercise_id):
            return ReverseLungeRecognizer()
        if ExerciseKind.is_plank(exercise_id):
            return PlankRecognizer()
        if ExerciseKind.is_jumping_jack(exercise_id):
            return JumpingJackRecognizer()
        if ExerciseKind.is_high_knees(exercise_id):
            return HighKneesRecognizer()
        if ExerciseKind.is_glute_bridge(exercise_id):
            return GluteBridgeRecognizer()
        return SquatRecognizer(config=squat_config)

    @staticmethod
    def _build_evaluator(
        exercise_id: str, pushup_config: PushupConfig
    ) -> ActionEvaluator:
        if ExerciseKind.is_pushup(exercise_id):
            return PushupEvaluator(config=pushup_config)
        if ExerciseKind.is_reverse_lunge(exercise_id):
            return ReverseLungeEvaluator()
        if ExerciseKind.is_plank(exercise_id):
            return PlankEvaluator()
        if ExerciseKind.is_jumping_jack(exercise_id):
            return JumpingJackEvaluator()
        if ExerciseKind.is_high_knees(exercise_id):
            return HighKneesEvaluator()
        if ExerciseKind.is_glute_bridge(exercise_id):
            return GluteBridgeEvaluator()
        return SquatEvaluator()

    @property
    def mode(self) -> PoseBackendMode:
        return self._mode

    @property
    def detector(self) -> PoseDetector | None:
        return self._detector

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def pose(self) -> PoseResult:
        return self._pose

    @property
    def action(self) -> ActionRecognitionResult:
        return self._action

    @property
    def evaluation(self) -> EvaluationResult:
        return self._evaluation

    @property
    def evaluation_detail(self) -> SquatEvaluationResult | None:
        e = self._evaluator
        return e.last_detail if isinstance(e, SquatEvaluator) else None

    @property
    def coach(self) -> CoachFeedback:
        return self._coach

    @property
    def backend_name(self) -> str:
        det = self._detector
        if det is None:
            return "external PoseResult"
        return getattr(det, "backend_name", type(det).__name__)

    @property
    def baseline(self) -> PersonalBaseline:
        return self._baseline

    @property
    def config(self) -> SquatConfig:
        return self._squat_config

    @property
    def pushup_config(self) -> PushupConfig:
        return self._pushup_config

    @property
    def recognizer(self) -> ActionRecognizer:
        return self._recognizer

    @property
    def exercise_id(self) -> str:
        return self._exercise_id

    @property
    def is_pushup(self) -> bool:
        return ExerciseKind.is_pushup(self._exercise_id)

    @property
    def completes_by_hold(self) -> bool:
        return ExerciseKind.is_plank(self._exercise_id)

    @property
    def hold_elapsed_ms(self) -> int:
        r = self._recognizer
        return r.current_hold_ms if isinstance(r, PlankRecognizer) else 0

    @property
    def hold_target_ms(self) -> int:
        return PlankConfig.defaults.target_hold_ms

    @property
    def current_rep_frames(self) -> list[SquatFrameData]:
        return list(self._action.current_rep_frames)

    @property
    def last_trajectory(self) -> SquatRepTrajectory | None:
        traj = self._action.last_completed_trajectory
        return traj if isinstance(traj, SquatRepTrajectory) else None

    @property
    def current_pushup_frames(self) -> list[PushupFrameData]:
        return list(self._action.current_pushup_frames)

    @property
    def last_pushup_trajectory(self) -> PushupRepTrajectory | None:
        traj = self._action.last_pushup_trajectory
        return traj if isinstance(traj, PushupRepTrajectory) else None

    @property
    def is_using_mock_pose(self) -> bool:
        return isinstance(self._detector, MockPoseDetector)

    def set_mode(self, mode: PoseBackendMode) -> None:
        if self._mode == mode:
            return
        was_running = self._running
        self.stop()
        self._mode = mode
        if mode == PoseBackendMode.external:
            self._detector = None
        else:
            self._detector = self._create_detector(mode)
        if was_running:
            self.start()

    def update_baseline(self, baseline: PersonalBaseline) -> None:
        self._baseline = baseline

    def update_config(self, config: SquatConfig) -> None:
        self._squat_config = config
        r = self._recognizer
        if isinstance(r, SquatRecognizer):
            r.update_config(config)

    def update_pushup_config(self, config: PushupConfig) -> None:
        self._pushup_config = config
        r = self._recognizer
        if isinstance(r, PushupRecognizer):
            r.update_config(config)
        e = self._evaluator
        if isinstance(e, PushupEvaluator) and hasattr(e, "update_config"):
            e.update_config(config)

    def switch_exercise(self, exercise_id: str | None) -> None:
        next_id = ExerciseKind.normalize(exercise_id)
        if next_id != self._exercise_id:
            self._exercise_id = next_id
            self._recognizer = self._build_recognizer(
                self._exercise_id, self._squat_config, self._pushup_config
            )
            self._evaluator = self._build_evaluator(
                self._exercise_id, self._pushup_config
            )
        else:
            self._recognizer.reset()
            self._evaluator.reset()
        self._action = ActionRecognitionResult(
            phase=ActionPhase.preparing,
            machine_state=SquatMachineState.waiting_person,
            rep_count=0,
            knee_angle=None,
        )
        self._evaluation = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback=FeedbackService.opening_line(self._exercise_id),
        )
        if self._running:
            self._coach = self._feedback.generate(
                action=self._action,
                evaluation=self._evaluation,
                is_running=True,
                is_paused=self._paused,
                exercise_id=self._exercise_id,
            )

    def start(self) -> None:
        detector = self._detector
        if detector is not None and hasattr(detector, "initialize"):
            detector.initialize()  # type: ignore[attr-defined]
        self._recognizer.reset()
        self._evaluator.reset()
        self._running = True
        self._paused = False
        if isinstance(detector, MockPoseDetector):
            detector.restart_cycle()
        self._action = ActionRecognitionResult(
            phase=ActionPhase.preparing,
            machine_state=SquatMachineState.waiting_person,
            rep_count=0,
            knee_angle=None,
        )
        self._evaluation = EvaluationResult(
            score=0,
            amplitude_score=0,
            stability_score=0,
            rhythm_score=0,
            feedback=FeedbackService.opening_line(self._exercise_id),
        )
        self._coach = self._feedback.generate(
            action=self._action,
            evaluation=self._evaluation,
            is_running=True,
            exercise_id=self._exercise_id,
        )

    def pause(self) -> None:
        if not self._running or self._paused:
            return
        self._paused = True
        detector = self._detector
        if detector is not None and hasattr(detector, "pause"):
            detector.pause()  # type: ignore[attr-defined]
        self._coach = self._feedback.generate(
            action=self._action,
            evaluation=self._evaluation,
            is_running=True,
            is_paused=True,
            exercise_id=self._exercise_id,
        )

    def resume(self) -> None:
        if not self._running or not self._paused:
            return
        self._paused = False
        detector = self._detector
        if detector is not None and hasattr(detector, "resume"):
            detector.resume()  # type: ignore[attr-defined]

    def stop(self) -> None:
        self._running = False
        self._paused = False
        detector = self._detector
        if detector is not None:
            if hasattr(detector, "dispose"):
                detector.dispose()  # type: ignore[attr-defined]
            else:
                detector.close()
        self._coach = self._feedback.generate(
            action=self._action,
            evaluation=self._evaluation,
            is_running=False,
            exercise_id=self._exercise_id,
        )

    def process_pose(self, pose: PoseResult) -> CoachFeedback:
        self._pose = pose
        if not self._running or self._paused:
            self._coach = self._feedback.generate(
                action=self._action,
                evaluation=self._evaluation,
                is_running=self._running,
                is_paused=self._paused,
                exercise_id=self._exercise_id,
            )
            return self._coach
        self._action = self._recognizer.recognize(self._pose)
        self._evaluation = self._evaluator.evaluate(
            action=self._action,
            pose=self._pose,
            baseline=self._baseline,
            config=self._squat_config,
        )
        self._coach = self._feedback.generate(
            action=self._action,
            evaluation=self._evaluation,
            is_running=True,
            is_paused=False,
            exercise_id=self._exercise_id,
        )
        return self._coach

    def tick(self) -> None:
        if not self._running or self._paused:
            return
        detector = self._detector
        if detector is None:
            raise RuntimeError(
                "TrainingPipeline.tick requires mock/real mode; "
                "use process_pose for live camera."
            )
        self._pose = detector.detect(None)
        self.process_pose(self._pose)

    def _create_detector(self, mode: PoseBackendMode) -> PoseDetector:
        if mode == PoseBackendMode.mock:
            return MockPoseDetector()
        if mode == PoseBackendMode.real:
            if RealPoseDetector is None:
                raise RuntimeError("Real pose detector is not available")
            return RealPoseDetector()
        raise RuntimeError("external mode has no owned detector")
