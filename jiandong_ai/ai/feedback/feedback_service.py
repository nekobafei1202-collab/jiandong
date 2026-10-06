from __future__ import annotations

from dataclasses import dataclass

from ..action.action_recognizer import (
    ActionPhase,
    ActionRecognitionResult,
    SquatMachineState,
)
from ..action.exercise_kind import ExerciseKind
from ..evaluation.action_evaluator import EvaluationResult


@dataclass
class CoachFeedback:
    status_text: str
    message: str
    score_text: str = "--"
    knee_angle_text: str = "--"
    machine_state_label: str = "WAITING"
    is_correct: bool = False


class FeedbackService:
    @staticmethod
    def opening_line(exercise_id: str | None) -> str:
        if ExerciseKind.is_pushup(exercise_id):
            return "保持平板支撑后开始下压"
        if ExerciseKind.is_reverse_lunge(exercise_id):
            return "前腿屈膝下沉，躯干保持直立"
        if ExerciseKind.is_plank(exercise_id):
            return "侧对镜头，身体成一条直线"
        if ExerciseKind.is_jumping_jack(exercise_id):
            return "手脚同时打开，再收回并拢"
        if ExerciseKind.is_high_knees(exercise_id):
            return "膝盖抬向髋部，躯干保持直立"
        if ExerciseKind.is_glute_bridge(exercise_id):
            return "请侧对镜头仰卧，靠臀部把髋顶起"
        return "站稳后开始下蹲"

    @staticmethod
    def ready_line(exercise_id: str | None) -> str:
        if ExerciseKind.is_pushup(exercise_id):
            return "请进入摄像头画面，准备平板支撑"
        if ExerciseKind.is_glute_bridge(exercise_id):
            return "请侧对镜头仰卧，肩背贴地后开始"
        if ExerciseKind.is_plank(exercise_id):
            return "请侧对镜头，双手撑地成一条直线"
        if ExerciseKind.is_reverse_lunge(exercise_id):
            return "请侧身站到镜头前"
        return "请站到摄像头前，点击开始训练"

    def generate(
        self,
        *,
        action: ActionRecognitionResult,
        evaluation: EvaluationResult | None = None,
        is_running: bool = False,
        is_paused: bool = False,
        exercise_id: str | None = None,
    ) -> CoachFeedback:
        scored = evaluation is not None and evaluation.score > 0
        score_text = "--" if (not is_running or not scored) else str(evaluation.score)
        knee_text = self._angle_text(action, exercise_id)

        if not is_running:
            return CoachFeedback(
                status_text="准备开始",
                message=self.ready_line(exercise_id),
            )
        if is_paused:
            return CoachFeedback(
                status_text="已暂停",
                message="点击继续以恢复 AI 分析",
                score_text=score_text,
                knee_angle_text=knee_text,
                machine_state_label=action.machine_state_label,
                is_correct=bool(evaluation and evaluation.is_correct),
            )

        status = self._status_text(action, exercise_id)
        message = (
            (evaluation.feedback if evaluation else None)
            or action.form_cue
            or self._default_message(action, exercise_id)
        )
        return CoachFeedback(
            status_text=status,
            message=message,
            score_text=score_text,
            knee_angle_text=knee_text,
            machine_state_label=action.machine_state_label,
            is_correct=bool(evaluation and evaluation.is_correct),
        )

    def _angle_text(
        self, action: ActionRecognitionResult, exercise_id: str | None
    ) -> str:
        if not ExerciseKind.shows_joint_angle(exercise_id):
            return "--"
        angle = (
            action.body_line_angle
            if ExerciseKind.is_plank(exercise_id)
            else (action.knee_angle or action.elbow_angle or action.body_line_angle)
        )
        if angle is None:
            return "--"
        return f"{angle:.0f}°"

    def _status_text(
        self, action: ActionRecognitionResult, exercise_id: str | None
    ) -> str:
        pushup = ExerciseKind.is_pushup(exercise_id)
        plank = ExerciseKind.is_plank(exercise_id)
        bridge = ExerciseKind.is_glute_bridge(exercise_id)
        jack = ExerciseKind.is_jumping_jack(exercise_id)
        knees = ExerciseKind.is_high_knees(exercise_id)
        state = action.machine_state
        if state == SquatMachineState.waiting_person:
            return "未检测到人体" if action.phase == ActionPhase.no_person else "准备中"
        if state == SquatMachineState.standing:
            if pushup or plank:
                return "保持" if plank else "平板"
            if bridge:
                return "躺平"
            if jack:
                return "并拢"
            if knees:
                return "站立"
            return "站立"
        if state == SquatMachineState.down:
            if pushup:
                return "下压中"
            if bridge:
                return "顶髋"
            if plank:
                return "调整"
            return "下蹲中"
        if state == SquatMachineState.bottom:
            if pushup:
                return "最低点"
            if plank:
                return "塌腰"
            if bridge:
                return "顶点"
            if jack:
                return "打开"
            if knees:
                return "抬膝"
            return "蹲到底"
        if state == SquatMachineState.up:
            if pushup:
                return "撑起"
            if plank:
                return "翘臀"
            if bridge:
                return "放下"
            if knees:
                return "落下"
            return "起身"
        return "准备中"

    def _default_message(
        self, action: ActionRecognitionResult, exercise_id: str | None
    ) -> str:
        if action.phase == ActionPhase.no_person:
            if ExerciseKind.is_glute_bridge(exercise_id):
                return "请侧对镜头，让肩、髋、膝进入画面"
            if ExerciseKind.is_plank(exercise_id):
                return "请侧对镜头，让肩、髋、踝进入画面"
            return "请调整位置，确保全身进入摄像头"
        state = action.machine_state
        if state in (SquatMachineState.waiting_person, SquatMachineState.standing):
            return self.opening_line(exercise_id)
        if state == SquatMachineState.down:
            if ExerciseKind.is_pushup(exercise_id):
                return "半程偷懒"
            if ExerciseKind.is_glute_bridge(exercise_id):
                return "继续顶髋，臀肌发力"
            return "下蹲幅度可以再大一些"
        if state == SquatMachineState.bottom:
            if ExerciseKind.is_plank(exercise_id):
                return "塌腰"
            if ExerciseKind.is_glute_bridge(exercise_id):
                return "顶点稍停，腰不要拱起"
            if ExerciseKind.is_high_knees(exercise_id):
                return "膝盖再抬高一些"
            return "动作标准"
        if state == SquatMachineState.up:
            if ExerciseKind.is_pushup(exercise_id):
                return "身体保持一条直线"
            if ExerciseKind.is_plank(exercise_id):
                return "翘臀"
            if ExerciseKind.is_glute_bridge(exercise_id):
                return "有控制地放下"
            if ExerciseKind.is_high_knees(exercise_id):
                return "轻快落地"
            return "动作保持稳定一些"
        return self.opening_line(exercise_id)
