# Android Pose Bridge

`pip install mediapipe` 无法直接打进 Android APK。真机姿态检测走本目录桥接：

1. Flet/Flutter 侧用 **MediaPipe Pose Landmarker**（BlazePose）推理
2. 将 33 点映射为 **COCO-17**（与原版 `real_pose_detector.dart` 一致）
3. 通过 method channel / Flet 扩展把关键点 JSON 交给 Python `TrainingPipeline.process_pose`

## COCO-17 映射

与原版 ML Kit 映射相同（按名称 1:1）：

nose, leftEye, rightEye, leftEar, rightEar,
leftShoulder, rightShoulder, leftElbow, rightElbow, leftWrist, rightWrist,
leftHip, rightHip, leftKnee, rightKnee, leftAnkle, rightAnkle

## 权限

`AndroidManifest.xml` 需声明：

```xml
<uses-permission android:name="android.permission.CAMERA" />
```

## 打包

在仓库根目录：

```bash
flet build apk
```

开发阶段请先用 Windows + `mediapipe` Python 验收识别逻辑；本桥仅在真机打包时启用。
