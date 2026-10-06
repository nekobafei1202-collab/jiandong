from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: str
    name: str
    email: str
    avatar: str | None = None
    training_days: int = 0


@dataclass(frozen=True)
class Exercise:
    id: str
    name: str
    duration: int
    difficulty: str
    category: str
    description: str = ""
    body_part: str = ""
    actions: tuple[str, ...] = ()
    cover_asset: str | None = None


@dataclass(frozen=True)
class CustomPlan:
    actions: tuple[str, ...]


@dataclass(frozen=True)
class RecordAction:
    action_name: str
    reps: int
    avg_score: int | None = None
    feedback: str | None = None

    def to_json(self) -> dict:
        data: dict = {"actionName": self.action_name, "reps": self.reps}
        if self.avg_score is not None:
            data["avgScore"] = self.avg_score
        if self.feedback is not None:
            data["feedback"] = self.feedback
        return data

    @classmethod
    def from_json(cls, data: dict) -> RecordAction:
        return cls(
            action_name=str(data.get("actionName") or ""),
            reps=int(data.get("reps") or 0),
            avg_score=(
                int(data["avgScore"]) if data.get("avgScore") is not None else None
            ),
            feedback=data.get("feedback"),
        )


@dataclass(frozen=True)
class TrainingRecord:
    id: str
    exercise_name: str
    duration: int
    score: int
    date: str  # ISO
    calories: int | None = None
    total_reps: int | None = None
    actions: tuple[RecordAction, ...] = ()

    def to_json(self) -> dict:
        data: dict = {
            "id": self.id,
            "exerciseName": self.exercise_name,
            "duration": self.duration,
            "score": self.score,
            "date": self.date,
        }
        if self.calories is not None:
            data["calories"] = self.calories
        if self.total_reps is not None:
            data["totalReps"] = self.total_reps
        if self.actions:
            data["actions"] = [a.to_json() for a in self.actions]
        return data

    @classmethod
    def from_json(cls, data: dict) -> TrainingRecord:
        actions_raw = data.get("actions") or []
        actions = tuple(
            RecordAction.from_json(dict(e))
            for e in actions_raw
            if isinstance(e, dict)
        )
        return cls(
            id=str(data.get("id") or ""),
            exercise_name=str(data.get("exerciseName") or ""),
            duration=int(data.get("duration") or 0),
            score=int(data.get("score") or 0),
            date=str(data.get("date") or ""),
            calories=(
                int(data["calories"]) if data.get("calories") is not None else None
            ),
            total_reps=(
                int(data["totalReps"]) if data.get("totalReps") is not None else None
            ),
            actions=actions,
        )


@dataclass(frozen=True)
class WeeklyStat:
    label: str
    minutes: int
