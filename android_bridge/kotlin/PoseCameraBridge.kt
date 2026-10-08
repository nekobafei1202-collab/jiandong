package com.flet.jiandong_ai

import android.app.Activity
import android.content.Intent
import android.util.Log
import java.io.File

/** File-command controller that launches the native camera activity. */
class PoseCameraBridge(private val activity: Activity) {
    private val tag = "PoseCameraBridge"
    private val bridgeDir = File(activity.getExternalFilesDir(null) ?: activity.filesDir, "jiandong_pose")
    private val legacyDir = File(activity.filesDir, "jiandong_pose")
    private var lastCommand = ""
    private var lastCommandAt = 0L

    init {
        ensureDir()
        Log.i(tag, "bridgeDir=${bridgeDir.absolutePath}")
    }

    fun ensureDir() {
        bridgeDir.mkdirs()
        legacyDir.mkdirs()
    }

    fun pollCommands() {
        ensureDir()
        for (dir in listOf(bridgeDir, legacyDir)) {
            val file = File(dir, "cmd.txt")
            if (!file.exists()) continue
            val command = file.readText().trim()
            if (command.isEmpty()) continue
            file.writeText("")
            File(bridgeDir, "cmd.txt").writeText("")
            File(legacyDir, "cmd.txt").writeText("")
            val now = System.currentTimeMillis()
            if (command == lastCommand && now - lastCommandAt < 500) return
            lastCommand = command
            lastCommandAt = now
            handle(command)
            return
        }
    }

    private fun handle(command: String) {
        Log.i(tag, "cmd=$command")
        val parts = command.split('\t')
        when (parts.firstOrNull()) {
            "start_front", "start_back", "resume_front", "resume_back",
            "preview_front", "preview_back",
            -> {
                val front = parts[0].endsWith("front")
                val action = parts.getOrNull(1).orEmpty().ifBlank { "深蹲" }
                // Same task as MainActivity — never NEW_TASK / NEW_DOCUMENT.
                activity.startActivity(
                    Intent(activity, PoseTrainingActivity::class.java)
                        .putExtra(PoseTrainingActivity.EXTRA_FRONT, front)
                        .putExtra(PoseTrainingActivity.EXTRA_ACTION, action)
                )
            }
            "stop" -> Unit
        }
    }

    fun stop() = Unit
}
