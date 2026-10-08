package com.flet.jiandong_ai

import com.google.mediapipe.tasks.components.containers.NormalizedLandmark
import kotlin.math.abs
import kotlin.math.hypot

data class StableLandmark(
    val x: Float,
    val y: Float,
    val z: Float,
    val confidence: Float,
)

/**
 * Confidence hysteresis + velocity-adaptive EMA.
 *
 * Static joints are deliberately damped; fast intentional motion catches up
 * quickly. Short confidence dips retain the last point instead of flashing.
 */
class PoseSmoother(private val count: Int = 33) {
    private data class State(
        var x: Float = 0f,
        var y: Float = 0f,
        var z: Float = 0f,
        var confidence: Float = 0f,
        var visible: Boolean = false,
        var misses: Int = 0,
    )

    private val states = Array(count) { State() }
    private var personVisible = false
    private var personHits = 0
    private var personMisses = 0

    fun reset() {
        states.indices.forEach { states[it] = State() }
        personVisible = false
        personHits = 0
        personMisses = 0
    }

    fun update(raw: List<NormalizedLandmark>?): List<StableLandmark> {
        val hasPose = !raw.isNullOrEmpty()
        if (hasPose) {
            personHits++
            personMisses = 0
            if (personHits >= 2) personVisible = true
        } else {
            personHits = 0
            personMisses++
            if (personMisses >= 7) personVisible = false
        }

        val result = ArrayList<StableLandmark>(count)
        for (i in 0 until count) {
            val state = states[i]
            val lm = raw?.getOrNull(i)
            val confidence = if (lm == null) 0f else {
                val visibility = lm.visibility().orElse(0f)
                val presence = lm.presence().orElse(visibility)
                minOf(visibility, presence).coerceIn(0f, 1f)
            }

            val enter = 0.55f
            val exit = 0.30f
            val accepted = lm != null && confidence >= if (state.visible) exit else enter
            if (accepted) {
                val nx = lm!!.x()
                val ny = lm.y()
                val nz = lm.z()
                val speed = hypot(nx - state.x, ny - state.y)
                // 0.18 while still, up to 0.72 during fast movement.
                val alpha = (0.18f + speed * 7.5f).coerceIn(0.18f, 0.72f)
                if (!state.visible || state.misses >= 5) {
                    state.x = nx
                    state.y = ny
                    state.z = nz
                } else {
                    // Suppress impossible one-frame teleports.
                    val boundedAlpha = if (speed > 0.34f) 0.12f else alpha
                    state.x += (nx - state.x) * boundedAlpha
                    state.y += (ny - state.y) * boundedAlpha
                    state.z += (nz - state.z) * boundedAlpha
                }
                state.confidence += (confidence - state.confidence) * 0.35f
                state.visible = true
                state.misses = 0
            } else {
                state.misses++
                state.confidence *= 0.86f
                if (state.misses >= 6 || state.confidence < 0.18f) state.visible = false
            }
            result += StableLandmark(
                x = state.x,
                y = state.y,
                z = state.z,
                confidence = if (personVisible && state.visible) state.confidence else 0f,
            )
        }
        return result
    }
}
