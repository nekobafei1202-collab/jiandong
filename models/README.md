# Android models

## Speech models

Speech model weights are downloaded locally and excluded from Git. Before
building the Android app with voice support, run these commands from the project root:

```powershell
.venv/Scripts/python.exe -m jiandong_ai.scripts.download_asr_model
.venv/Scripts/python.exe -m jiandong_ai.scripts.download_kws_model
.venv/Scripts/python.exe -m jiandong_ai.scripts.download_tts_model
```

The scripts populate `models/asr/`, `models/kws/`, and `models/tts/`.

## 姿态模型

Android 原生桥使用 `pose_landmarker_full.task`。`prepare_android_bridge.py` 会将它复制到 APK 的原生资源目录。仓库中旧的 RTMPose ONNX 和 MediaPipe Lite 文件不再用于运行，也已从 APK 打包内容中排除。
