"""Maps course action names to intro copy + bundled pose images."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionGuide:
    name: str
    image_asset: str
    summary: str
    cues: tuple[str, ...]
    target: str


class ActionGuideCatalog:
    _DIR = "assets/actions"

    fallback = ActionGuide(
        name="动作",
        image_asset=f"{_DIR}/warmup.png",
        summary="按课程节奏完成动作，全程保持呼吸平稳，动作幅度以自己能控制为准。",
        cues=(
            "先摆好起始姿势，再开始发力",
            "核心收紧，避免用惯性甩动",
            "感到明显不适时立刻停下",
        ),
        target="全身",
    )

    _BY_NAME: dict[str, ActionGuide] = {
        "深蹲": ActionGuide(
            name="深蹲",
            image_asset=f"{_DIR}/squat.png",
            summary="深蹲是下肢基础力量动作。髋部后坐、膝盖随脚尖方向弯曲，再蹬地站起。适合建立腿部与臀部力量。",
            cues=(
                "双脚约与肩同宽，脚尖略外展",
                "下蹲时膝盖不要过度内扣",
                "胸口尽量保持朝前，腰背不要过度塌陷",
                "站起时脚跟发力，臀部收紧",
            ),
            target="股四头肌、臀大肌",
        ),
        "俯卧撑": ActionGuide(
            name="俯卧撑",
            image_asset=f"{_DIR}/pushup.png",
            summary="俯卧撑锻炼胸、肩与肱三头肌，同时考验核心稳定。身体成一条直线，屈肘下压再撑起。",
            cues=(
                "双手略宽于肩，指尖朝前",
                "从头到脚跟保持一条直线",
                "下落时肘部约呈 45 度打开",
                "不要塌腰或耸肩",
            ),
            target="胸大肌、三角肌前束、肱三头肌",
        ),
        "开合跳": ActionGuide(
            name="开合跳",
            image_asset=f"{_DIR}/cardio.png",
            summary="开合跳是经典有氧热身动作，通过跳跃开合手脚提升心率与全身协调性。",
            cues=(
                "落地时膝盖微屈缓冲",
                "手臂上举与脚下开合同步",
                "保持核心收紧，避免过度后仰",
                "呼吸跟随节奏，不要憋气",
            ),
            target="心肺、小腿、肩带",
        ),
        "高抬腿": ActionGuide(
            name="高抬腿",
            image_asset=f"{_DIR}/high_knees.png",
            summary="原地高抬腿强调髋屈与步频，帮助热身并激活核心与髋部肌群。",
            cues=(
                "膝盖尽量抬至髋高",
                "脚掌轻快落地",
                "躯干保持直立，不要后仰",
                "摆臂自然配合",
            ),
            target="髂腰肌、核心、心肺",
        ),
        "热身": ActionGuide(
            name="热身",
            image_asset=f"{_DIR}/warmup.png",
            summary="热身用于提高体温与关节活动度，降低正式训练前的僵硬与受伤风险。",
            cues=(
                "从慢到快，逐渐加大幅度",
                "覆盖即将训练的关节与肌群",
                "感到微微发热即可，不必力竭",
            ),
            target="全身动员",
        ),
        "拉伸": ActionGuide(
            name="拉伸",
            image_asset=f"{_DIR}/stretch.png",
            summary="拉伸帮助放松紧张肌群、改善柔韧。以舒适拉伸感为准，避免弹振式猛拉。",
            cues=(
                "每个姿势保持约 15 到 30 秒",
                "呼吸缓慢均匀",
                "不要到剧痛区间",
            ),
            target="柔韧与恢复",
        ),
        "弓步蹲": ActionGuide(
            name="弓步蹲",
            image_asset=f"{_DIR}/lunge.png",
            summary="弓步蹲强化单侧腿力量与平衡。前腿屈膝下沉，后腿膝盖接近地面，再蹬回。",
            cues=(
                "前膝大致对准脚尖方向",
                "躯干保持直立",
                "下沉时后膝轻触垫面即可",
                "左右腿轮流完成",
            ),
            target="股四头肌、臀大肌、腘绳肌",
        ),
        "臀桥": ActionGuide(
            name="臀桥",
            image_asset=f"{_DIR}/lower_body.png",
            summary="臀桥仰卧屈膝，靠臀部发力把髋部顶起，强化臀肌并兼顾下背稳定。",
            cues=(
                "肩背贴地，下巴微收",
                "顶髋时臀部主动收缩",
                "不要用腰过度代偿拱起",
                "下落时有控制地回放",
            ),
            target="臀大肌、腘绳肌",
        ),
        "提踵": ActionGuide(
            name="提踵",
            image_asset=f"{_DIR}/calf_raise.png",
            summary="提踵站立抬起脚跟，锻炼小腿三头肌，有助于踝关节力量与跑步稳定。",
            cues=(
                "脚掌支撑，缓慢抬起脚跟",
                "顶点稍停再放下",
                "膝盖保持微直但不要锁死",
            ),
            target="腓肠肌、比目鱼肌",
        ),
        "抬臂": ActionGuide(
            name="抬臂",
            image_asset=f"{_DIR}/upper.png",
            summary="抬臂动作活动肩关节与上背，常用于热身或肩带控制练习。",
            cues=(
                "肩胛下沉，避免耸肩",
                "手臂抬起时肋骨不要过分外翻",
                "动作平滑，左右对称",
            ),
            target="肩带、上背",
        ),
        "平板支撑": ActionGuide(
            name="平板支撑",
            image_asset=f"{_DIR}/plank.png",
            summary="平板支撑是核心等长训练。身体成直线支撑，重点在稳定而非憋气硬撑。",
            cues=(
                "肘或手在肩正下方",
                "臀部不要塌也不要过高翘起",
                "收紧腹部与臀部",
                "保持正常呼吸",
            ),
            target="腹横肌、竖脊肌、肩稳定",
        ),
        "卷腹": ActionGuide(
            name="卷腹",
            image_asset=f"{_DIR}/core.png",
            summary="卷腹训练腹直肌，上背离地、下背贴地，用腹部发力而非甩头。",
            cues=(
                "下巴微收，不要用力扯脖子",
                "呼气时卷起，吸气回落",
                "动作幅度可控即可",
            ),
            target="腹直肌",
        ),
        "死虫式": ActionGuide(
            name="死虫式",
            image_asset=f"{_DIR}/dead_bug.png",
            summary="死虫式仰卧对侧手脚伸展，训练抗伸展核心控制，适合保护下背。",
            cues=(
                "腰部轻轻压住地面",
                "对侧手脚同时缓慢伸展",
                "动作过程中腰不要拱起",
            ),
            target="深层核心",
        ),
        "侧桥": ActionGuide(
            name="侧桥",
            image_asset=f"{_DIR}/core.png",
            summary="侧桥侧卧支撑，强化腹斜肌与髋外侧稳定，改善侧向核心力量。",
            cues=(
                "肘在肩正下方",
                "髋部上推成一条斜线",
                "不要塌肩或扭腰",
            ),
            target="腹斜肌、臀中肌",
        ),
        "俯身划船": ActionGuide(
            name="俯身划船",
            image_asset=f"{_DIR}/row.png",
            summary="俯身划船模拟拉类动作，强化上背与肱二头肌，改善含胸圆肩趋势。",
            cues=(
                "髋铰链俯身，腰背保持中立",
                "肘部贴近身体向后拉",
                "肩胛主动后收下沉",
                "不要靠甩腰借力",
            ),
            target="背阔肌、菱形肌、肱二头肌",
        ),
        "手臂环绕": ActionGuide(
            name="手臂环绕",
            image_asset=f"{_DIR}/arm_circles.png",
            summary="手臂环绕用于激活肩关节活动度，适合训练前肩带热身。",
            cues=(
                "幅度由小到大",
                "肩部放松下沉",
                "正反方向各做若干次",
            ),
            target="肩关节活动度",
        ),
        "肩部拉伸": ActionGuide(
            name="肩部拉伸",
            image_asset=f"{_DIR}/shoulder_stretch.png",
            summary="肩部拉伸改善肩关节柔韧与肩胛活动，训练后放松效果较好。",
            cues=(
                "横臂拉肩或扶墙开胸均可",
                "保持呼吸，停留片刻",
                "两侧交替进行",
            ),
            target="肩带柔韧",
        ),
        "髋部打开": ActionGuide(
            name="髋部打开",
            image_asset=f"{_DIR}/hip_opener.png",
            summary="髋部打开动作改善髋屈伸与旋转活动度，为深蹲、弓步等做准备。",
            cues=(
                "动作可控，不要弹振",
                "骨盆尽量保持水平",
                "感到牵拉即可",
            ),
            target="髋屈肌、臀肌活动度",
        ),
        "腿后侧拉伸": ActionGuide(
            name="腿后侧拉伸",
            image_asset=f"{_DIR}/hamstring_stretch.png",
            summary="针对腘绳肌与小腿后侧的拉伸，有助于缓解久坐拉紧感。",
            cues=(
                "膝盖可微屈，以舒适为准",
                "躯干前倾来自髋部而非弓背",
                "双侧都要拉伸",
            ),
            target="腘绳肌、小腿",
        ),
        "腰背放松": ActionGuide(
            name="腰背放松",
            image_asset=f"{_DIR}/cat_cow.png",
            summary="腰背放松用轻柔屈曲或扭转释放下背压力，避免突然大幅度扭转。",
            cues=(
                "动作缓慢有控制",
                "疼痛加剧时立刻停下",
                "配合呼气加深放松",
            ),
            target="竖脊肌、腰方肌",
        ),
        "腿部拉伸": ActionGuide(
            name="腿部拉伸",
            image_asset=f"{_DIR}/quad_stretch.png",
            summary="综合拉伸大腿前侧、后侧与髋部，作为下肢课后恢复环节。",
            cues=(
                "覆盖股四头、腘绳与髋屈",
                "每个部位停留片刻",
                "保持平稳呼吸",
            ),
            target="下肢柔韧",
        ),
    }

    _ALIASES = {"弓步": "弓步蹲"}

    @classmethod
    def known_names(cls) -> list[str]:
        return sorted(cls._BY_NAME.keys())

    @classmethod
    def for_name(cls, name: str) -> ActionGuide:
        key = (name or "").strip()
        if not key:
            return cls.fallback
        mapped = cls._ALIASES.get(key, key)
        found = cls._BY_NAME.get(mapped)
        if found:
            return found
        return ActionGuide(
            name=key,
            image_asset=cls.fallback.image_asset,
            summary=f"{key}是本课程中的训练动作。按提示完成幅度，优先保证姿势稳定。",
            cues=cls.fallback.cues,
            target=cls.fallback.target,
        )
