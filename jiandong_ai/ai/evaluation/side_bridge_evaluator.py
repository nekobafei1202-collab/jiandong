"""Side-bridge hold scoring: good-hold time ratio + body-line stability.

Reuses PlankEvaluator's session math; only the copy is side-bridge specific.
"""

from __future__ import annotations

from ..action.action_recognizer import ActionRecognitionResult
from ..action.side_bridge_config import SideBridgeConfig
from .action_evaluator import EvaluationResult
from .plank_evaluator import PlankEvaluator


class SideBridgeEvaluator(PlankEvaluator):
    def __init__(self, config: SideBridgeConfig | None = None) -> None:
        super().__init__(config or SideBridgeConfig.defaults)

    @property
    def config(self) -> SideBridgeConfig:
        return self._config  # type: ignore[return-value]

    def update_config(self, value: SideBridgeConfig) -> None:
        self._config = value

    def _feedback(self, action: ActionRecognitionResult) -> str:
        live = action.form_cue
        if live:
            return live
        if self._sag_frames == 0 and self._pike_frames == 0:
            return "姿势良好"
        return (
            "髋部不要下沉"
            if self._sag_frames >= self._pike_frames
            else "髋部不要抬太高"
        )
