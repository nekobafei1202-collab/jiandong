package com.flet.jiandong_ai

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.os.SystemClock
import android.util.Log
import androidx.camera.core.ImageProxy
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.framework.image.MPImage
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarker
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarkerResult
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

class MediaPipePoseEngine(
    context: Context,
    private val outputDir: File,
    private val onResult: (List<StableLandmark>, Int, Int, Long, Long) -> Unit,
) : AutoCloseable {
    private val tag = "MediaPipePose"
    private val smoother = PoseSmoother()
    private val busy = AtomicBoolean(false)
    private val sequence = AtomicLong(0)
    @Volatile private var front = true
    @Volatile private var paused = false
    @Volatile private var sourceWidth = 1
    @Volatile private var sourceHeight = 1

    private val landmarker: PoseLandmarker

    init {
        outputDir.mkdirs()
        val options = PoseLandmarker.PoseLandmarkerOptions.builder()
            .setBaseOptions(
                BaseOptions.builder()
                    .setModelAssetPath("models/pose_landmarker_full.task")
                    .build()
            )
            .setRunningMode(RunningMode.LIVE_STREAM)
            .setNumPoses(1)
            .setMinPoseDetectionConfidence(0.55f)
            .setMinPosePresenceConfidence(0.55f)
            .setMinTrackingConfidence(0.60f)
            .setResultListener(::handleResult)
            .setErrorListener { error ->
                busy.set(false)
                Log.e(tag, "MediaPipe inference failed", error)
            }
            .build()
        landmarker = PoseLandmarker.createFromOptions(context, options)
        Log.i(tag, "Pose Landmarker Full ready")
    }

    fun setFrontCamera(value: Boolean) {
        if (front != value) smoother.reset()
        front = value
    }

    fun setPaused(value: Boolean) {
        paused = value
        if (value) busy.set(false)
    }

    fun analyze(image: ImageProxy) {
        if (paused || !busy.compareAndSet(false, true)) return
        val bitmap = imageToBitmap(image)
        if (bitmap == null) {
            busy.set(false)
            return
        }
        sourceWidth = bitmap.width
        sourceHeight = bitmap.height
        val mpImage = BitmapImageBuilder(bitmap).build()
        try {
            landmarker.detectAsync(mpImage, SystemClock.uptimeMillis())
        } catch (error: Exception) {
            busy.set(false)
            mpImage.close()
            Log.w(tag, "detectAsync failed", error)
        }
    }

    private fun handleResult(result: PoseLandmarkerResult, input: MPImage) {
        try {
            val raw = result.landmarks().firstOrNull()
            val stable = smoother.update(raw).map { point ->
                if (front) point.copy(x = 1f - point.x) else point
            }
            val frameId = sequence.incrementAndGet()
            val timestamp = result.timestampMs()
            publishPose(stable, frameId, timestamp, sourceWidth, sourceHeight)
            onResult(stable, sourceWidth, sourceHeight, frameId, timestamp)
        } catch (error: Exception) {
            Log.w(tag, "result handling failed", error)
        } finally {
            input.close()
            busy.set(false)
        }
    }

    private fun publishPose(
        points: List<StableLandmark>,
        frameId: Long,
        timestamp: Long,
        width: Int,
        height: Int,
    ) {
        val keypoints = JSONArray()
        for ((index, name) in COCO17) {
            val p = points.getOrNull(index) ?: continue
            keypoints.put(
                JSONObject()
                    .put("name", name)
                    .put("x", p.x.toDouble())
                    .put("y", p.y.toDouble())
                    .put("confidence", p.confidence.toDouble())
            )
        }
        val payload = JSONObject()
            .put("frameId", frameId)
            .put("timestampMs", timestamp)
            .put("imageWidth", 0)
            .put("imageHeight", 0)
            .put("sourceWidth", width)
            .put("sourceHeight", height)
            .put("isFrontCamera", front)
            .put("rotationDegrees", 0)
            .put("keypoints", keypoints)
        atomicWrite(File(outputDir, "pose.json"), payload.toString())
    }

    private fun imageToBitmap(image: ImageProxy): Bitmap? {
        return try {
            val plane = image.planes[0]
            val buffer = plane.buffer
            buffer.rewind()
            val raw = Bitmap.createBitmap(image.width, image.height, Bitmap.Config.ARGB_8888)
            raw.copyPixelsFromBuffer(buffer)
            val rotation = image.imageInfo.rotationDegrees
            if (rotation == 0) raw else {
                val matrix = Matrix().apply { postRotate(rotation.toFloat()) }
                Bitmap.createBitmap(raw, 0, 0, raw.width, raw.height, matrix, true).also {
                    if (it !== raw) raw.recycle()
                }
            }
        } catch (error: Exception) {
            Log.w(tag, "RGBA conversion failed", error)
            null
        }
    }

    override fun close() {
        try {
            landmarker.close()
        } catch (_: Exception) {
        }
        smoother.reset()
    }

    companion object {
        private val COCO17 = arrayOf(
            0 to "nose",
            2 to "leftEye",
            5 to "rightEye",
            7 to "leftEar",
            8 to "rightEar",
            11 to "leftShoulder",
            12 to "rightShoulder",
            13 to "leftElbow",
            14 to "rightElbow",
            15 to "leftWrist",
            16 to "rightWrist",
            23 to "leftHip",
            24 to "rightHip",
            25 to "leftKnee",
            26 to "rightKnee",
            27 to "leftAnkle",
            28 to "rightAnkle",
        )

        fun atomicWrite(target: File, value: String) {
            target.parentFile?.mkdirs()
            val temp = File(target.parentFile, "${target.name}.tmp")
            temp.writeText(value)
            if (!temp.renameTo(target)) {
                target.writeText(value)
                temp.delete()
            }
        }
    }
}
