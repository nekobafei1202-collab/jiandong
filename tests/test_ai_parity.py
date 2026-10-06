from __future__ import annotations

from datetime import datetime, timedelta

from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.ai.action.squat_config import SquatConfig
from jiandong_ai.ai.action.squat_recognizer import SquatRecognizer
from jiandong_ai.ai.pose.keypoint import Keypoint, KeypointName
from jiandong_ai.ai.pose.pose_result import PoseResult
from jiandong_ai.ai.session.training_pipeline import TrainingPipeline
from jiandong_ai.ai.utils.angle_utils import AngleUtils


def _pose_from_knee_angle(angle_deg: float, ts: datetime) -> PoseResult:
    """Build a synthetic reliable lower-body pose for a target knee angle."""
    import math

    cx = 0.5
    knee_y = 0.55
    thigh = 0.15
    shin = 0.15
    rad = math.radians(angle_deg)
    hip_x = cx
    hip_y = knee_y - thigh
    # ankle placed so interior angle at knee == angle_deg
    ankle_x = cx + shin * math.sin(rad)
    ankle_y = knee_y - shin * math.cos(rad)

    def kp(name: KeypointName, x: float, y: float) -> Keypoint:
        return Keypoint(name=name, x=x, y=y, confidence=0.95)

    points = [
        kp(KeypointName.nose, cx, 0.15),
        kp(KeypointName.leftShoulder, cx - 0.08, 0.28),
        kp(KeypointName.rightShoulder, cx + 0.08, 0.28),
        kp(KeypointName.leftHip, hip_x - 0.03, hip_y),
        kp(KeypointName.rightHip, hip_x + 0.03, hip_y),
        kp(KeypointName.leftKnee, cx - 0.03, knee_y),
        kp(KeypointName.rightKnee, cx + 0.03, knee_y),
        kp(KeypointName.leftAnkle, ankle_x - 0.03, ankle_y),
        kp(KeypointName.rightAnkle, ankle_x + 0.03, ankle_y),
        kp(KeypointName.leftElbow, cx - 0.1, 0.36),
        kp(KeypointName.rightElbow, cx + 0.1, 0.36),
        kp(KeypointName.leftWrist, cx - 0.12, 0.44),
        kp(KeypointName.rightWrist, cx + 0.12, 0.44),
        kp(KeypointName.leftEye, cx - 0.02, 0.14),
        kp(KeypointName.rightEye, cx + 0.02, 0.14),
        kp(KeypointName.leftEar, cx - 0.04, 0.15),
        kp(KeypointName.rightEar, cx + 0.04, 0.15),
    ]
    return PoseResult.from_keypoints(points, timestamp=ts)


def test_angle_utils_right_angle():
    a = Keypoint(KeypointName.leftHip, 0, 0, 1)
    b = Keypoint(KeypointName.leftKnee, 0, 1, 1)
    c = Keypoint(KeypointName.leftAnkle, 1, 1, 1)
    ang = AngleUtils.calculate_angle(a, b, c)
    assert abs(ang - 90) < 1e-6


def test_exercise_kind_normalize_and_manual():
    assert ExerciseKind.normalize("俯卧撑") == ExerciseKind.pushup
    assert ExerciseKind.normalize("弓步蹲") == ExerciseKind.reverse_lunge
    assert ExerciseKind.supports_auto_detect("深蹲")
    assert ExerciseKind.is_manual_complete("卷腹")
    assert ExerciseKind.display_name("glute_bridge") == "臀桥"


def test_squat_config_thresholds_match_dart():
    c = SquatConfig.defaults
    assert c.standing_knee_angle == 155
    assert c.down_knee_angle == 130
    assert c.bottom_knee_angle == 100
    assert c.state_confirm_frames == 3
    assert c.min_rep_interval_ms == 700


def test_squat_recognizer_counts_full_cycle():
    # Relax debounce for synthetic frames
    cfg = SquatConfig(
        standing_knee_angle=155,
        down_knee_angle=130,
        bottom_knee_angle=100,
        state_confirm_frames=1,
        min_state_duration_ms=0,
        min_rep_interval_ms=0,
        min_effective_range_of_motion=20,
    )
    r = SquatRecognizer(config=cfg)
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    i = 0
    result = None
    for ang, n in [(165, 5), (120, 5), (90, 5), (120, 5), (165, 8)]:
        for _ in range(n):
            result = r.recognize(
                _pose_from_knee_angle(ang, t0 + timedelta(milliseconds=40 * i))
            )
            i += 1
    assert result is not None
    assert result.rep_count >= 1


def test_pipeline_process_pose_external():
    pipe = TrainingPipeline(exercise_id="squat")
    pipe.start()
    pose = _pose_from_knee_angle(165, datetime.now())
    coach = pipe.process_pose(pose)
    assert coach.status_text
    assert pipe.is_running
    pipe.stop()
    assert not pipe.is_running
