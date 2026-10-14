"""Muscle activation map: render front/back body SVGs colored by intensity.

Path data comes from Jsplice/MuscleMap (MIT) — see assets/muscle/MuscleMap-LICENSE.txt.
"""

from __future__ import annotations

from jiandong_ai.ai.action.exercise_kind import ExerciseKind
from jiandong_ai.widgets.muscle_map_data import BACK, FRONT

INTENSITY_COLORS = {
    3: "#1D4ED8",
    2: "#60A5FA",
    1: "#BFDBFE",
}
INACTIVE_COLOR = "#E5E7EB"
OUTLINE_COLOR = "#F3F4F6"
OUTLINE_STROKE = "#D1D5DB"

_ACTION_MUSCLES: dict[str, dict[str, int]] = {
    "squat": {"QUADS": 3, "GLUTES": 3, "HAMSTRINGS": 2, "CALVES": 1, "CORE": 1},
    "pushup": {"CHEST": 3, "TRICEPS": 3, "SHOULDERS_FRONT": 2, "CORE": 2},
    "reverse_lunge": {"QUADS": 3, "GLUTES": 3, "HAMSTRINGS": 2, "CALVES": 1},
    "plank": {"CORE": 3, "OBLIQUES": 2, "SHOULDERS_FRONT": 2, "BACK_LOWER": 1, "GLUTES": 1},
    "jumping_jack": {"CALVES": 2, "QUADS": 2, "SHOULDERS_SIDE": 2, "GLUTES": 1, "CORE": 1},
    "crunch": {"CORE": 3, "OBLIQUES": 2},
    "side_bridge": {"CORE": 3, "OBLIQUES": 3, "GLUTES": 1, "SHOULDERS_SIDE": 1},
    "dead_bug": {"CORE": 3, "OBLIQUES": 2, "SHOULDERS_FRONT": 1},
    "high_knees": {"QUADS": 2, "CALVES": 2, "CORE": 2, "GLUTES": 1},
    "glute_bridge": {"GLUTES": 3, "HAMSTRINGS": 2, "BACK_LOWER": 2, "CORE": 1},
}


def _action_key(action_name: str) -> str:
    for key in _ACTION_MUSCLES:
        check = getattr(ExerciseKind, f"is_{key}")
        if check(action_name):
            return key
    return ""


def activation_for_actions(action_names: list[str]) -> dict[str, int]:
    """Aggregate {muscle_group: intensity 1-3} over completed actions."""
    result: dict[str, int] = {}
    for name in action_names:
        if ExerciseKind.is_guide_only(name):
            continue
        for group, level in _ACTION_MUSCLES.get(_action_key(name), {}).items():
            result[group] = max(result.get(group, 0), level)
    return result


def render_muscle_svg(activation: dict[str, int], *, view: str = "front") -> str:
    """Full SVG string; activated muscle paths colored by intensity tier."""
    data = FRONT if view == "front" else BACK
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{data["viewBox"]}">'
    ]
    for d in data["outline"]:
        parts.append(
            f'<path d="{d}" fill="{OUTLINE_COLOR}" '
            f'stroke="{OUTLINE_STROKE}" stroke-width="2"/>'
        )
    for m in data["muscles"]:
        level = max(0, min(3, int(activation.get(m["group"], 0))))
        color = INTENSITY_COLORS.get(level, INACTIVE_COLOR)
        parts.append(f'<path id="{m["id"]}" d="{m["d"]}" fill="{color}"/>')
    parts.append("</svg>")
    return "".join(parts)


def write_muscle_svgs(action_names: list[str]) -> tuple[str | None, str | None]:
    """Render front/back SVGs to content-hashed temp files (unique name per
    action set, so the Flutter image cache never serves a stale body)."""
    import hashlib
    import tempfile
    from pathlib import Path

    try:
        activation = activation_for_actions(action_names)
        digest = hashlib.md5(
            "|".join(sorted(f"{g}:{v}" for g, v in activation.items())).encode()
        ).hexdigest()[:10]
        tmp = Path(tempfile.gettempdir())
        front = tmp / f"jiandong_muscle_front_{digest}.svg"
        back = tmp / f"jiandong_muscle_back_{digest}.svg"
        front.write_text(render_muscle_svg(activation, view="front"), encoding="utf-8")
        back.write_text(render_muscle_svg(activation, view="back"), encoding="utf-8")
        return str(front), str(back)
    except Exception:
        return None, None
