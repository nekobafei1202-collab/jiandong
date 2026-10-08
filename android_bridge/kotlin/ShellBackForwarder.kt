package com.flet.jiandong_ai

import android.content.Context
import android.os.SystemClock
import org.json.JSONObject
import java.io.File

/** Sync bridge: MainActivity back → Python shell handler → consumed or default exit. */
object ShellBackForwarder {
    private fun dir(ctx: Context): File =
        File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "jiandong_pose").apply { mkdirs() }

    /** @return true if Python consumed the back press (stay in app). */
    fun requestConsume(ctx: Context): Boolean {
        val root = dir(ctx)
        val req = File(root, "shell_back_req.json")
        val ack = File(root, "shell_back_ack.json")
        ack.delete()
        val seq = System.currentTimeMillis()
        req.writeText(JSONObject().put("seq", seq).toString())
        val deadline = SystemClock.uptimeMillis() + 400
        while (SystemClock.uptimeMillis() < deadline) {
            if (ack.exists()) {
                val consumed = try {
                    JSONObject(ack.readText()).optBoolean("consumed", false)
                } catch (_: Exception) {
                    false
                }
                ack.delete()
                req.delete()
                return consumed
            }
            Thread.sleep(8)
        }
        req.delete()
        return false
    }
}
