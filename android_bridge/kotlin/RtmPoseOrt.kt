package com.flet.jiandong_ai

import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.nio.FloatBuffer
import java.util.Collections

/**
 * Lightweight RTMPose-t (Good-GYM ONNX) via onnxruntime-android.
 * Full-frame box (skips YOLOX) for a simpler mobile path.
 */
class RtmPoseOrt(context: Context) {
    private val tag = "RtmPoseOrt"
    private var env: OrtEnvironment? = null
    private var session: OrtSession? = null
    private val inputW = 192
    private val inputH = 256

    init {
        try {
            val localEnv = OrtEnvironment.getEnvironment()
            env = localEnv
            val bytes = context.assets.open("models/$POSE_ASSET").use { it.readBytes() }
            session = localEnv.createSession(bytes, OrtSession.SessionOptions())
            Log.i(tag, "RTMPose session ready")
        } catch (e: Exception) {
            Log.e(tag, "ORT init failed — camera preview still works", e)
            session = null
        }
    }

    fun infer(bitmap: Bitmap): FloatArray? {
        val sess = session ?: return null
        val envLocal = env ?: return null
        return try {
            val input = preprocess(bitmap)
            // Direct ByteBuffer avoids an extra copy and matches ORT Android samples.
            val buf = FloatBuffer.allocate(input.size)
            buf.put(input)
            buf.rewind()
            val shape = longArrayOf(1, 3, inputH.toLong(), inputW.toLong())
            OnnxTensor.createTensor(envLocal, buf, shape).use { tensor ->
                val inputName = sess.inputNames.iterator().next()
                val wanted = sess.outputNames
                sess.run(Collections.singletonMap(inputName, tensor), wanted).use { result ->
                    decodeSimcc(result)
                }
            }
        } catch (e: Exception) {
            Log.w(tag, "infer failed", e)
            null
        } catch (e: Error) {
            // JNI / linkage failures — disable further ORT so preview can survive.
            Log.e(tag, "infer fatal — disabling ORT", e)
            try {
                session?.close()
            } catch (_: Exception) {
            }
            session = null
            null
        }
    }

    private fun preprocess(src: Bitmap): FloatArray {
        val scaled = Bitmap.createScaledBitmap(src, inputW, inputH, true)
        val pixels = IntArray(inputW * inputH)
        scaled.getPixels(pixels, 0, inputW, 0, 0, inputW, inputH)
        val out = FloatArray(3 * inputW * inputH)
        val mean = floatArrayOf(123.675f, 116.28f, 103.53f)
        val std = floatArrayOf(58.395f, 57.12f, 57.375f)
        var i = 0
        while (i < pixels.size) {
            val c = pixels[i]
            val r = ((c shr 16) and 0xff).toFloat()
            val g = ((c shr 8) and 0xff).toFloat()
            val b = (c and 0xff).toFloat()
            out[0 * inputW * inputH + i] = (r - mean[0]) / std[0]
            out[1 * inputW * inputH + i] = (g - mean[1]) / std[1]
            out[2 * inputW * inputH + i] = (b - mean[2]) / std[2]
            i++
        }
        return out
    }

    private fun decodeSimcc(result: OrtSession.Result): FloatArray {
        require(result.size() >= 2) { "expected simcc_x + simcc_y" }
        // Prefer OnnxTensor float buffers — avoids nested-array JNI conversion quirks.
        val sx = tensorTo3d(result[0])
        val sy = tensorTo3d(result[1])
        val n = 17
        val wx = sx[0][0].size
        val hy = sy[0][0].size
        val out = FloatArray(n * 3)
        for (k in 0 until n) {
            var bestX = 0
            var bestXv = Float.NEGATIVE_INFINITY
            for (x in 0 until wx) {
                val v = sx[0][k][x]
                if (v > bestXv) {
                    bestXv = v
                    bestX = x
                }
            }
            var bestY = 0
            var bestYv = Float.NEGATIVE_INFINITY
            for (y in 0 until hy) {
                val v = sy[0][k][y]
                if (v > bestYv) {
                    bestYv = v
                    bestY = y
                }
            }
            out[k * 3] = bestX.toFloat() / (wx - 1).coerceAtLeast(1)
            out[k * 3 + 1] = bestY.toFloat() / (hy - 1).coerceAtLeast(1)
            val conf = (0.5f + 0.5f * kotlin.math.tanh(((bestXv + bestYv) / 2f) / 10f))
            out[k * 3 + 2] = conf
        }
        return out
    }

    @Suppress("UNCHECKED_CAST")
    private fun tensorTo3d(value: Any): Array<Array<FloatArray>> {
        val tensor = when (value) {
            is OnnxTensor -> value
            is Map.Entry<*, *> -> value.value as? OnnxTensor
            else -> null
        }
        if (tensor != null) {
            val shape = tensor.info.shape
            require(shape.size >= 3) { "simcc rank ${shape.size}" }
            val a = shape[1].toInt()
            val b = shape[2].toInt()
            val buf = tensor.floatBuffer.duplicate()
            buf.rewind()
            val arr = Array(1) { Array(a) { FloatArray(b) } }
            for (i in 0 until a) {
                for (j in 0 until b) {
                    arr[0][i][j] = buf.get()
                }
            }
            return arr
        }
        if (value is Array<*>) {
            return value as Array<Array<FloatArray>>
        }
        // Result[i] may already be the nested Java array from .value
        val raw = try {
            value.javaClass.getMethod("getValue").invoke(value)
        } catch (_: Exception) {
            null
        }
        if (raw is Array<*>) {
            return raw as Array<Array<FloatArray>>
        }
        throw IllegalArgumentException("bad tensor ${value.javaClass}")
    }

    companion object {
        const val POSE_ASSET = "rtmpose-t_simcc-body7_pt-body7_420e-256x192-026a1439_20230504.onnx"
        val COCO17 = arrayOf(
            "nose", "leftEye", "rightEye", "leftEar", "rightEar",
            "leftShoulder", "rightShoulder", "leftElbow", "rightElbow",
            "leftWrist", "rightWrist", "leftHip", "rightHip",
            "leftKnee", "rightKnee", "leftAnkle", "rightAnkle"
        )
    }
}
