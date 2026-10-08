package com.flet.jiandong_ai

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.fragment.app.FragmentActivity
import org.json.JSONObject
import java.io.File
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlin.math.roundToInt

/**
 * Native camera surface and HUD. Pixel frames never cross into Python/Flet;
 * only small pose/hud JSON payloads do.
 *
 * Enter = preview only (camera, no pose/timer). User taps「开始拍摄」to begin.
 */
class PoseTrainingActivity : FragmentActivity() {
    private val ui = Handler(Looper.getMainLooper())
    private lateinit var cameraExecutor: ExecutorService
    private lateinit var root: FrameLayout
    private lateinit var previewView: PreviewView
    private lateinit var overlay: PoseOverlayView
    private lateinit var engine: MediaPipePoseEngine
    private lateinit var bridgeDir: File
    private var provider: ProcessCameraProvider? = null
    private var front = true
    private var paused = false
    private var sessionActive = false
    private var startedAt = 0L
    private var eventSeq = 0L
    private var lastHudStamp = 0L

    private lateinit var timerText: TextView
    private lateinit var aiText: TextView
    private lateinit var actionText: TextView
    private lateinit var repText: TextView
    private lateinit var setText: TextView
    private var repBox: View? = null
    private var scoreBox: View? = null
    private var coachBanner: View? = null
    private var queuePrevButton: View? = null
    private var queueNextButton: View? = null
    private lateinit var scoreText: TextView
    private lateinit var coachTitle: TextView
    private lateinit var coachSubtitle: TextView
    private lateinit var controlsHost: FrameLayout
    private var pauseButton: TextView? = null
    private var demoPanel: View? = null
    private var demoImage: android.widget.ImageView? = null
    private var demoFallback: View? = null
    private val demoBitmaps = mutableListOf<android.graphics.Bitmap>()
    private var demoIndex = 0
    private var confirmOverlay: View? = null
    private var restOverlay: View? = null
    private var restSecondsText: TextView? = null
    private var restLabelText: TextView? = null
    private var metricsHost: View? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = Color.TRANSPARENT
        window.navigationBarColor = Color.TRANSPARENT

        front = intent.getBooleanExtra(EXTRA_FRONT, true)
        bridgeDir = File(getExternalFilesDir(null) ?: filesDir, "jiandong_pose").apply { mkdirs() }
        cameraExecutor = Executors.newSingleThreadExecutor()
        engine = MediaPipePoseEngine(this, bridgeDir) { points, width, height, _, _ ->
            overlay.submit(points, width, height)
        }.also {
            it.setFrontCamera(front)
            it.setPaused(true)
        }

        buildUi(intent.getStringExtra(EXTRA_ACTION).orEmpty().ifBlank { "深蹲" })
        applyInsets()
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                when {
                    confirmOverlay != null -> hideEndConfirm()
                    sessionActive && !paused -> togglePause()
                    sessionActive -> confirmEndTraining { stopAndSave() }
                    else -> closeWithoutSaving()
                }
            }
        })

        if (hasCameraPermission()) startCamera() else {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), REQ_CAMERA)
        }
        ui.post(clockTick)
        ui.post(hudPoll)
    }

    private fun buildUi(actionName: String) {
        root = FrameLayout(this).apply { setBackgroundColor(CANVAS) }
        previewView = PreviewView(this).apply {
            scaleType = PreviewView.ScaleType.FILL_CENTER
            implementationMode = PreviewView.ImplementationMode.PERFORMANCE
        }
        overlay = PoseOverlayView(this)
        root.addView(previewView, match())
        root.addView(overlay, match())

        val hud = FrameLayout(this)
        root.addView(hud, match())

        val top = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(16), dp(8), dp(16), 0)
        }
        top.addView(iconButton(android.R.drawable.ic_menu_close_clear_cancel) {
            if (sessionActive) confirmEndTraining { closeWithoutSaving() } else closeWithoutSaving()
        }, fixed(36, 36))
        top.addView(space(6))
        timerText = pillText("●  00:00", 12f, bold = true).apply { setTextColor(Color.WHITE) }
        top.addView(timerText, wrap())
        top.addView(space(6))
        actionText = pillText(actionName, 14f, bold = true).apply {
            gravity = Gravity.CENTER
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
        }
        top.addView(actionText, LinearLayout.LayoutParams(0, dp(38), 1f))
        top.addView(space(6))
        aiText = pillText("● AI未激活", 11f, bold = true)
        top.addView(aiText, wrap())
        top.addView(space(6))
        top.addView(iconButton(android.R.drawable.ic_menu_camera) { switchCamera() }, fixed(36, 36))
        hud.addView(top, FrameLayout.LayoutParams(MATCH, dp(58), Gravity.TOP))

        val metrics = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.TOP
            setPadding(dp(16), 0, dp(16), 0)
        }
        val demo = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(8), dp(8), dp(8), dp(8))
            background = glass(16f)
            addView(label("正确的姿势", 11f, true), LinearLayout.LayoutParams(MATCH, dp(26)))
            val fallback = label("跟随示范\n保持全身入镜", 12f, false).apply {
                gravity = Gravity.CENTER
                setTextColor(TEXT_SECONDARY)
            }
            demoFallback = fallback
            val image = android.widget.ImageView(this@PoseTrainingActivity).apply {
                scaleType = android.widget.ImageView.ScaleType.FIT_CENTER
                visibility = View.GONE
            }
            demoImage = image
            addView(FrameLayout(this@PoseTrainingActivity).apply {
                background = rounded(Color.rgb(26, 36, 48), 12f, GLASS_STROKE)
                addView(fallback, match())
                addView(image, match())
            }, LinearLayout.LayoutParams(MATCH, dp(112)))
        }
        demoPanel = demo
        applyDemoVisibility(actionName, guideOnly = isGuideOnlyAction(actionName))
        metrics.addView(demo, fixed(108, 154))

        val reps = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setText = pillText("组 1/4", 12f, true)
            addView(setText, wrap())
            addView(spaceV(10))
            repText = pillText("0 次", 30f, true).apply {
                gravity = Gravity.CENTER
                setPadding(dp(12), dp(8), dp(12), dp(8))
            }
            addView(repText, wrap())
        }
        repBox = reps
        metrics.addView(reps, LinearLayout.LayoutParams(0, dp(160), 1f))

        val score = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            scoreText = label("--", 22f, true).apply {
                gravity = Gravity.CENTER
                background = rounded(Color.argb(90, 18, 24, 32), 999f, CYAN)
            }
            addView(scoreText, fixed(92, 92))
            addView(label("姿势", 12f, true).apply {
                gravity = Gravity.CENTER
                setPadding(0, dp(6), 0, 0)
            }, fixed(92, 28))
        }
        scoreBox = score
        metrics.addView(score, fixed(92, 126))
        metricsHost = metrics
        hud.addView(metrics, FrameLayout.LayoutParams(MATCH, dp(170), Gravity.TOP).apply { topMargin = dp(72) })

        val rest = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            visibility = View.GONE
            restLabelText = label("组间休息", 18f, true).apply {
                gravity = Gravity.CENTER
                setTextColor(TEXT_SECONDARY)
            }
            restSecondsText = label("60", 72f, true).apply {
                gravity = Gravity.CENTER
                setTextColor(Color.WHITE)
            }
            addView(restLabelText)
            addView(spaceV(8))
            addView(restSecondsText)
            addView(label("秒", 16f, false).apply {
                gravity = Gravity.CENTER
                setTextColor(TEXT_SECONDARY)
            })
        }
        restOverlay = rest
        hud.addView(rest, FrameLayout.LayoutParams(MATCH, MATCH, Gravity.CENTER).apply {
            topMargin = dp(72)
            bottomMargin = dp(120)
        })

        val banner = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(12), dp(16), dp(12))
            background = rounded(Color.argb(220, 74, 59, 43), 16f, Color.argb(80, 255, 208, 138))
            coachTitle = label("准备中", 16f, true)
            coachSubtitle = label("站稳后点击开始拍摄", 13f, false).apply {
                setTextColor(Color.rgb(255, 208, 138))
            }
            addView(coachTitle)
            addView(coachSubtitle)
        }
        coachBanner = banner
        hud.addView(banner, FrameLayout.LayoutParams(MATCH, dp(78), Gravity.BOTTOM).apply {
            leftMargin = dp(16)
            rightMargin = dp(16)
            bottomMargin = dp(116)
        })
        applyGuideMetricsVisibility(isGuideOnlyAction(actionName))

        // ‹ › queue arrows live in the bottom control rows so the action
        // name keeps the full top-bar width.
        queuePrevButton = navArrow("上一组") { emitEvent("queue_prev") }
        queueNextButton = navArrow("下一组") { emitEvent("queue_next") }

        controlsHost = FrameLayout(this)
        hud.addView(controlsHost, FrameLayout.LayoutParams(MATCH, dp(100), Gravity.BOTTOM))
        showPreviewControls()
        setContentView(root)
    }

    private fun reparent(button: View?) {
        (button?.parent as? ViewGroup)?.removeView(button)
    }

    private fun showPreviewControls() {
        controlsHost.removeAllViews()
        pauseButton = null
        val start = label("开始拍摄", 16f, true).apply {
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
            background = rounded(CORAL, 999f, CORAL)
            setOnClickListener { beginSession() }
        }
        val wrap = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(dp(16), dp(8), dp(16), dp(12))
            // Set nav only applies while recording — hide during preview.
            queuePrevButton?.visibility = View.GONE
            queueNextButton?.visibility = View.GONE
            addView(start, LinearLayout.LayoutParams(0, dp(54), 1f))
        }
        controlsHost.addView(wrap, match())
    }

    private fun showActiveControls() {
        controlsHost.removeAllViews()
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(dp(16), dp(8), dp(16), dp(12))
        }
        val pause = label("Ⅱ\n暂停", 13f, true).apply {
            gravity = Gravity.CENTER
            background = glass(999f)
            setOnClickListener { togglePause() }
        }
        reparent(queuePrevButton)
        reparent(queueNextButton)
        row.addView(queuePrevButton!!, fixed(72, 48))
        row.addView(space(12))
        pauseButton = pause
        row.addView(pause, fixed(70, 70))
        row.addView(space(12))
        val stop = label("■", 24f, true).apply {
            gravity = Gravity.CENTER
            setTextColor(RECORD_RED)
            background = rounded(Color.argb(110, 0, 0, 0), 999f, Color.WHITE, dp(4))
            setOnClickListener { confirmEndTraining { stopAndSave() } }
        }
        row.addView(stop, fixed(78, 78))
        row.addView(space(12))
        row.addView(queueNextButton!!, fixed(72, 48))
        controlsHost.addView(row, match())
    }

    private fun beginSession() {
        if (sessionActive) return
        sessionActive = true
        paused = false
        startedAt = SystemClock.elapsedRealtime()
        engine.setPaused(false)
        aiText.text = "● AI已激活"
        coachTitle.text = "准备中"
        coachSubtitle.text = "站稳后开始下蹲"
        showActiveControls()
        applyGuideMetricsVisibility(isGuideOnlyAction(actionText.text.toString()))
        bindCamera()
        emitEvent("begin")
    }

    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            provider = future.get()
            bindCamera()
        }, ContextCompat.getMainExecutor(this))
    }

    private fun bindCamera() {
        val cameraProvider = provider ?: return
        cameraProvider.unbindAll()
        val selector = if (front) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
        val preview = Preview.Builder().build().also { it.setSurfaceProvider(previewView.surfaceProvider) }
        if (!sessionActive) {
            cameraProvider.bindToLifecycle(this, selector, preview)
            return
        }
        val analysis = ImageAnalysis.Builder()
            .setTargetResolution(android.util.Size(480, 640))
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()
        analysis.setAnalyzer(cameraExecutor) { image ->
            try {
                if (!paused) engine.analyze(image)
            } finally {
                image.close()
            }
        }
        cameraProvider.bindToLifecycle(this, selector, preview, analysis)
    }

    private fun switchCamera() {
        front = !front
        overlay.clearPose()
        engine.setFrontCamera(front)
        bindCamera()
        emitEvent("switch", JSONObject().put("front", front))
    }

    private fun togglePause() {
        if (!sessionActive) return
        paused = !paused
        engine.setPaused(paused)
        aiText.text = if (paused) "● AI已暂停" else "● AI已激活"
        pauseButton?.text = if (paused) "▶\n继续" else "Ⅱ\n暂停"
        emitEvent(if (paused) "pause" else "resume")
    }

    private fun stopAndSave() {
        emitEvent("stop")
        finish()
    }

    private fun confirmEndTraining(onConfirm: () -> Unit) {
        if (confirmOverlay != null) return
        val dim = FrameLayout(this).apply {
            setBackgroundColor(Color.argb(150, 4, 6, 10))
            isClickable = true
            setOnClickListener { hideEndConfirm() }
        }
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(24), dp(22), dp(24), dp(18))
            background = rounded(Color.argb(242, 18, 24, 32), 16f, GLASS_STROKE)
            isClickable = true
        }
        card.addView(label("结束训练？", 17f, true).apply { gravity = Gravity.CENTER })
        card.addView(spaceV(10))
        card.addView(label("结束后可查看训练总结，并可选择保存记录。", 13f, false).apply {
            setTextColor(TEXT_SECONDARY)
            gravity = Gravity.CENTER
        })
        card.addView(spaceV(20))
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        row.addView(label("取消", 14f, true).apply {
            gravity = Gravity.CENTER
            background = glass(999f)
            setOnClickListener { hideEndConfirm() }
        }, fixed(108, 46))
        row.addView(space(16))
        row.addView(label("结束", 14f, true).apply {
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
            background = rounded(CORAL, 999f, CORAL)
            setOnClickListener {
                hideEndConfirm()
                onConfirm()
            }
        }, fixed(108, 46))
        card.addView(row)
        dim.addView(card, FrameLayout.LayoutParams(MATCH, WRAP, Gravity.CENTER).apply {
            leftMargin = dp(44)
            rightMargin = dp(44)
        })
        root.addView(dim, match())
        confirmOverlay = dim
    }

    private fun hideEndConfirm() {
        confirmOverlay?.let { root.removeView(it) }
        confirmOverlay = null
    }

    private fun loadDemoFrames(actionName: String) {
        val dir = DEMO_DIRS[actionName] ?: return
        val assetDir = "demo/$dir"
        val names = try {
            assets.list(assetDir)?.filter { it.endsWith(".png", ignoreCase = true) }?.sorted()
        } catch (_: Exception) {
            null
        }.orEmpty()
        if (names.isEmpty()) return
        // Source frames are 240x320; halve to keep the loop cheap.
        val opts = android.graphics.BitmapFactory.Options().apply { inSampleSize = 2 }
        for (name in names) {
            try {
                assets.open("$assetDir/$name").use { input ->
                    android.graphics.BitmapFactory.decodeStream(input, null, opts)
                }?.let { demoBitmaps.add(it) }
            } catch (_: Exception) {
            }
        }
        if (demoBitmaps.isEmpty()) return
        // Frames loaded: drop the hint text so it doesn't show through the
        // transparent-background mannequin frames.
        demoFallback?.visibility = View.GONE
        demoImage?.apply {
            setImageBitmap(demoBitmaps[0])
            visibility = View.VISIBLE
        }
        ui.postDelayed(demoTick, intervalFor(demoBitmaps.size))
    }

    private fun intervalFor(frameCount: Int): Long {
        val n = if (frameCount < 1) 1 else frameCount
        val ms = DEMO_LOOP_MS / n
        return if (ms < 1L) 1L else ms
    }

    private val demoTick = object : Runnable {
        override fun run() {
            if (demoBitmaps.isEmpty()) return
            demoIndex = (demoIndex + 1) % demoBitmaps.size
            demoImage?.setImageBitmap(demoBitmaps[demoIndex])
            ui.postDelayed(this, intervalFor(demoBitmaps.size))
        }
    }

    private fun closeWithoutSaving() {
        emitEvent("close")
        finish()
    }

    private fun emitEvent(type: String, extra: JSONObject = JSONObject()) {
        val payload = extra
            .put("seq", ++eventSeq)
            .put("type", type)
            .put("timestampMs", System.currentTimeMillis())
        MediaPipePoseEngine.atomicWrite(File(bridgeDir, "event.json"), payload.toString())
    }

    private val clockTick = object : Runnable {
        override fun run() {
            if (sessionActive && !paused && startedAt > 0L) {
                val seconds = ((SystemClock.elapsedRealtime() - startedAt) / 1000).toInt()
                timerText.text = "●  %02d:%02d".format(seconds / 60, seconds % 60)
            } else if (!sessionActive) {
                timerText.text = "●  00:00"
            }
            ui.postDelayed(this, 500)
        }
    }

    private val hudPoll = object : Runnable {
        override fun run() {
            val file = File(bridgeDir, "hud.json")
            if (file.exists() && file.lastModified() != lastHudStamp) {
                try {
                    val hud = JSONObject(file.readText())
                    lastHudStamp = file.lastModified()
                    // Queue state applies in preview too — the action label and
                    // ‹ › arrows must track Python's queue before「开始拍摄」.
                    val action = hud.optString("action", "")
                    val guideOnly = hud.optBoolean("guideOnly", false) ||
                        (action.isNotBlank() && isGuideOnlyAction(action))
                    if (action.isNotBlank() && action != actionText.text.toString()) {
                        switchAction(action, guideOnly = guideOnly)
                    } else if (action.isNotBlank() || hud.has("guideOnly")) {
                        applyDemoVisibility(
                            if (action.isNotBlank()) action else actionText.text.toString(),
                            guideOnly = guideOnly,
                        )
                    }
                    if (hud.has("setNav") || hud.has("queueNav")) {
                        val show = if (hud.has("setNav")) {
                            hud.optBoolean("setNav", false)
                        } else {
                            hud.optBoolean("queueNav", false)
                        }
                        val vis = if (show) View.VISIBLE else View.GONE
                        queuePrevButton?.visibility = vis
                        queueNextButton?.visibility = vis
                        if (show) {
                            val prevLabel = hud.optString("prevLabel", "上一组")
                            val nextLabel = hud.optString("nextLabel", "下一组")
                            if (prevLabel.isNotBlank()) {
                                (queuePrevButton as? TextView)?.text = prevLabel
                            }
                            if (nextLabel.isNotBlank()) {
                                (queueNextButton as? TextView)?.text = nextLabel
                            }
                            val prevOk = hud.optBoolean("setNavPrev", true)
                            val nextOk = hud.optBoolean("setNavNext", true)
                            queuePrevButton?.isEnabled = prevOk
                            queuePrevButton?.alpha = if (prevOk) 1f else 0.35f
                            queueNextButton?.isEnabled = nextOk
                            queueNextButton?.alpha = if (nextOk) 1f else 0.35f
                        }
                    }
                    val resting = hud.optBoolean("resting", false)
                    applyRestOverlay(
                        resting = resting,
                        seconds = hud.optInt("restSeconds", 0),
                        label = hud.optString("restLabel", "组间休息"),
                        action = if (action.isNotBlank()) action else actionText.text.toString(),
                        guideOnly = guideOnly,
                    )
                    applyGuideMetricsVisibility(guideOnly || resting)
                    if (sessionActive) {
                        if (!guideOnly && !resting) {
                            // setIndex = current set (1..total), setTotal = target sets.
                            val setIndex = hud.optInt("setIndex", 1).coerceAtLeast(1)
                            val setTotal = hud.optInt("setTotal", 4).coerceAtLeast(1)
                            setText.text = "组 $setIndex/$setTotal"
                            val repsDone = hud.optInt("reps", 0)
                            val unit = hud.optString("unit", "次")
                            val repTarget = hud.optInt("repTarget", 0)
                            repText.text = if (repTarget > 0) {
                                "$repsDone/$repTarget $unit"
                            } else {
                                "$repsDone $unit"
                            }
                            val scoreVal = hud.optInt("score", 0)
                            scoreText.text = if (scoreVal > 0) "$scoreVal%" else "--"
                            coachTitle.text = hud.optString("title", "准备中")
                            coachSubtitle.text = hud.optString("subtitle", "保持全身入镜")
                        }
                    }
                } catch (_: Exception) {
                }
            }
            ui.postDelayed(this, 100)
        }
    }

    private fun isGuideOnlyAction(name: String): Boolean {
        val n = name.trim()
        return n == "热身" || n == "拉伸"
    }

    private fun applyRestOverlay(
        resting: Boolean,
        seconds: Int,
        label: String,
        action: String,
        guideOnly: Boolean,
    ) {
        if (resting) {
            restLabelText?.text = label.ifBlank { "组间休息" }
            restSecondsText?.text = seconds.coerceAtLeast(0).toString()
            restOverlay?.visibility = View.VISIBLE
            metricsHost?.visibility = View.GONE
            demoPanel?.visibility = View.GONE
        } else {
            restOverlay?.visibility = View.GONE
            metricsHost?.visibility = View.VISIBLE
            applyDemoVisibility(action, guideOnly)
        }
    }

    private fun applyGuideMetricsVisibility(guideOnly: Boolean) {
        val metricsVis = if (guideOnly) View.GONE else View.VISIBLE
        repBox?.visibility = metricsVis
        scoreBox?.visibility = metricsVis
        // Guide steps / rest: no coach/评价 banner.
        coachBanner?.visibility = if (guideOnly && sessionActive) View.GONE else View.VISIBLE
    }

    private fun applyDemoVisibility(name: String, guideOnly: Boolean) {
        if (guideOnly || isGuideOnlyAction(name)) {
            ui.removeCallbacks(demoTick)
            demoBitmaps.forEach { it.recycle() }
            demoBitmaps.clear()
            demoIndex = 0
            demoImage?.apply {
                setImageDrawable(null)
                visibility = View.GONE
            }
            demoPanel?.visibility = View.GONE
            return
        }
        demoPanel?.visibility = View.VISIBLE
        if (demoBitmaps.isEmpty()) {
            loadDemoFrames(name)
        }
    }

    private fun switchAction(name: String, guideOnly: Boolean = isGuideOnlyAction(name)) {
        actionText.text = name
        ui.removeCallbacks(demoTick)
        demoBitmaps.forEach { it.recycle() }
        demoBitmaps.clear()
        demoIndex = 0
        demoImage?.apply {
            setImageDrawable(null)
            visibility = View.GONE
        }
        demoFallback?.visibility = View.VISIBLE
        if (guideOnly || isGuideOnlyAction(name)) {
            demoPanel?.visibility = View.GONE
            applyGuideMetricsVisibility(true)
            return
        }
        demoPanel?.visibility = View.VISIBLE
        applyGuideMetricsVisibility(false)
        loadDemoFrames(name)
    }

    private fun applyInsets() {
        ViewCompat.setOnApplyWindowInsetsListener(root) { _, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            root.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
    }

    private fun hasCameraPermission(): Boolean =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, results)
        if (requestCode == REQ_CAMERA && results.firstOrNull() == PackageManager.PERMISSION_GRANTED) startCamera()
        else finish()
    }

    override fun onDestroy() {
        ui.removeCallbacksAndMessages(null)
        demoBitmaps.forEach { it.recycle() }
        demoBitmaps.clear()
        demoImage = null
        provider?.unbindAll()
        engine.close()
        cameraExecutor.shutdownNow()
        super.onDestroy()
    }

    private fun label(text: String, size: Float, bold: Boolean) = TextView(this).apply {
        this.text = text
        textSize = size
        setTextColor(Color.WHITE)
        typeface = if (bold) Typeface.DEFAULT_BOLD else Typeface.DEFAULT
    }

    private fun pillText(text: String, size: Float, bold: Boolean) = label(text, size, bold).apply {
        gravity = Gravity.CENTER
        setPadding(dp(10), dp(7), dp(10), dp(7))
        background = glass(999f)
    }

    private fun iconButton(res: Int, click: () -> Unit) = ImageButton(this).apply {
        setImageResource(res)
        setColorFilter(Color.WHITE)
        setPadding(dp(8), dp(8), dp(8), dp(8))
        background = glass(999f)
        setOnClickListener { click() }
    }

    private fun navArrow(text: String, click: () -> Unit) = label(text, 13f, true).apply {
        gravity = Gravity.CENTER
        background = glass(999f)
        visibility = View.GONE
        setOnClickListener { click() }
    }

    private fun glass(radius: Float) = rounded(Color.argb(150, 18, 24, 32), radius, GLASS_STROKE)

    private fun rounded(fill: Int, radius: Float, stroke: Int, strokeWidth: Int = dp(1)) =
        GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = dp(radius)
            setColor(fill)
            setStroke(strokeWidth, stroke)
        }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).roundToInt()
    private fun dp(value: Float): Float = value * resources.displayMetrics.density
    private fun match() = FrameLayout.LayoutParams(MATCH, MATCH)
    private fun fixed(w: Int, h: Int) = LinearLayout.LayoutParams(dp(w), dp(h))
    private fun wrap() = LinearLayout.LayoutParams(WRAP, WRAP)
    private fun space(width: Int) = View(this).apply { layoutParams = fixed(width, 1) }
    private fun spaceV(height: Int) = View(this).apply { layoutParams = fixed(1, height) }

    companion object {
        const val EXTRA_FRONT = "front"
        const val EXTRA_ACTION = "action"
        private const val REQ_CAMERA = 0xC02
        private const val MATCH = ViewGroup.LayoutParams.MATCH_PARENT
        private const val WRAP = ViewGroup.LayoutParams.WRAP_CONTENT
        private val CANVAS = Color.rgb(7, 10, 15)
        private val CYAN = Color.rgb(92, 225, 230)
        private val CORAL = Color.rgb(232, 140, 122)
        private val RECORD_RED = Color.rgb(255, 59, 48)
        private val TEXT_SECONDARY = Color.rgb(168, 176, 188)
        private val GLASS_STROKE = Color.argb(55, 255, 255, 255)
        // White-mannequin PNG frame sets under assets/demo/<dir> (interval:
        // demo_guide_pane.py spreads one 2200ms loop over the frame count).
        private const val DEMO_LOOP_MS = 2200L
        private val DEMO_DIRS = mapOf(
            "深蹲" to "squat_white_mannequin",
            "俯卧撑" to "pushup_white_mannequin",
            "弓步蹲" to "reverse_lunge_white_mannequin",
            "平板支撑" to "plank_white_mannequin",
            "开合跳" to "jumping_jack_white_mannequin",
            "卷腹" to "crunch_white_mannequin",
            "高抬腿" to "high_knees_white_mannequin",
        )
    }
}
