// Contract mirror — runtime bridge lives in android_bridge/kotlin (CameraX + ORT).
package com.flet.jiandong_ai

object PoseBridgeContract {
    const val CHANNEL = "jiandong_ai/pose"
    const val FILES_DIR = "jiandong_pose"
    val COCO17 = arrayOf(
        "nose", "leftEye", "rightEye", "leftEar", "rightEar",
        "leftShoulder", "rightShoulder", "leftElbow", "rightElbow",
        "leftWrist", "rightWrist", "leftHip", "rightHip",
        "leftKnee", "rightKnee", "leftAnkle", "rightAnkle"
    )
}
