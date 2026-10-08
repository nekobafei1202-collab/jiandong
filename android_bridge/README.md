# Android Pose Bridge (Good-GYM RTMPose ONNX)

True-device pose uses the **same lightweight ONNX** as desktop ([Good-GYM](https://github.com/yo-WASSUP/Good-GYM), MIT):

- `yolox_nano_…onnx` (bundled; person-det optional on device)
- `rtmpose-t_…onnx` via **onnxruntime-android**

CameraX writes:

- `files/jiandong_pose/latest.jpg`
- `files/jiandong_pose/latest.json` (COCO-17)
- `files/jiandong_pose/cmd.txt` — `start_front` / `start_back` / `stop` / `pause`

Python [`AndroidBridgePoseSession`](../jiandong_ai/ai/session/android_bridge_session.py) polls these files.

## Build

```bash
# 1) models
python -m jiandong_ai.scripts.download_rtmpose_models

# 2) generate / refresh Flet Flutter shell (first time)
flet build apk --permissions camera --skip-flutter-doctor --yes

# 3) inject Kotlin + assets + gradle deps
python -m jiandong_ai.scripts.prepare_android_bridge

# 4) rebuild APK (re-run prepare after a clean flutter regen)
flet build apk --permissions camera --skip-flutter-doctor --yes
```

## Permissions

`CAMERA` via `flet build --permissions camera`.
