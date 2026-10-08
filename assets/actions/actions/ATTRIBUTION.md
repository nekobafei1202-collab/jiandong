# Action pose images attribution

Bundled under `assets/actions/` for offline course intro screens.

**Source (all 12 files):** [bryllim/workout-guide](https://github.com/bryllim/workout-guide)
— 302 open exercise illustrations, MIT-licensed code with visual assets under
**CC BY-SA 4.0** (see `LICENSE-ASSETS` upstream). Frames were taken from
`packages/workout-guide/assets/<slug>/frame-N.png` (2026-09-24).

Upstream in turn credits the Everkinetic exercise illustration set where
applicable; see `ATTRIBUTION.md` in that repository.

**Local modifications (2026-09-24, `tmp_repdb/wg_fetch.py` + `wg_apply.py`):**

1. Recolored from white-on-transparent to dark ink (`#0F1115`, matches
   `ShellColors.textPrimary`) on transparent background, so the figures sit on
   the light shell's white cards.
2. Added soft red muscle-highlight overlays at prime-mover positions.
   As derivative works of CC BY-SA sources, the bundled files remain CC BY-SA 4.0.

| File | Action | Upstream slug | Frame |
|------|--------|---------------|-------|
| `squat.png` | 深蹲 | `bodyweight-squat` | 2 |
| `pushup.png` | 俯卧撑 | `push-up` | 2 |
| `cardio.png` | 开合跳 | `jumping-jack` | 2 |
| `plank.png` | 平板支撑 | `plank` | 2 |
| `lunge.png` | 弓步蹲 | `forward-lunge` | 2 |
| `upper.png` | 抬臂(侧平举) | `lateral-raise` | 2 |
| `lower_body.png` | 臀桥 | `glute-bridge` | 2 |
| `core.png` | 侧桥 | `side-plank` | 2 |
| `strength.png` | 通用力量(卧推) | `bench-press` | 2 |
| `warmup.png` | 热身(开合跳) | `jumping-jack` | 1 |
| `stretch.png` | 拉伸(蝴蝶式) | `butterfly-stretch` | 1 |
| `mobility.png` | 髋部拉伸 | `kneeling-hip-flexor-stretch` | 2 |
| `high_knees.png` | 高抬腿 | `high-knees` | 2 |
| `calf_raise.png` | 提踵 | `standing-calf-raise` | 2 |
| `dead_bug.png` | 死虫式 | `dead-bug` | 2 |
| `row.png` | 俯身划船 | `barbell-row` | 2 |
| `arm_circles.png` | 手臂环绕 | `arm-circles` | 2 |
| `shoulder_stretch.png` | 肩部拉伸 | `cross-body-shoulder-stretch` | 1 |
| `hip_opener.png` | 髋部打开(摆腿) | `leg-swings-stretch` | 1 |
| `hamstring_stretch.png` | 腿后侧拉伸 | `hamstring-stretch` | 2 |
| `cat_cow.png` | 腰背放松(猫牛式) | `cat-cow-stretch` | 2 |
| `quad_stretch.png` | 腿部拉伸(股四头) | `standing-quad-stretch` | 2 |

颈部放松 / 肩颈拉伸 / 呼吸调整 上游无合适插画，暂共用 `stretch.png`。

The upstream set provides 3 frames per exercise (start / mid / end poses);
only one frame per action is bundled here. More frames can be pulled with the
same scripts if animated demos are wanted later.
