# 健动 AI 项目约定

## adb 真机操作约定（与用户的长期约定）

用 adb 对用户手机做任何盲操作（tap/swipe/input）时：

1. 操作前先截图确认当前界面，避免误触系统界面（控制中心/桌面）
2. **绝不改动用户的旋转锁定设置**；验证结束后执行 `settings put system accelerometer_rotation 0` 恢复锁定
3. 其他系统设置项（亮度、音量、勿扰等）一律不碰

## 打包清理约定（与用户的长期约定）

每次帮用户完成 APK 打包并安装到手机、验证没问题之后，必须主动执行清理：

1. 将 APK 成品备份到 `_backup/`（如用户没要求保留可跳过）
2. 删除 `build/` 目录（Flutter/Gradle 编译缓存，下次打包会自动重建）
3. 向用户确认清理完成和释放的空间

**绝不能误删**：`.venv/`、`models/`、`jiandong_ai/`、`android_bridge/`、`tests/`、`assets/` 等源码和环境目录。

## 调试产物

临时调试截图、日志、拆包目录（如 `_phone_run/`、`_apk_inspect/`、`_run_*.png`）属于一次性产物，清理时可删除；打包 APK 时不得包含这些文件。诊断视频 `_diag_videos/` 用后即删。
