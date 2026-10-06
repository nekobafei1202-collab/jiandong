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

在仓库根目录（需本机安装 Flutter SDK，Flet 会调用）：

```bash
# 1. 确保 Python 依赖与模型就绪
pip install -r requirements.txt
python -m jiandong_ai.scripts.download_model

# 2. 构建 APK（首次较慢）
flet build apk
```

产物一般在 `build/apk/`。安装到真机后授予相机权限，训练页走原生 Pose Landmarker → `pose_channel.pose_from_bridge_payload` → `TrainingPipeline.process_pose`。

开发阶段请先用 Windows + 摄像头验收识别逻辑；本桥在真机打包时启用。
