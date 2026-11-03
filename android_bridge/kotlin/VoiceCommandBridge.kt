package com.flet.jiandong_ai

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.util.Log
import androidx.core.content.ContextCompat
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.KeywordSpotter
import com.k2fsa.sherpa.onnx.KeywordSpotterConfig
import com.k2fsa.sherpa.onnx.OnlineModelConfig
import com.k2fsa.sherpa.onnx.OnlineTransducerModelConfig
import org.json.JSONObject
import java.io.File
import java.util.concurrent.atomic.AtomicInteger

/**
 * In-process half-duplex gate shared with TtsAnnouncer: while speech is queued
 * or playing (plus a short post-speech grace window), KWS input is discarded.
 * Lock-free so the TTS worker and audio-capture threads stay decoupled.
 */
object VoicePlaybackGate {
    private val activeSpeechCount = AtomicInteger(0)
    @Volatile private var lastSpeechEndedAt = 0L
    @Volatile var postSpeechGraceMs = DEFAULT_POST_SPEECH_GRACE_MS

    fun speechStarted() {
        activeSpeechCount.incrementAndGet()
    }

    fun speechEnded() {
        while (true) {
            val current = activeSpeechCount.get()
            if (current <= 0) return
            if (activeSpeechCount.compareAndSet(current, current - 1)) {
                if (current == 1) lastSpeechEndedAt = System.currentTimeMillis()
                return
            }
        }
    }

    fun shouldMuteCapture(now: Long = System.currentTimeMillis()): Boolean {
        if (activeSpeechCount.get() > 0) return true
        val endedAt = lastSpeechEndedAt
        return endedAt > 0L && now - endedAt < postSpeechGraceMs
    }

    private const val DEFAULT_POST_SPEECH_GRACE_MS = 500L
}

/**
 * sherpa-onnx keyword spotter for the accessibility (视障) mode.
 *
 * Gated by <bridgeDir>/voice_enabled.flag — when the flag is absent nothing
 * is initialized and no microphone is opened, so existing users see zero
 * change. PoseTrainingActivity writes training_active.flag while alive;
 * that flag decides whether a hit goes to event.json (training commands)
 * or voice_cmd.json (course-selection commands).
 */
class VoiceCommandBridge(private val activity: Activity) {
    private val tag = "VoiceCommandBridge"
    private val bridgeDir = File(activity.getExternalFilesDir(null) ?: activity.filesDir, "jiandong_pose")
    private val flagFile = File(bridgeDir, "voice_enabled.flag")
    private val trainingFlagFile = File(bridgeDir, "training_active.flag")
    private val assistantActiveFile = File(bridgeDir, AsrBridge.ASSISTANT_ACTIVE_FLAG)
    private val assistantWakeFile = File(bridgeDir, ASSISTANT_WAKE_FLAG)
    private val handler = android.os.Handler(android.os.Looper.getMainLooper())

    private var spotter: KeywordSpotter? = null
    private var audioRecord: AudioRecord? = null
    private var echoCanceler: AcousticEchoCanceler? = null
    @Volatile private var recording = false
    private var audioThread: Thread? = null
    private var voiceCmdSeq = 0L
    private var voiceEventSeq = VOICE_EVENT_SEQ_BASE
    private var lastHitKeyword = ""
    private var lastHitAt = 0L
    @Volatile private var kwsResumeAfter = 0L

    fun start() {
        handler.post(flagPoll)
    }

    fun hasRecordPermission(): Boolean =
        ContextCompat.checkSelfPermission(activity, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    fun onPermissionResult(granted: Boolean) {
        if (granted && flagFile.exists() && !assistantActiveFile.exists() && !recording) {
            startListening()
        }
    }

    fun stop() {
        handler.removeCallbacksAndMessages(null)
        stopListening()
    }

    private val flagPoll = object : Runnable {
        override fun run() {
            try {
                val enabled = flagFile.exists()
                val assistantActive = assistantActiveFile.exists()
                val mayListen = enabled && !assistantActive &&
                    System.currentTimeMillis() >= kwsResumeAfter
                if (mayListen && !recording && hasRecordPermission()) {
                    startListening()
                } else if ((!enabled || assistantActive) && recording) {
                    stopListening()
                }
            } catch (e: Exception) {
                Log.w(tag, "flagPoll: $e")
            }
            handler.postDelayed(this, FLAG_POLL_MS)
        }
    }

    private fun startListening() {
        if (recording) return
        if (spotter == null) {
            spotter = try {
                createSpotter()
            } catch (e: Exception) {
                Log.e(tag, "KWS init failed, voice commands disabled", e)
                return
            }
        }
        val bufferSize = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        ).coerceAtLeast(SAMPLE_RATE / 2)
        val record = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize,
            )
        } catch (e: Exception) {
            Log.e(tag, "AudioRecord init failed", e)
            return
        }
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            Log.e(tag, "AudioRecord not initialized")
            return
        }
        audioRecord = record
        if (AcousticEchoCanceler.isAvailable()) {
            try { echoCanceler = AcousticEchoCanceler.create(record.audioSessionId)?.apply { enabled = true } }
            catch (e: Exception) { Log.w(tag, "echo cancellation unavailable", e) }
        }
        recording = true
        audioThread = Thread({ audioLoop(record, bufferSize) }, "voice-kws").apply {
            isDaemon = true
            start()
        }
        Log.i(tag, "KWS listening started")
    }

    private fun stopListening() {
        recording = false
        audioThread?.join(500)
        audioThread = null
        try {
            audioRecord?.stop()
        } catch (_: Exception) {
        }
        audioRecord?.release()
        audioRecord = null
        echoCanceler?.release()
        echoCanceler = null
    }

    private fun audioLoop(record: AudioRecord, bufferSize: Int) {
        val kws = spotter ?: return
        val stream = kws.createStream()
        val shorts = ShortArray(bufferSize / 2)
        try {
            record.startRecording()
        } catch (e: Exception) {
            Log.e(tag, "startRecording failed", e)
            recording = false
            return
        }
        var captureMuted = false
        while (recording) {
            val read = record.read(shorts, 0, shorts.size)
            if (read <= 0) continue
            val speechPlaying = VoicePlaybackGate.shouldMuteCapture()
            val safetyListening = trainingFlagFile.exists()
            if (speechPlaying && !safetyListening) {
                if (!captureMuted) {
                    kws.reset(stream)
                    captureMuted = true
                }
                continue
            }
            if (captureMuted) {
                // Drop speech buffered just before the pause and any tail
                // captured during the post-speech grace window.
                kws.reset(stream)
                captureMuted = false
            }
            val samples = FloatArray(read) { shorts[it] / 32768.0f }
            stream.acceptWaveform(samples, SAMPLE_RATE)
            while (kws.isReady(stream)) {
                kws.decode(stream)
            }
            val keyword = kws.getResult(stream).keyword
            if (keyword.isNotBlank()) {
                kws.reset(stream)
                val word = keyword.trim()
                // 播报时仅保留暂停/结束，其他口令仍防止扬声器回声误触。
                if (!speechPlaying || word == "暂停训练" || word == "结束训练") onKeyword(word)
            }
        }
        stream.release()
    }

    private fun onKeyword(keyword: String) {
        val now = System.currentTimeMillis()
        if (keyword == lastHitKeyword && now - lastHitAt < KEYWORD_COOLDOWN_MS) return
        val inTraining = trainingFlagFile.exists()
        if (inTraining) {
            val type = TRAINING_COMMANDS[keyword] ?: return
            lastHitKeyword = keyword
            lastHitAt = now
            Log.i(tag, "training cmd: $keyword -> $type")
            // seq starts well above PoseTrainingActivity's own counter to
            // avoid colliding with native-emitted event seqs.
            val payload = JSONObject()
                .put("seq", ++voiceEventSeq)
                .put("type", type)
                .put("timestampMs", now)
            MediaPipePoseEngine.atomicWrite(File(bridgeDir, "training_control.json"), payload.toString())
        } else {
            if (keyword !in COURSE_KEYWORDS) return
            lastHitKeyword = keyword
            lastHitAt = now
            if (keyword == EXIT_ASSISTANT_KEYWORD) {
                assistantActiveFile.delete()
            }
            if (keyword == WAKE_ASSISTANT_KEYWORD) {
                kwsResumeAfter = now + KWS_WAKE_RELEASE_MS
                MediaPipePoseEngine.atomicWrite(
                    assistantWakeFile,
                    JSONObject().put("timestampMs", now).toString(),
                )
            }
            Log.i(tag, "course cmd: $keyword")
            val payload = JSONObject()
                .put("seq", ++voiceCmdSeq)
                .put("keyword", keyword)
            MediaPipePoseEngine.atomicWrite(File(bridgeDir, "voice_cmd.json"), payload.toString())
            if (keyword == WAKE_ASSISTANT_KEYWORD) {
                // AssistantSession will create assistant_active.flag; release the
                // microphone now so AsrBridge can take it without contention.
                handler.post { stopListening() }
            }
        }
    }

    private fun createSpotter(): KeywordSpotter {
        val config = KeywordSpotterConfig(
            featConfig = FeatureConfig(sampleRate = SAMPLE_RATE, featureDim = FEATURE_DIM),
            modelConfig = OnlineModelConfig(
                transducer = OnlineTransducerModelConfig(
                    encoder = "kws/encoder.onnx",
                    decoder = "kws/decoder.onnx",
                    joiner = "kws/joiner.onnx",
                ),
                tokens = "kws/tokens.txt",
                numThreads = KWS_THREADS,
                provider = "cpu",
                debug = false,
            ),
            keywordsFile = "kws/keywords.txt",
            maxActivePaths = MAX_ACTIVE_PATHS,
            keywordsScore = KEYWORDS_SCORE,
            keywordsThreshold = KEYWORDS_THRESHOLD,
            numTrailingBlanks = NUM_TRAILING_BLANKS,
        )
        return KeywordSpotter(assetManager = activity.assets, config = config)
    }

    companion object {
        const val FLAG_NAME = "voice_enabled.flag"
        const val TRAINING_FLAG_NAME = "training_active.flag"
        const val ASSISTANT_WAKE_FLAG = "assistant_wake.flag"

        private const val SAMPLE_RATE = 16000
        private const val FEATURE_DIM = 80
        private const val FLAG_POLL_MS = 200L
        private const val KEYWORD_COOLDOWN_MS = 1500L
        private const val KWS_WAKE_RELEASE_MS = 800L
        private const val VOICE_EVENT_SEQ_BASE = 50000L
        private const val WAKE_ASSISTANT_KEYWORD = "小健小健"
        private const val EXIT_ASSISTANT_KEYWORD = "退出助手"

        // Per-keyword tuning knobs (also adjustable per word in keywords.txt).
        private const val KEYWORDS_THRESHOLD = 0.25f
        private const val KEYWORDS_SCORE = 1.5f
        private const val MAX_ACTIVE_PATHS = 4
        private const val NUM_TRAILING_BLANKS = 1
        private const val KWS_THREADS = 1

        // 训练口令 → emitEvent 同款事件 type（与 Python voice_session 一致）。
        private val TRAINING_COMMANDS = mapOf(
            "开始训练" to "begin",
            "暂停训练" to "pause",
            "继续训练" to "resume",
            "结束训练" to "stop",
            "帮助" to "voice_help",
            "再说一遍" to "voice_repeat",
            "下一个动作" to "action_next",
            "上一个动作" to "action_prev",
        )

        // 训练外口令（登录页消费「登录/帮助」，助手消费唤醒词，选课会话消费选课词）。
        private val COURSE_KEYWORDS = setOf(
            "小健小健", "退出助手", "登录", "帮助",
            "腿部", "核心", "上肢", "背部", "全身", "确认", "换一个", "再说一遍",
        )
    }
}
