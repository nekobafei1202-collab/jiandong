"""Mutable pointer through a course actions list.

Pure logic — no UI deps — so queue advance can be unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..action.exercise_kind import ExerciseKind


@dataclass
class CourseActionResult:
    action_name: str
    reps: int
    avg_score: int | None = None
    manual: bool = False


class CourseActionQueue:
    def __init__(self, actions: list[str], start_index: int = 0) -> None:
        cleaned = [a for a in actions if a and a.strip()] if actions else []
        if not cleaned:
            cleaned = ["深蹲"]
        self.actions: list[str] = list(cleaned)
        self._index = self._clamp_index(start_index, len(self.actions))
        self._completed: list[CourseActionResult] = []
        self._visit_recorded = False

    @classmethod
    def from_args(
        cls,
        *,
        actions: list[str] | None = None,
        action_name: str | None = None,
        exercise_id: str | None = None,
        action_index: int | None = None,
    ) -> CourseActionQueue:
        items: list[str] = []
        if actions:
            items.extend(e.strip() for e in actions if e and e.strip())
        if not items:
            single = (action_name or exercise_id or "").strip()
            if single:
                items.append(single)
        return cls(actions=items, start_index=action_index or 0)

    @staticmethod
    def _clamp_index(index: int, length: int) -> int:
        if length <= 0:
            return 0
        if index < 0:
            return 0
        if index >= length:
            return length - 1
        return index

    @property
    def index(self) -> int:
        return self._index

    @property
    def total(self) -> int:
        return len(self.actions)

    @property
    def is_multi(self) -> bool:
        return self.total > 1

    @property
    def has_next(self) -> bool:
        return self._index + 1 < self.total

    @property
    def has_previous(self) -> bool:
        return self._index > 0

    @property
    def is_last(self) -> bool:
        return not self.has_next

    @property
    def current_visit_recorded(self) -> bool:
        return self._visit_recorded

    @property
    def current(self) -> str:
        return self.actions[self._index]

    @property
    def current_display_name(self) -> str:
        return ExerciseKind.display_name(self.current)

    @property
    def current_supports_auto_detect(self) -> bool:
        return ExerciseKind.supports_auto_detect(self.current)

    @property
    def current_is_manual(self) -> bool:
        return ExerciseKind.is_manual_complete(self.current)

    @property
    def progress_label(self) -> str:
        if not self.is_multi:
            return ""
        return f"第 {self._index + 1}/{self.total} 个"

    @property
    def hud_title(self) -> str:
        name = self.current_display_name
        progress = self.progress_label
        if not progress:
            return name
        return f"{progress} · {name}"

    @property
    def completed(self) -> list[CourseActionResult]:
        return list(self._completed)

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    @property
    def total_reps(self) -> int:
        return sum(
            r.reps
            for r in self._completed
            if not ExerciseKind.is_guide_only(r.action_name)
        )

    @property
    def average_score(self) -> int | None:
        scored = [
            r.avg_score
            for r in self._completed
            if r.avg_score
            and r.avg_score > 0
            and not ExerciseKind.is_guide_only(r.action_name)
        ]
        if not scored:
            return None
        return round(sum(scored) / len(scored))

    def complete_current_and_advance(
        self,
        *,
        reps: int,
        avg_score: int | None = None,
        manual: bool | None = None,
    ) -> bool:
        self._store_current(reps=reps, avg_score=avg_score, manual=manual)
        if not self.has_next:
            return False
        self._index += 1
        self._visit_recorded = False
        return True

    def next(
        self,
        *,
        reps: int,
        avg_score: int | None = None,
        manual: bool | None = None,
    ) -> bool:
        return self.complete_current_and_advance(
            reps=reps, avg_score=avg_score, manual=manual
        )

    def previous(self) -> bool:
        if not self.has_previous:
            return False
        self._index -= 1
        self._visit_recorded = False
        return True

    def go_to(self, index: int) -> bool:
        if index < 0 or index >= self.total:
            return False
        if index == self._index:
            return True
        self._index = index
        self._visit_recorded = False
        return True

    def record_current_only(
        self,
        *,
        reps: int,
        avg_score: int | None = None,
        manual: bool | None = None,
    ) -> None:
        self._store_current(reps=reps, avg_score=avg_score, manual=manual)

    def peek_last_completed(self) -> CourseActionResult | None:
        if not self._completed:
            return None
        return self._completed[-1]

    def pop_last_completed(self) -> CourseActionResult | None:
        if not self._completed:
            return None
        return self._completed.pop()

    def _store_current(
        self,
        *,
        reps: int,
        avg_score: int | None = None,
        manual: bool | None = None,
    ) -> None:
        guide = ExerciseKind.is_guide_only(self.current)
        self._completed.append(
            CourseActionResult(
                action_name=self.current_display_name,
                reps=0 if guide else reps,
                avg_score=None if guide else avg_score,
                manual=True if guide else (
                    self.current_is_manual if manual is None else manual
                ),
            )
        )
        self._visit_recorded = True
