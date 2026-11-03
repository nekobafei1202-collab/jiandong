# Pose models

## Speech models

Speech model weights are downloaded locally and excluded from Git. Before
building the Android app with voice support, run these commands from the project root:

```powershell
.venv/Scripts/python.exe -m jiandong_ai.scripts.download_asr_model
.venv/Scripts/python.exe -m jiandong_ai.scripts.download_kws_model
.venv/Scripts/python.exe -m jiandong_ai.scripts.download_tts_model
```

The scripts populate `models/asr/`, `models/kws/`, and `models/tts/`.

## RTMPose (default — desktop + Android bridge)

Lightweight ONNX pair borrowed from [Good-GYM](https://github.com/yo-WASSUP/Good-GYM) (MIT):

| File | Role |
|------|------|
| `yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx` | Person detection |
| `rtmpose-t_simcc-body7_pt-body7_420e-256x192-026a1439_20230504.onnx` | COCO-17 pose |

Download:

```bash
python -m jiandong_ai.scripts.download_rtmpose_models
```

Desktop inference: `rtmlib` + `onnxruntime` (CPU).  
Android inference: same ONNX via `onnxruntime-android` (see `android_bridge/`).

## MediaPipe (optional desktop fallback)

`pose_landmarker_lite.task` — only used if RTMPose init fails.

```bash
python -m jiandong_ai.scripts.download_model
```
