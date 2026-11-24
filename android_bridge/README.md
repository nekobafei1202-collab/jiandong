# Android Pose Bridge (MediaPipe Tasks)

手机姿态识别使用 CameraX 与 MediaPipe Tasks `pose_landmarker_full.task`，由原生桥输出 COCO-17 关键点。

CameraX writes:

- `files/jiandong_pose/latest.jpg`
- `files/jiandong_pose/latest.json` (COCO-17)
- `files/jiandong_pose/cmd.txt` — `start_front` / `start_back` / `stop` / `pause`

Python [`AndroidBridgePoseSession`](../jiandong_ai/ai/session/android_bridge_session.py) polls these files.

## Build

```bash
# 1) models
python -m jiandong_ai.scripts.download_kws_model   # 无障碍语音口令模型（sherpa-onnx KWS）
python -m jiandong_ai.scripts.download_tts_model   # 离线 TTS 兜底模型（vits-zh-aishell3 int8）
python -m jiandong_ai.scripts.download_asr_model   # “小健”自由对话离线识别（SenseVoice + VAD）

# 2) build on Windows with D: caches and native injection after template refresh
python -m jiandong_ai.scripts.build_android
```

## Permissions

`CAMERA` via `flet build --permissions camera`; `RECORD_AUDIO` / `VIBRATE` are
injected into the manifest by `prepare_android_bridge.py` (used only by the
无障碍语音模式).

## 无障碍语音模式（视障）

- `VoiceCommandBridge.kt` — sherpa-onnx KWS 全程监听（模型在 `assets/kws/`，
  由 `download_kws_model.py` 生成到 `models/kws/`）。仅在共享目录存在
  `voice_enabled.flag` 时启动麦克风；`PoseTrainingActivity` 存活期间写
  `training_active.flag`，此时命中口令写 `training_control.json`；原生训练页执行
  开始、暂停、恢复、结束后，再通过 `event.json` 同步 Python。其他页面写
  `voice_cmd.json`（登录/选课口令）。录音启用设备回声消除，训练播报中仍识别暂停和结束。
- 语音辅助已开启时直接进入相机页，不插入触屏引导。预览阶段运行入镜检测，
  确认位置后等待用户口令才开始计时；热身/拉伸说“继续训练”进入下一步。
  “再说一遍”重听，“下一个动作/上一个动作”切换动作；暂停时休息倒计时也暂停。
- `training_speech.json` 独立承载位置、状态、动作说明和结束总结，避免 HUD 刷新
  覆盖播报；启动时清理旧进程会话标记，避免残留助手占用麦克风。
- `TtsAnnouncer.kt` — `voice_session_active.flag` 存在才轮询 `tts.json`
  （登录引导/选课对话），`training_active.flag` 存在才轮询 `hud.json`
  （计数/纠错/休息/总结）；通道激活时以现有内容为基线，且不播早于进程启动的
  残留文件。引擎三级降级：系统 TextToSpeech（中文）→ sherpa-onnx
  OfflineTts（`assets/tts/` 的 vits-zh-aishell3 int8，供 MIUI 等无系统 TTS
  引擎的 ROM 使用，AudioTrack 播放）→ 震动。
- Python 侧开关：`android_bridge_session.write_voice_flag(enabled)` 原子写/删
  flag 文件。

## “小健”AI 语音助手

- 在“我的 → 无障碍训练”中开启“语音辅助模式”和“AI 语音助手”，并在同一
  面板填写 DeepSeek API Key。Key 仅写入应用本地
  `~/.jiandong_ai/ai_config.json`，不会打入 APK 或普通设置文件。
- 说“小健小健”后，KWS 释放麦克风，`AsrBridge.kt` 懒加载
  `assets/asr/` 下的 SenseVoice 与 Silero VAD；识别文本由
  `AssistantSession` 发给 DeepSeek。训练开始后自由对话退出，训练控制继续
  使用固定 KWS 口令。
- 真机验收顺序：唤醒 → “我想练腿” → 健身问答 → “退出助手” → 再次用固定
  口令；另测 60 秒无输入退出、请求与播报期间暂停计时，以及断网降级。


## Serena 离线提示音

固定提示优先播放 Qwen3-TTS `0.6B-CustomVoice` 的 Serena 预生成录音；
手机不加载 Qwen 模型，不请求千问云 API。未命中录音的动态回答继续使用
系统已安装的离线中文音色，或原有 sherpa-onnx VITS 兜底。

生成全部文件（有 NVIDIA GPU 的 Windows 电脑）：

```powershell
powershell -ExecutionPolicy Bypass -File jiandong_ai/scripts/setup_serena.ps1
```

加 `-SampleOnly` 只生成前三段试听，不能用于完整 APK 打包。
健康的生成环境会直接复用；仅需修复安装时使用 `-Repair`。
生成器使用较小的解码分段控制显存峰值，已完成的录音会自动跳过。
环境在 `D:/appdemo/.tts-venv/`，所有模型、下载缓存、临时文件在
`D:/appdemo/.speech-cache/`。二者均被明确排除出 APK。
录音和文本索引位于 `assets/voice/serena/`；原生桥准备脚本验证所有固定提示、
24 kHz 单声道 PCM16 WAV 和文件路径，缺失/损坏/未生成完整时拒绝打包。
文本索引记录模型来源与音色；模型采用 Apache-2.0：
https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice

`SerenaPrompts.kt` 读取录音，复用 `TtsAnnouncer` 的播放队列和麦克风静音门控。
新的打断播报会丢弃旧队列并停止旧录音；关闭语音模式同样停止播放。

`build_android` 将排除通配符展开成具体路径，并再次检查打包暂存区，避免调试
截图、旧日志、桌面状态、测试目录和生成缓存进入 APK。构建依赖已完整准备好、
仅调整原生资源或排除规则时可加 `--native-only`；它不会刷新 Python 应用代码。
