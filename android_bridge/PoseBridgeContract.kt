// Placeholder: wire MediaPipe Pose Landmarker Tasks here when packaging
// with `flet build apk`. Emit COCO-17 JSON via the contract in coco17_contract.py.
//
package com.jiandong.appdemo

object PoseBridgeContract {
    const val CHANNEL = "jiandong_ai/pose"
    val COCO17 = arrayOf(
        "nose", "leftEye", "rightEye", "leftEar", "rightEar",
        "leftShoulder", "rightShoulder", "leftElbow", "rightElbow",
        "leftWrist", "rightWrist", "leftHip", "rightHip",
        "leftKnee", "rightKnee", "leftAnkle", "rightAnkle"
    )
}
