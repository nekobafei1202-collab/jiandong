# 健动 AI（Android）

AI 健身辅助 App，运行于 Android 手机。电脑用于编辑代码、运行测试和构建 APK。

> 让每一次运动，都更适合你

## 下载与安装

普通用户只需到 [Releases](https://github.com/nekobafei1202-collab/jiandong_ai_python/releases) 下载最新的 `.apk`，在 Android 手机上打开文件并按系统提示安装；无需下载源码、Python 或模型文件。首次手动安装时，系统可能要求允许文件管理器安装应用。

当前通用 APK 包含 `arm64-v8a`、`armeabi-v7a`、`x86_64` 三种架构，要求 Android 7.0（API 24）及以上。已在 `arm64-v8a` 真机验证安装和启动；其余架构已打包，尚未分别做真机验证。APK 内含离线语音和姿态模型，因此文件较大。

应用可查看课程、安排训练计划，用手机相机识别动作并计数、评分和提示，训练结束后保存记录；语音辅助可在应用设置中开启。

## 技术栈

| 层 | 选型 |
| --- | --- |
| UI / 打包 | Flet（Flutter 渲染） |
| 姿态（Android） | MediaPipe Tasks + CameraX 原生桥 → Python 管线 |
| 相机 | CameraX（真机） |
| 数据 | 本地 `jiandong_data.json` |

## 源码开发与打包

以下步骤供开发者使用。当前构建脚本依赖 Windows 的 `D:` 盘下已配置的 Flutter、Android SDK 和 Java 环境。

```bash
cd D:\appdemo
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m jiandong_ai.scripts.build_android
```

打包脚本会刷新 Flet 模板并注入 Android 原生桥。详见 [`android_bridge/README.md`](android_bridge/README.md)。
默认 APK 包含 arm64-v8a、armeabi-v7a、x86_64 三种 Android 架构。

## 目录

```
jiandong_ai/   # 应用与 AI 管线
assets/        # 与原版共用的图片 / demo 序列
models/        # 手机端模型
tests/         # 黄金用例
android_bridge/# CameraX + MediaPipe 原生桥
```

## Mock 账号

- 邮箱：`test@example.com`
- 密码：`123456`
