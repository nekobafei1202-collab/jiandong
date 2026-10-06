from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from .pose_result import PoseResult


class PoseDetector(ABC):
    @abstractmethod
    def detect(self, frame, *, timestamp: datetime | None = None) -> PoseResult:
        """Detect pose from a BGR numpy frame or pre-parsed payload."""

    def close(self) -> None:
        return None
