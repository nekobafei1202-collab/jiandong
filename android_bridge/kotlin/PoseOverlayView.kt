package com.flet.jiandong_ai

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.view.View
import kotlin.math.max

/** GPU-friendly skeleton overlay drawn directly above CameraX PreviewView. */
class PoseOverlayView(context: Context) : View(context) {
    private val bonePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(92, 225, 230)
        strokeWidth = dp(3f)
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val jointPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(92, 225, 230)
        style = Paint.Style.FILL
    }
    private val jointStroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        strokeWidth = dp(1f)
        style = Paint.Style.STROKE
    }

    @Volatile private var points: List<StableLandmark> = emptyList()
    @Volatile private var imageWidth = 1
    @Volatile private var imageHeight = 1

    fun submit(landmarks: List<StableLandmark>, sourceWidth: Int, sourceHeight: Int) {
        points = landmarks
        imageWidth = max(1, sourceWidth)
        imageHeight = max(1, sourceHeight)
        postInvalidateOnAnimation()
    }

    fun clearPose() {
        points = emptyList()
        postInvalidateOnAnimation()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val snapshot = points
        if (snapshot.size < 29) return

        val scale = max(width.toFloat() / imageWidth, height.toFloat() / imageHeight)
        val shownW = imageWidth * scale
        val shownH = imageHeight * scale
        val offsetX = (width - shownW) / 2f
        val offsetY = (height - shownH) / 2f

        fun xy(index: Int): Pair<Float, Float>? {
            val p = snapshot.getOrNull(index) ?: return null
            if (p.confidence < 0.28f) return null
            return Pair(offsetX + p.x * shownW, offsetY + p.y * shownH)
        }

        for ((a, b) in EDGES) {
            val pa = xy(a)
            val pb = xy(b)
            if (pa != null && pb != null) {
                canvas.drawLine(pa.first, pa.second, pb.first, pb.second, bonePaint)
            }
        }
        for (index in JOINTS) {
            val p = xy(index) ?: continue
            canvas.drawCircle(p.first, p.second, dp(4f), jointPaint)
            canvas.drawCircle(p.first, p.second, dp(4f), jointStroke)
        }
    }

    private fun dp(value: Float): Float = value * resources.displayMetrics.density

    companion object {
        // MediaPipe 33-point torso + limbs. Hands/feet details intentionally omitted.
        private val EDGES = arrayOf(
            7 to 2, 2 to 0, 0 to 5, 5 to 8,
            11 to 12,
            11 to 13, 13 to 15,
            12 to 14, 14 to 16,
            11 to 23, 12 to 24, 23 to 24,
            23 to 25, 25 to 27,
            24 to 26, 26 to 28,
        )
        private val JOINTS = intArrayOf(
            0, 2, 5, 7, 8, 11, 12, 13, 14, 15, 16,
            23, 24, 25, 26, 27, 28,
        )
    }
}
