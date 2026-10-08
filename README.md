# 健动 AI（Python / Flet）

AI 健身辅助 App 的 Python 重写版。原版 Flutter 工程保留在 `D:\app`，本仓库独立于 `D:\appdemo`。

> 让每一次运动，都更适合你

## 技术栈

| 层 | 选型 |
| --- | --- |
| UI / 打包 | Flet（Flutter 渲染） |
| 姿态（Windows） | Good-GYM RTMPose ONNX（rtmlib）→ COCO-17；MediaPipe 可选回退 |
| 姿态（Android） | 同 ONNX + onnxruntime-android + CameraX 文件桥 → Python 管线 |
| 相机 | OpenCV（桌面）/ CameraX（真机） |
| 数据 | 本地 `jiandong_data.json` |

## 快速开始（Windows）

```bash
cd D:\appdemo
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m jiandong_ai.scripts.download_rtmpose_models
python -m jiandong_ai.main
```

跳过启动页直达主壳：

```bash
python -m jiandong_ai.main --preview
```

跑黄金测试（识别逻辑与 Dart 阈值对齐）：

```bash
pytest -q
```

## Android 打包

见 [`android_bridge/README.md`](android_bridge/README.md)。RTMPose ONNX 来自 [Good-GYM](https://github.com/yo-WASSUP/Good-GYM)（MIT）。

```bash
python -m jiandong_ai.scripts.download_rtmpose_models
flet build apk --permissions camera --skip-flutter-doctor --yes
python -m jiandong_ai.scripts.prepare_android_bridge
flet build apk --permissions camera --skip-flutter-doctor --yes
```

## 目录

```
jiandong_ai/   # 应用与 AI 管线
assets/        # 与原版共用的图片 / demo 序列
models/        # RTMPose / YOLOX ONNX
tests/         # 黄金用例
android_bridge/# CameraX + ORT 桥
```

## Mock 账号

- 邮箱：`test@example.com`
- 密码：`123456`
