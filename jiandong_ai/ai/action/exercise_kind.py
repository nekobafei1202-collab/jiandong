from __future__ import annotations


class ExerciseKind:
    squat = "squat"
    pushup = "pushup"
    reverse_lunge = "reverse_lunge"
    plank = "plank"
    jumping_jack = "jumping_jack"
    crunch = "crunch"
    high_knees = "high_knees"
    glute_bridge = "glute_bridge"

    squat_label = "深蹲"
    pushup_label = "俯卧撑"
    reverse_lunge_label = "弓步蹲"
    plank_label = "平板支撑"
    jumping_jack_label = "开合跳"
    crunch_label = "卷腹"
    high_knees_label = "高抬腿"
    glute_bridge_label = "臀桥"

    squat_demo_dir = "assets/demo/squat_white_mannequin"
    pushup_demo_dir = "assets/demo/pushup_white_mannequin"
    reverse_lunge_demo_dir = "assets/demo/reverse_lunge_white_mannequin"
    plank_demo_dir = "assets/demo/plank_white_mannequin"
    jumping_jack_demo_dir = "assets/demo/jumping_jack_white_mannequin"
    crunch_demo_dir = "assets/demo/crunch_white_mannequin"
    high_knees_demo_dir = "assets/demo/high_knees_white_mannequin"

    @staticmethod
    def _token(id_: str | None) -> str:
        return (id_ or "").strip().lower().replace("-", "_").replace(" ", "_")

    @staticmethod
    def _is_any(id_: str | None, keys: set[str]) -> bool:
        return ExerciseKind._token(id_) in keys

    @classmethod
    def is_pushup(cls, id_: str | None) -> bool:
        s = (id_ or "").strip().lower()
        return s in {cls.pushup, "push-up", "push_up", cls.pushup_label}

    @classmethod
    def is_squat(cls, id_: str | None) -> bool:
        s = (id_ or "").strip().lower()
        return s in {cls.squat, cls.squat_label}

    @classmethod
    def is_reverse_lunge(cls, id_: str | None) -> bool:
        return cls._is_any(
            id_, {"reverse_lunge", "lunge", "lunge_squat", "弓步蹲", "弓步"}
        )

    @classmethod
    def is_plank(cls, id_: str | None) -> bool:
        return cls._is_any(id_, {"plank", "forearm_plank", "平板支撑"})

    @classmethod
    def is_jumping_jack(cls, id_: str | None) -> bool:
        return cls._is_any(
            id_, {"jumping_jack", "jumping_jacks", "jumpingjack", "开合跳"}
        )

    @classmethod
    def is_crunch(cls, id_: str | None) -> bool:
        return cls._is_any(id_, {"crunch", "crunches", "卷腹"})

    @classmethod
    def is_high_knees(cls, id_: str | None) -> bool:
        return cls._is_any(id_, {"high_knees", "high_knee", "highknees", "高抬腿"})

    @classmethod
    def is_glute_bridge(cls, id_: str | None) -> bool:
        return cls._is_any(
            id_, {"glute_bridge", "glutebridge", "hip_bridge", "臀桥"}
        )

    @classmethod
    def normalize(cls, id_: str | None) -> str:
        if id_ is None or not id_.strip():
            return cls.squat
        if cls.is_pushup(id_):
            return cls.pushup
        if cls.is_reverse_lunge(id_):
            return cls.reverse_lunge
        if cls.is_plank(id_):
            return cls.plank
        if cls.is_jumping_jack(id_):
            return cls.jumping_jack
        if cls.is_high_knees(id_):
            return cls.high_knees
        if cls.is_glute_bridge(id_):
            return cls.glute_bridge
        if cls.is_squat(id_):
            return cls.squat
        return cls.squat

    @classmethod
    def supports_auto_detect(cls, id_: str | None) -> bool:
        if id_ is None or not id_.strip():
            return True
        return (
            cls.is_squat(id_)
            or cls.is_pushup(id_)
            or cls.is_reverse_lunge(id_)
            or cls.is_plank(id_)
            or cls.is_jumping_jack(id_)
            or cls.is_high_knees(id_)
            or cls.is_glute_bridge(id_)
        )

    @classmethod
    def is_manual_complete(cls, id_: str | None) -> bool:
        return not cls.supports_auto_detect(id_)

    @classmethod
    def is_guide_only(cls, id_: str | None) -> bool:
        """Warmup / cooldown bookends: show in queue, no count or pose score."""
        s = (id_ or "").strip()
        return s in {"热身", "拉伸"} or cls._token(id_) in {
            "warmup",
            "warm_up",
            "stretch",
            "cooldown",
            "cool_down",
        }

    @classmethod
    def rest_seconds(cls, id_: str | None) -> int:
        """Inter-set / inter-action rest duration for the completed exercise."""
        if cls.is_guide_only(id_):
            return 0
        if cls.is_jumping_jack(id_) or cls.is_high_knees(id_):
            return 30
        if cls.is_plank(id_):
            return 45
        return 60

    @classmethod
    def display_name(cls, id_: str | None) -> str:
        if id_ is None or not id_.strip():
            return cls.squat_label
        if cls.is_pushup(id_):
            return cls.pushup_label
        if cls.is_reverse_lunge(id_):
            return cls.reverse_lunge_label
        if cls.is_plank(id_):
            return cls.plank_label
        if cls.is_jumping_jack(id_):
            return cls.jumping_jack_label
        if cls.is_crunch(id_):
            return cls.crunch_label
        if cls.is_high_knees(id_):
            return cls.high_knees_label
        if cls.is_glute_bridge(id_):
            return cls.glute_bridge_label
        if cls.is_squat(id_):
            return cls.squat_label
        return id_.strip()

    @classmethod
    def shows_joint_angle(cls, id_: str | None) -> bool:
        return not cls.is_jumping_jack(id_) and not cls.is_high_knees(id_)

    @classmethod
    def demo_asset_dir(cls, id_: str | None) -> str | None:
        if cls.is_pushup(id_):
            return cls.pushup_demo_dir
        if cls.is_squat(id_) or id_ is None or not str(id_).strip():
            return cls.squat_demo_dir
        if cls.is_reverse_lunge(id_):
            return cls.reverse_lunge_demo_dir
        if cls.is_plank(id_):
            return cls.plank_demo_dir
        if cls.is_jumping_jack(id_):
            return cls.jumping_jack_demo_dir
        if cls.is_crunch(id_):
            return cls.crunch_demo_dir
        if cls.is_high_knees(id_):
            return cls.high_knees_demo_dir
        return None
