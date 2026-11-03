"""Inject native CameraX + MediaPipe Pose bridge into Flet's Android project."""

from __future__ import annotations

import re
import shutil
import socket
from pathlib import Path

# Large AAR/model downloads: never let a blocked endpoint hang forever.
socket.setdefaulttimeout(120)

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


def _copy_kws_models(assets: Path) -> None:
    """sherpa-onnx KWS model + keywords.txt for VoiceCommandBridge."""
    src = MODELS / "kws"
    dest = assets / "kws"
    dest.mkdir(parents=True, exist_ok=True)
    names = ("encoder.onnx", "decoder.onnx", "joiner.onnx", "tokens.txt", "keywords.txt")
    missing = [name for name in names if not (src / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing {missing} under {src}. Run "
            "`python -m jiandong_ai.scripts.download_kws_model` first."
        )
    for name in names:
        shutil.copy2(src / name, dest / name)
    print(f"asset kws/ ({len(names)} files)")


def _copy_tts_models(assets: Path) -> None:
    """sherpa-onnx VITS TTS fallback model for TtsAnnouncer (no-engine ROMs)."""
    src = MODELS / "tts"
    dest = assets / "tts"
    dest.mkdir(parents=True, exist_ok=True)
    names = (
        "model.onnx", "lexicon.txt", "tokens.txt",
        "phone.fst", "date.fst", "number.fst", "new_heteronym.fst",
    )
    required = ("model.onnx", "lexicon.txt", "tokens.txt")
    missing = [name for name in required if not (src / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing {missing} under {src}. Run "
            "`python -m jiandong_ai.scripts.download_tts_model` first."
        )
    copied = 0
    for name in names:
        if (src / name).exists():
            shutil.copy2(src / name, dest / name)
            copied += 1
    print(f"asset tts/ ({copied} files)")


def _copy_serena_prompts(assets: Path) -> None:
    """Copy only validated audio referenced by the generated Serena manifest."""
    import json
    from jiandong_ai.scripts.generate_serena_prompts import valid_wav, prompt_texts, normalize
    src = ROOT / "assets" / "voice" / "serena"
    manifest_path = src / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Generate Serena recordings before packaging: python -m jiandong_ai.scripts.generate_serena_prompts")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("speaker") != "Serena" or manifest.get("schema") != 1 or not manifest.get("clips"):
        raise ValueError("Invalid Serena manifest")
    missing = {normalize(text) for text in prompt_texts()} - manifest["clips"].keys()
    if missing:
        raise ValueError(f"Serena prompt generation is incomplete: {len(missing)} missing clips")
    names = set(manifest["clips"].values())
    for name in names:
        if not re.fullmatch(r"[a-f0-9]{24}\.wav", name) or not valid_wav(src / name):
            raise ValueError(f"Missing or invalid Serena recording: {name}")
    dest = assets / "voice" / "serena"
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(src / name, dest / name)
    shutil.copy2(manifest_path, dest / "manifest.json")
    for name in ("NOTICE.txt", "QWEN-LICENSE.txt"):
        if (src / name).exists():
            shutil.copy2(src / name, dest / name)
    print(f"asset Serena recordings ({len(names)} clips)")


def _copy_asr_models(assets: Path) -> None:
    """SenseVoice ASR + Silero VAD models for AsrBridge."""
    src = MODELS / "asr"
    dest = assets / "asr"
    dest.mkdir(parents=True, exist_ok=True)
    names = ("model.onnx", "tokens.txt", "silero_vad.onnx")
    missing = [name for name in names if not (src / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing {missing} under {src}. Run "
            "`python -m jiandong_ai.scripts.download_asr_model` first."
        )
    for name in names:
        shutil.copy2(src / name, dest / name)
    print(f"asset asr/ ({len(names)} files)")


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


_SHERPA_AAR_NAME = "sherpa-onnx-1.13.5.aar"
_SHERPA_AAR_URLS = (
    # JitPack build of the sherpa-onnx Android AAR (single file, ~49MB).
    "https://jitpack.io/com/github/k2-fsa/sherpa-onnx/sherpa-onnx/1.13.5/sherpa-onnx-1.13.5.aar",
    # Official release tarball; the AAR member is extracted from it.
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.8/sherpa-onnx-v1.13.8-android.tar.bz2",
)


def _ensure_sherpa_aar(app: Path) -> None:
    """Place the sherpa-onnx AAR under app/libs (idempotent)."""
    import tarfile
    import tempfile
    import urllib.request

    libs = app / "libs"
    libs.mkdir(parents=True, exist_ok=True)
    dest = libs / _SHERPA_AAR_NAME
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"sherpa-onnx aar already present: {dest.name}")
        return
    last_err: Exception | None = None
    for url in _SHERPA_AAR_URLS:
        try:
            print(f"Downloading {url}")
            if url.endswith(".aar"):
                urllib.request.urlretrieve(url, dest)
            else:
                with tempfile.NamedTemporaryFile(suffix=".tar.bz2", delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                try:
                    urllib.request.urlretrieve(url, tmp_path)
                    with tarfile.open(tmp_path) as tar:
                        member = next(m for m in tar.getmembers() if m.name.endswith(".aar"))
                        extracted = tar.extractfile(member)
                        if extracted is None:
                            raise RuntimeError(f"no readable aar in {url}")
                        dest.write_bytes(extracted.read())
                finally:
                    tmp_path.unlink(missing_ok=True)
            if dest.exists() and dest.stat().st_size > 1_000_000:
                print(f"sherpa-onnx aar saved: {dest} ({dest.stat().st_size} bytes)")
                return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"  failed: {exc}")
    raise RuntimeError(f"Could not obtain sherpa-onnx aar: {last_err}")


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
        f'implementation(files("libs/{_SHERPA_AAR_NAME}"))',
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
    # 每次从唯一模板生成；旧代码含有类名不代表已经带上本次修复。
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
import java.io.File

class MainActivity : FlutterFragmentActivity() {
    private var poseBridge: PoseCameraBridge? = null
    private var voiceBridge: VoiceCommandBridge? = null
    private var asrBridge: AsrBridge? = null
    private var ttsAnnouncer: TtsAnnouncer? = null
    private var audioPermissionRequested = false
    private val poseHandler = Handler(Looper.getMainLooper())
    private val posePoll = object : Runnable {
        override fun run() {
            poseBridge?.pollCommands()
            ensureAudioPermission()
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
        // 进程被系统杀死后，文件标记仍会留下；不能让旧助手/训练占住新进程的麦克风。
        val voiceDir = File(getExternalFilesDir(null) ?: filesDir, "jiandong_pose")
        for (name in listOf("training_active.flag", "assistant_active.flag", "asr_ready.flag",
            "assistant_wake.flag", "assistant_thinking.flag", "voice_session_active.flag",
            "training_control.json")) File(voiceDir, name).delete()
        poseBridge = PoseCameraBridge(this)
        val accessibility = getSystemService(android.content.Context.ACCESSIBILITY_SERVICE)
            as android.view.accessibility.AccessibilityManager
        val systemVoice = File(getExternalFilesDir(null) ?: filesDir, "jiandong_pose/system_reader.flag")
        if (accessibility.isEnabled && accessibility.isTouchExplorationEnabled) {
            systemVoice.parentFile?.mkdirs()
            systemVoice.writeText("1")
            File(systemVoice.parentFile, VoiceCommandBridge.FLAG_NAME).writeText("1")
        } else systemVoice.delete()
        poseHandler.post(posePoll)
        voiceBridge = VoiceCommandBridge(this).also { it.start() }
        asrBridge = AsrBridge(this).also { it.start() }
        ttsAnnouncer = TtsAnnouncer(this).also { it.start() }
        ensureCameraPermission()
        ensureAudioPermission()
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

    private fun voiceFlagExists(): Boolean {
        val dir = File(getExternalFilesDir(null) ?: filesDir, "jiandong_pose")
        return File(dir, VoiceCommandBridge.FLAG_NAME).exists()
    }

    private fun ensureAudioPermission() {
        // Only prompt when the accessibility voice switch is on — the default
        // user experience must not gain a new permission dialog.
        if (!voiceFlagExists() || audioPermissionRequested) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            != PackageManager.PERMISSION_GRANTED) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) {
            audioPermissionRequested = true
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.RECORD_AUDIO),
                REQ_AUDIO,
            )
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_AUDIO) {
            val granted = grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED
            voiceBridge?.onPermissionResult(granted)
            asrBridge?.onPermissionResult(granted)
            if (!granted) {
                val dir = File(getExternalFilesDir(null) ?: filesDir, "jiandong_pose")
                MediaPipePoseEngine.atomicWrite(File(dir, "training_speech.json"),
                    org.json.JSONObject().put("seq", System.nanoTime())
                        .put("text", "麦克风权限未获允许，当前无法接收语音口令。请使用系统读屏，在应用权限中允许麦克风后重新打开应用。")
                        .put("timestampMs", System.currentTimeMillis()).toString())
            }
        }
    }

    override fun onDestroy() {
        poseHandler.removeCallbacks(posePoll)
        poseBridge?.stop()
        voiceBridge?.stop()
        asrBridge?.stop()
        ttsAnnouncer?.stop()
        super.onDestroy()
    }

    companion object {
        private const val REQ_CAMERA = 0xC01
        private const val REQ_AUDIO = 0xA01
    }
}
""",
        encoding="utf-8",
    )
    print(f"patched {main}")


def _patch_manifest(manifest: Path) -> None:
    import re

    text = manifest.read_text(encoding="utf-8")
    # Voice accessibility mode needs the mic (KWS) and vibration (TTS fallback).
    for perm in ("RECORD_AUDIO", "VIBRATE"):
        needle = f'android.permission.{perm}'
        if needle not in text:
            text = text.replace(
                "<application",
                f'    <uses-permission android:name="{needle}" />\n    <application',
                1,
            )
            print(f"manifest permission added: {perm}")
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
    _copy_kws_models(assets)
    _copy_tts_models(assets)
    _copy_serena_prompts(assets)
    _copy_asr_models(assets)
    _copy_demo_frames(assets)
    _copy_kotlin(kotlin_root)
    gradle = app / "build.gradle.kts"
    if not gradle.exists():
        gradle = app / "build.gradle"
    if gradle.exists():
        _ensure_sherpa_aar(app)
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
