from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pushup_frame_data import PushupFrameData, PushupRepTrajectory
    from .squat_frame_data import SquatFrameData, SquatRepTrajectory
    from ..pose.pose_result import PoseResult


class SquatMachineState(str, Enum):
    waiting_person = "waitingPerson"
    standing = "standing"
    down = "down"
    bottom = "bottom"
    up = "up"


class ActionPhase(str, Enum):
    preparing = "preparing"
    standing = "standing"
    squatting = "squatting"
    rising = "rising"
    completed_rep = "completedRep"
    no_person = "noPerson"


@dataclass
class ActionRecognitionResult:
    phase: ActionPhase
    machine_state: SquatMachineState
    rep_count: int
    knee_angle: float | None = None
    left_knee_angle: float | None = None
    right_knee_angle: float | None = None
    just_completed_rep: bool = False
    reached_bottom: bool = False
    depth_ok: bool = False
    has_reliable_pose: bool = False
    rep_min_knee_angle: float | None = None
    rep_max_knee_angle: float | None = None
    range_of_motion: float | None = None
    current_rep_frames: list = field(default_factory=list)
    last_completed_trajectory: object | None = None
    elbow_angle: float | None = None
    left_elbow_angle: float | None = None
    right_elbow_angle: float | None = None
    body_line_angle: float | None = None
    elbow_flare_angle: float | None = None
    current_pushup_frames: list = field(default_factory=list)
    last_pushup_trajectory: object | None = None
    form_cue: str | None = None
    leg_spread_ratio: float | None = None
    arm_raise_ratio: float | None = None

    @property
    def machine_state_label(self) -> str:
        return {
            SquatMachineState.waiting_person: "WAITING",
            SquatMachineState.standing: "STANDING",
            SquatMachineState.down: "DOWN",
            SquatMachineState.bottom: "BOTTOM",
            SquatMachineState.up: "UP",
        }[self.machine_state]


class ActionRecognizer(ABC):
    @abstractmethod
    def recognize(self, pose: PoseResult) -> ActionRecognitionResult: ...

    @abstractmethod
    def reset(self) -> None: ...

    @property
    @abstractmethod
    def action_name(self) -> str: ...
