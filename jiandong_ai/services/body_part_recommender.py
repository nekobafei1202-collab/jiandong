"""无障碍语音选课的部位推荐引擎（规则版，不接大模型）。

数据源为 muscle_map 的动作×肌群强度表；口语部位词先归一到肌群组，
按强度 3→2→1 排序去重取 3-4 个动作，前后包「热身」「拉伸」书挡，
与现有课程数据（如 c_002）同模式。
"""

from __future__ import annotations

from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.widgets.muscle_map import action_muscle_map

# 口语部位词 → 规范部位
PART_ALIASES: dict[str, str] = {
    "腿": "leg",
    "腿部": "leg",
    "下肢": "leg",
    "臀腿": "leg",
    "核心": "core",
    "腹": "core",
    "腹部": "core",
    "腰腹": "core",
    "上肢": "upper",
    "胸": "upper",
    "胸部": "upper",
    "手臂": "upper",
    "背": "back",
    "背部": "back",
    "全身": "full",
}

# 规范部位 → 目标肌群组
_PART_GROUPS: dict[str, tuple[str, ...]] = {
    "leg": ("QUADS", "GLUTES", "HAMSTRINGS", "CALVES"),
    "core": ("CORE", "OBLIQUES"),
    "upper": ("CHEST", "TRICEPS", "SHOULDERS_FRONT"),
    "back": ("BACK_LOWER", "LATS"),
    "full": (),
}

PART_DISPLAY: dict[str, str] = {
    "leg": "腿部",
    "core": "核心",
    "upper": "上肢",
    "back": "背部",
    "full": "全身",
}

_WARMUP = "热身"
_STRETCH = "拉伸"


def resolve_part(keyword: str) -> str | None:
    """口语部位词 → 规范部位（leg/core/upper/back/full），无法识别返回 None。"""
    token = (keyword or "").strip()
    if token in PART_ALIASES:
        return PART_ALIASES[token]
    for word, part in PART_ALIASES.items():
        if len(word) >= 2 and word in token:
            return part
    return None


class BodyPartRecommender:
    """同一部位内推荐动作组合；「换一个」轮换同部位次优动作并记录已拒绝项。"""

    def __init__(self, *, pick_count: int = 3) -> None:
        self._pick_count = max(1, int(pick_count))
        self._part: str | None = None
        self._selected: list[str] = []  # 动作 key，不含书挡
        self._rejected: set[str] = set()

    @staticmethod
    def _ranked_candidates(part: str) -> list[str]:
        """按目标肌群最高强度 3→2→1 排序（同分保持表内顺序）。"""
        table = action_muscle_map()
        groups = _PART_GROUPS.get(part, ())
        scored: list[tuple[int, int, str]] = []
        for order, (key, muscles) in enumerate(table.items()):
            if groups:
                level = max((muscles.get(g, 0) for g in groups), default=0)
            else:
                level = max(muscles.values(), default=0)
            if level > 0:
                scored.append((-level, order, key))
        scored.sort()
        return [key for _, _, key in scored]

    def recommend(self, part: str) -> list[str]:
        """生成带热身/拉伸书挡的动作中文名列表；未知部位返回空列表。"""
        if part not in _PART_GROUPS:
            return []
        self._part = part
        self._rejected = set()
        self._selected = self._ranked_candidates(part)[: self._pick_count]
        return self._with_bookends(self._selected)

    def reroll(self) -> list[str]:
        """「换一个」：用同部位次优动作替换当前强度最低的一项，避免重复推荐。"""
        if self._part is None or not self._selected:
            return []
        candidates = [
            key
            for key in self._ranked_candidates(self._part)
            if key not in self._selected and key not in self._rejected
        ]
        if not candidates:
            # 候选耗尽：清空已拒绝项（保留当前选中）重新开始轮换。
            self._rejected = set()
            candidates = [
                key
                for key in self._ranked_candidates(self._part)
                if key not in self._selected
            ]
        if not candidates:
            return self._with_bookends(self._selected)
        replacement = candidates[0]
        ranked = self._ranked_candidates(self._part)
        # 替换当前选中里排名最低的动作。
        drop = min(self._selected, key=lambda k: ranked.index(k))
        self._rejected.add(drop)
        self._selected = [replacement if k == drop else k for k in self._selected]
        return self._with_bookends(self._selected)

    @staticmethod
    def _with_bookends(keys: list[str]) -> list[str]:
        return [_WARMUP, *(ExerciseKind.display_name(k) for k in keys), _STRETCH]

    @property
    def part(self) -> str | None:
        return self._part

    @property
    def selected(self) -> list[str]:
        return list(self._selected)

    @property
    def rejected(self) -> set[str]:
        return set(self._rejected)
