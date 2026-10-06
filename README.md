# 健动 AI（Python / Flet）

AI 健身辅助 App 的 Python 重写版。原版 Flutter 工程保留在 `D:\app`，本仓库独立于 `D:\appdemo`。

> 让每一次运动，都更适合你

## 技术栈

| 层 | 选型 |
| --- | --- |
| UI / 打包 | Flet（Flutter 渲染） |
| 姿态（Windows 开发） | MediaPipe Pose → COCO-17 |
| 姿态（Android） | MediaPipe Tasks 原生桥 → Python 管线 |
| 相机 | OpenCV / Flet Camera |
| 数据 | 本地 `jiandong_data.json` |

## 快速开始（Windows）

```bash
cd D:\appdemo
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
# 下载姿态模型（约 5.5MB）
powershell -Command "Invoke-WebRequest -Uri https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task -OutFile models\pose_landmarker_lite.task"
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

见 [`android_bridge/README.md`](android_bridge/README.md)。需要先完成 Windows 全链路验收。

```bash
flet build apk
```

## 目录

```
jiandong_ai/   # 应用与 AI 管线
assets/        # 与原版共用的图片 / demo 序列
tests/         # 黄金用例
android_bridge/# Android Pose Landmarker 桥
```

## Mock 账号

- 邮箱：`test@example.com`
- 密码：`123456`
