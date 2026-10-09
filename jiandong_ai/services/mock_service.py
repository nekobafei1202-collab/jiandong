from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from jiandong_ai.app.constants import MOCK_EMAIL, MOCK_PASSWORD
from jiandong_ai.models import (
    CustomPlan,
    Exercise,
    TrainingRecord,
    User,
    WeeklyStat,
)

_DATA_FILE = "jiandong_data.json"


class AppSession:
    current_user: User | None = None

    @classmethod
    def set_user(cls, user: User | None) -> None:
        cls.current_user = user

    @classmethod
    def clear(cls) -> None:
        cls.current_user = None


class MockService:
    _instance: MockService | None = None

    def __init__(self) -> None:
        self._history: list[TrainingRecord] | None = None
        self._custom_plan: CustomPlan | None = None
        self._plan_done: list[bool] = [True, True, False]
        self._store_available = False
        self._store_path: Path | None = None
        self._plan_listeners: list[Callable[[], None]] = []
        self._default_user = User(
            id="u_001",
            name="小健",
            email=MOCK_EMAIL,
            training_days=12,
        )
        self._default_plan_actions = ("深蹲", "俯卧撑", "开合跳")

    @classmethod
    def instance(cls) -> MockService:
        if cls._instance is None:
            cls._instance = MockService()
        return cls._instance

    def init(self, data_dir: Path | None = None) -> None:
        try:
            base = data_dir or Path.home() / ".jiandong_ai"
            base.mkdir(parents=True, exist_ok=True)
            self._store_path = base / _DATA_FILE
            if self._store_path.exists():
                decoded = json.loads(self._store_path.read_text(encoding="utf-8"))
                if isinstance(decoded, dict):
                    self._restore(decoded)
            self._store_available = True
        except Exception:
            self._store_available = False

    def on_plan_changed(self, cb: Callable[[], None]) -> None:
        self._plan_listeners.append(cb)

    def _notify_plan(self) -> None:
        for cb in list(self._plan_listeners):
            try:
                cb()
            except Exception:
                pass

    def _restore(self, data: dict) -> None:
        plan = data.get("plan")
        if isinstance(plan, dict):
            actions = [a for a in (plan.get("actions") or []) if isinstance(a, str)]
            done = [bool(e) for e in (plan.get("done") or [])]
            if actions:
                self._custom_plan = CustomPlan(actions=tuple(actions))
                self._plan_done = done or [False] * len(actions)
        history = data.get("history")
        if isinstance(history, list):
            self._history = [
                TrainingRecord.from_json(dict(e))
                for e in history
                if isinstance(e, dict)
            ]

    def _save(self) -> None:
        if not self._store_available or self._store_path is None:
            return
        try:
            payload = {
                "plan": {
                    "actions": self.get_today_plan_actions(),
                    "done": self._plan_done,
                },
                "history": [r.to_json() for r in self._ensure_history()],
            }
            self._store_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def login(self, account: str, password: str) -> User | None:
        time.sleep(0.15)
        if account.strip().lower() == MOCK_EMAIL and password == MOCK_PASSWORD:
            AppSession.set_user(self._default_user)
            return self._default_user
        return None

    def register(self, name: str, account: str, password: str) -> User:
        time.sleep(0.15)
        user = User(
            id=f"u_{int(time.time() * 1000)}",
            name=name.strip() or "新用户",
            email=account.strip(),
            training_days=0,
        )
        AppSession.set_user(user)
        return user

    def get_current_user(self) -> User:
        return AppSession.current_user or self._default_user

    def get_today_plan(self) -> list[tuple[str, bool]]:
        actions = list(
            self._custom_plan.actions
            if self._custom_plan
            else self._default_plan_actions
        )
        done = self._plan_done
        return [
            (actions[i], done[i] if i < len(done) else False)
            for i in range(len(actions))
        ]

    def get_today_plan_actions(self) -> list[str]:
        return list(
            self._custom_plan.actions
            if self._custom_plan
            else self._default_plan_actions
        )

    def get_today_completed_count(self) -> int:
        return sum(1 for _, d in self.get_today_plan() if d)

    def get_today_goal_count(self) -> int:
        return len(self.get_today_plan())

    def set_today_plan_actions(self, actions: list[str]) -> None:
        cleaned = tuple(a.strip() for a in actions if a.strip())
        self._custom_plan = CustomPlan(actions=cleaned)
        self._plan_done = [False] * len(cleaned)
        self._notify_plan()
        self._save()

    def mark_plan_done(self, action: str) -> None:
        name = action.strip()
        if not name:
            return
        actions = self.get_today_plan_actions()
        if len(self._plan_done) < len(actions):
            self._plan_done = self._plan_done + [False] * (
                len(actions) - len(self._plan_done)
            )
        for i, a in enumerate(actions):
            if a == name and not self._plan_done[i]:
                self._plan_done[i] = True
                self._notify_plan()
                self._save()
                return

    def first_incomplete_plan_index(self) -> int:
        plan = self.get_today_plan()
        if not plan:
            return 0
        for i, (_, done) in enumerate(plan):
            if not done:
                return i
        return 0

    def get_quick_target(self, action: str) -> str:
        return {
            "深蹲": "15 个",
            "俯卧撑": "12 个",
            "开合跳": "30 个",
            "抬臂": "20 个",
            "平板支撑": "30 秒",
        }.get(action, "")

    def get_recommended_workouts(self) -> list[Exercise]:
        return [
            Exercise(
                id="w_001",
                name="燃脂训练",
                duration=15,
                difficulty="入门",
                category="全身",
                body_part="全身",
                description="高效有氧组合，帮助提升心率与燃脂效率。",
                actions=("热身", "开合跳", "深蹲", "高抬腿", "拉伸"),
                cover_asset="assets/images/courses/featured_hiit.png",
            ),
            Exercise(
                id="w_002",
                name="下肢力量",
                duration=20,
                difficulty="中级",
                category="下肢",
                body_part="下肢",
                description="聚焦臀腿力量，改善稳定与爆发力。",
                actions=("热身", "深蹲", "弓步蹲", "臀桥", "拉伸"),
                cover_asset="assets/images/courses/featured_squat.png",
            ),
            Exercise(
                id="w_003",
                name="全身拉伸",
                duration=10,
                difficulty="入门",
                category="拉伸",
                body_part="全身",
                description="放松筋膜，缓解训练后的紧绷感。",
                actions=("颈部放松", "肩部拉伸", "髋部打开", "腿后侧拉伸"),
                cover_asset="assets/images/courses/featured_yoga.png",
            ),
        ]

    def get_quick_exercises(self) -> list[str]:
        return ["深蹲", "俯卧撑", "开合跳", "抬臂", "平板支撑"]

    def get_courses(self, category: str = "全部") -> list[Exercise]:
        all_courses = [
            Exercise(
                id="c_001",
                name="新手全身训练",
                duration=15,
                difficulty="入门",
                category="新手",
                body_part="全身",
                description="适合零基础用户的入门课程，动作简单、节奏可控。",
                actions=("热身", "深蹲", "开合跳", "抬臂", "拉伸"),
                cover_asset="assets/images/courses/c_001.png",
            ),
            Exercise(
                id="c_002",
                name="下肢力量训练",
                duration=20,
                difficulty="中级",
                category="下肢",
                body_part="下肢",
                description="强化下肢肌群，提升日常走路与跑步支撑力。",
                actions=("热身", "深蹲", "弓步", "提踵", "拉伸"),
                cover_asset="assets/images/courses/c_002.png",
            ),
            Exercise(
                id="c_003",
                name="核心稳定训练",
                duration=12,
                difficulty="入门",
                category="核心",
                body_part="核心",
                description="激活核心，改善姿态稳定性。",
                actions=("热身", "平板支撑", "死虫式", "侧桥", "拉伸"),
                cover_asset="assets/images/courses/c_003.png",
            ),
            Exercise(
                id="c_004",
                name="上肢塑形训练",
                duration=18,
                difficulty="中级",
                category="上肢",
                body_part="上肢",
                description="针对肩背手臂的力量与塑形课程。",
                actions=("热身", "俯身划船", "俯卧撑", "手臂环绕", "拉伸"),
                cover_asset="assets/images/courses/c_004.png",
            ),
            Exercise(
                id="c_005",
                name="放松拉伸课程",
                duration=10,
                difficulty="入门",
                category="拉伸",
                body_part="全身",
                description="训练后恢复专用，帮助放松紧张肌肉。",
                actions=("呼吸调整", "肩颈拉伸", "腰背放松", "腿部拉伸"),
                cover_asset="assets/images/courses/c_005.png",
            ),
        ]
        if category == "全部":
            return all_courses
        return [e for e in all_courses if e.category == category]

    def get_course_by_id(self, id_: str) -> Exercise | None:
        for e in self.get_courses():
            if e.id == id_:
                return e
        return None

    def get_today_stats(self) -> dict:
        history = self._ensure_history()
        now = datetime.now()

        def is_today(iso: str) -> bool:
            try:
                d = datetime.fromisoformat(iso)
            except ValueError:
                return False
            return d.year == now.year and d.month == now.month and d.day == now.day

        today = [r for r in history if is_today(r.date)]
        minutes = sum(r.duration for r in today)
        avg_score = (
            round(sum(r.score for r in today) / len(today)) if today else 0
        )
        calories = sum(
            (r.calories if r.calories is not None else r.duration * 4) for r in today
        )
        total_minutes = sum(r.duration for r in history)
        return {
            "durationMinutes": minutes,
            "sessionCount": len(today),
            "avgScore": avg_score,
            "todayCalories": calories,
            "todaySets": len(today),
            "totalHours": round(total_minutes / 60 * 10) / 10,
        }

    def get_streak_days(self) -> int:
        days: set[datetime] = set()
        for r in self._ensure_history():
            try:
                d = datetime.fromisoformat(r.date)
                days.add(datetime(d.year, d.month, d.day))
            except ValueError:
                continue
        if not days:
            return 0
        now = datetime.now()
        cursor = datetime(now.year, now.month, now.day)
        if cursor not in days:
            cursor -= timedelta(days=1)
        streak = 0
        while cursor in days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    def get_weekly_stats(self) -> list[WeeklyStat]:
        labels = ["一", "二", "三", "四", "五", "六", "日"]
        now = datetime.now()
        today = datetime(now.year, now.month, now.day)
        monday = today - timedelta(days=today.weekday())
        minutes = [0] * 7
        for r in self._ensure_history():
            try:
                d = datetime.fromisoformat(r.date)
                day = datetime(d.year, d.month, d.day)
            except ValueError:
                continue
            diff = (day - monday).days
            if 0 <= diff < 7:
                minutes[diff] += r.duration
        return [WeeklyStat(label=labels[i], minutes=minutes[i]) for i in range(7)]

    def get_training_history(self) -> list[TrainingRecord]:
        return list(self._ensure_history())

    def _ensure_history(self) -> list[TrainingRecord]:
        if self._history is not None:
            return self._history
        # Start empty so history reflects real sessions only.
        self._history = []
        return self._history

    def add_training_record(self, record: TrainingRecord) -> None:
        time.sleep(0.05)
        self._ensure_history().insert(0, record)
        self._save()

    def delete_training_record(self, record_id: str) -> bool:
        history = self._ensure_history()
        for i, r in enumerate(history):
            if r.id == record_id:
                history.pop(i)
                self._save()
                return True
        return False
