"""Inject native CameraX + MediaPipe Pose bridge into Flet's Android project."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLUTTER = ROOT / "build" / "flutter"
ANDROID = FLUTTER / "android"
KOTLIN_SRC = ROOT / "android_bridge" / "kotlin"
MODELS = ROOT / "models"
PKG_REL = Path("com") / "flet" / "jiandong_ai"


def _copy_models(assets: Path) -> None:
    dest = assets / "models"
    dest.mkdir(parents=True, exist_ok=True)
    # Remove old mobile RTMPose assets: Android now uses MediaPipe Full.
    for stale in dest.glob("*.onnx"):
        stale.unlink(missing_ok=True)
    for name in ("pose_landmarker_full.task",):
        src = MODELS / name
        if src.exists():
            shutil.copy2(src, dest / name)
            print(f"asset {name}")
        else:
            raise FileNotFoundError(
                f"Missing {src}. Download MediaPipe pose_landmarker_full.task "
                "(SHA256 4EAA5EB7A98365221087693FCC286334CF0858E2EB6E15B506AA4A7ECDCEC4AD)."
            )


def _copy_demo_frames(assets: Path) -> None:
    """White-mannequin PNG frame sets for PoseTrainingActivity's demo pane."""
    src_root = ROOT / "assets" / "demo"
    dest_root = assets / "demo"
    if dest_root.exists():
        shutil.rmtree(dest_root)
    copied = 0
    for src in sorted(src_root.iterdir()):
        if not src.is_dir() or not src.name.endswith("_white_mannequin"):
            continue  # skip the duplicated nested assets/demo/demo copy
        dest = dest_root / src.name
        dest.mkdir(parents=True, exist_ok=True)
        for frame in sorted(src.glob("*.png")):
            shutil.copy2(frame, dest / frame.name)
            copied += 1
        print(f"demo frames {src.name}")
    if not copied:
        raise FileNotFoundError(f"No white-mannequin demo frames under {src_root}")


def _copy_kotlin(kotlin_root: Path) -> None:
    dest = kotlin_root / PKG_REL
    dest.mkdir(parents=True, exist_ok=True)
    # Remove stale copies under java/
    java_stale = ANDROID / "app" / "src" / "main" / "java" / PKG_REL
    if java_stale.exists():
        shutil.rmtree(java_stale, ignore_errors=True)
    # RTMPose ORT is desktop-only now; ensure no stale mobile class remains.
    (dest / "RtmPoseOrt.kt").unlink(missing_ok=True)
    for path in KOTLIN_SRC.glob("*.kt"):
        if path.name == "RtmPoseOrt.kt":
            continue
        shutil.copy2(path, dest / path.name)
        print(f"kotlin {path.name} -> {dest}")


_ORT_PROGUARD = """
# onnxruntime-android JNI looks up TensorInfo/OnnxTensor by reflection;
# R8 stripping them causes: JNI DETECTED ERROR mid == null in OrtSession.run.
-keep class ai.onnxruntime.** { *; }
-keepclassmembers class ai.onnxruntime.** { *; }
"""


def _ensure_proguard(app: Path) -> None:
    rules = app / "proguard-rules.pro"
    if rules.exists():
        text = rules.read_text(encoding="utf-8")
    else:
        text = ""
    if "ai.onnxruntime" not in text:
        text = text.rstrip() + "\n" + _ORT_PROGUARD
        rules.write_text(text + "\n", encoding="utf-8")
        print(f"proguard keep rules: {rules}")
    else:
        print("proguard ORT rules already present")


def _ensure_gradle_deps(app_gradle: Path) -> None:
    original = app_gradle.read_text(encoding="utf-8")
    text = original
    text = re.sub(
        r'^\s*implementation\("com\.microsoft\.onnxruntime:onnxruntime-android:[^"]+"\)\s*$',
        "",
        text,
        flags=re.MULTILINE,
    )
    deps = [
        'implementation("androidx.camera:camera-camera2:1.3.4")',
        'implementation("androidx.camera:camera-lifecycle:1.3.4")',
        'implementation("androidx.camera:camera-view:1.3.4")',
        'implementation("com.google.mediapipe:tasks-vision:0.10.14")',
    ]
    if all(dep in text for dep in deps):
        if text != original:
            app_gradle.write_text(text, encoding="utf-8")
        print("gradle deps already present")
        return
    block = "dependencies {\n" + "".join(f"    {d}\n" for d in deps) + "}"
    if re.search(r"dependencies\s*\{\s*\}", text):
        text = re.sub(r"dependencies\s*\{\s*\}", block, text, count=1)
    elif "dependencies {" in text:
        for dep in deps:
            if dep not in text:
                text = text.replace("dependencies {", "dependencies {\n    " + dep, 1)
    else:
        text += "\n\n" + block + "\n"
    app_gradle.write_text(text, encoding="utf-8")
    print(f"gradle deps updated: {app_gradle.name}")


def _ensure_release_proguard(app_gradle: Path) -> None:
    """Point release builds at proguard-rules.pro (Flutter may enable R8)."""
    text = app_gradle.read_text(encoding="utf-8")
    if "proguard-rules.pro" in text:
        print("gradle proguardFiles already set")
        return
    needle = "buildTypes {\n        release {"
    if needle not in text:
        print("warn: could not locate release buildType for proguardFiles")
        return
    inject = (
        "buildTypes {\n        release {\n"
        "            // ORT JNI needs TensorInfo ctors; disable R8 strip + keep rules.\n"
        "            isMinifyEnabled = false\n"
        "            isShrinkResources = false\n"
        "            proguardFiles(\n"
        '                getDefaultProguardFile("proguard-android-optimize.txt"),\n'
        '                "proguard-rules.pro",\n'
        "            )"
    )
    text = text.replace(needle, inject, 1)
    app_gradle.write_text(text, encoding="utf-8")
    print("gradle release proguardFiles set")


def _patch_main_activity(main: Path) -> None:
    text = main.read_text(encoding="utf-8")
    if "ShellBackForwarder" in text and "OnBackPressedCallback" in text and "isTaskRoot" in text:
        print(f"MainActivity already patched: {main}")
        return
    # Flet 1.0 uses FlutterFragmentActivity; rewrite whole file for a reliable hook.
    main.write_text(
        """package com.flet.jiandong_ai

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.OnBackPressedCallback
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterFragmentActivity

class MainActivity : FlutterFragmentActivity() {
    private var poseBridge: PoseCameraBridge? = null
    private val poseHandler = Handler(Looper.getMainLooper())
    private val posePoll = object : Runnable {
        override fun run() {
            poseBridge?.pollCommands()
            poseHandler.postDelayed(this, 50)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Duplicate-launch guard: if the system still spawns a second launcher
        // instance, kill it immediately and return to the original task
        // instead of hanging on the Flet loading page.
        if (!isTaskRoot
            && intent?.action == Intent.ACTION_MAIN
            && intent?.hasCategory(Intent.CATEGORY_LAUNCHER) == true
        ) {
            finish()
            return
        }
        poseBridge = PoseCameraBridge(this)
        poseHandler.post(posePoll)
        ensureCameraPermission()
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (ShellBackForwarder.requestConsume(this@MainActivity)) {
                    return
                }
                isEnabled = false
                onBackPressedDispatcher.onBackPressed()
                isEnabled = true
            }
        })
    }

    private fun ensureCameraPermission() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.CAMERA),
                REQ_CAMERA,
            )
        }
    }

    override fun onDestroy() {
        poseHandler.removeCallbacks(posePoll)
        poseBridge?.stop()
        super.onDestroy()
    }

    companion object {
        private const val REQ_CAMERA = 0xC01
    }
}
""",
        encoding="utf-8",
    )
    print(f"patched {main}")


def _patch_manifest(manifest: Path) -> None:
    import re

    text = manifest.read_text(encoding="utf-8")
    # One task only: desktop icon resumes Main instead of spawning a second splash.
    text2, n_main = re.subn(
        r'(android:name="\.MainActivity"[^>]*android:launchMode=")[^"]+(")',
        r'\1singleTask\2',
        text,
        count=1,
    )
    if n_main:
        text = text2
        print("manifest MainActivity launchMode=singleTask")

    # Empty taskAffinity breaks launcher-icon task matching (esp. on Chinese
    # ROMs): a second task/instance gets spawned and the duplicate Flet
    # session hangs on the loading page. Default affinity (package name)
    # makes the launcher icon reliably resume the single existing task.
    if 'android:taskAffinity=""' in text:
        text = text.replace('\n            android:taskAffinity=""', "")
        print("manifest taskAffinity removed (use package-name default)")

    desired = """
        <activity
            android:name=".PoseTrainingActivity"
            android:exported="false"
            android:screenOrientation="portrait"
            android:theme="@style/NormalTheme"
            android:parentActivityName=".MainActivity"
            android:configChanges="orientation|screenSize|keyboardHidden"
            android:hardwareAccelerated="true" />
    """
    if "PoseTrainingActivity" in text:
        updated, n = re.subn(
            r'<activity\s+android:name="\.PoseTrainingActivity"[^/]*/>',
            desired.strip(),
            text,
            count=1,
            flags=re.DOTALL,
        )
        if n:
            manifest.write_text(updated, encoding="utf-8")
            print("manifest native training activity updated")
        else:
            manifest.write_text(text, encoding="utf-8")
            print("manifest native training activity already present")
        return
    marker = "</application>"
    if marker not in text:
        raise RuntimeError(f"Could not patch activity into {manifest}")
    manifest.write_text(text.replace(marker, desired + marker, 1), encoding="utf-8")
    print("manifest native training activity added")


def main() -> None:
    if not ANDROID.exists():
        raise SystemExit(
            f"Missing {ANDROID}. Run `flet build apk` once to generate the Flutter shell, "
            "then re-run this script and `flutter build apk`."
        )
    app = ANDROID / "app"
    kotlin_root = app / "src" / "main" / "kotlin"
    assets = app / "src" / "main" / "assets"
    _copy_models(assets)
    _copy_demo_frames(assets)
    _copy_kotlin(kotlin_root)
    gradle = app / "build.gradle.kts"
    if not gradle.exists():
        gradle = app / "build.gradle"
    if gradle.exists():
        _ensure_gradle_deps(gradle)
        _ensure_release_proguard(gradle)
    _ensure_proguard(app)
    manifest = app / "src" / "main" / "AndroidManifest.xml"
    if manifest.exists():
        _patch_manifest(manifest)
    mains = list((app / "src" / "main").rglob("MainActivity.kt"))
    # Prefer package matching applicationId
    preferred = [m for m in mains if "com\\flet\\jiandong_ai" in str(m) or "com/flet/jiandong_ai" in str(m)]
    target = preferred[0] if preferred else (mains[0] if mains else None)
    if target is None:
        print("MainActivity not found — skip lifecycle hook")
    else:
        _patch_main_activity(target)
    print("Android bridge prepared.")


if __name__ == "__main__":
    main()
