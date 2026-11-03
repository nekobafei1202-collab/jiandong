package com.flet.jiandong_ai

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import androidx.core.content.ContextCompat
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.OfflineModelConfig
import com.k2fsa.sherpa.onnx.OfflineRecognizer
import com.k2fsa.sherpa.onnx.OfflineRecognizerConfig
import com.k2fsa.sherpa.onnx.OfflineSenseVoiceModelConfig
import com.k2fsa.sherpa.onnx.SileroVadModelConfig
import com.k2fsa.sherpa.onnx.Vad
import com.k2fsa.sherpa.onnx.VadModelConfig
import org.json.JSONObject
import java.io.File

/**
 * SenseVoice free-form ASR bridge for the “小健” assistant.
 *
 * The 230MB recognizer and VAD are lazily loaded only while
 * assistant_active.flag exists, and cached until the bridge stops. The flag also
 * provides the microphone mutex with VoiceCommandBridge: KWS releases the mic
 * on wake, ASR starts only while the assistant flag is present.
 */
class AsrBridge(private val activity: Activity) {
    private val tag = "AsrBridge"
    private val bridgeDir = File(activity.getExternalFilesDir(null) ?: activity.filesDir, "jiandong_pose")
    private val voiceFlagFile = File(bridgeDir, VoiceCommandBridge.FLAG_NAME)
    private val assistantFlagFile = File(bridgeDir, ASSISTANT_ACTIVE_FLAG)
    private val trainingFlagFile = File(bridgeDir, VoiceCommandBridge.TRAINING_FLAG_NAME)
    private val handler = android.os.Handler(android.os.Looper.getMainLooper())

    private val lifecycleLock = Any()
    private var workerThread: Thread? = null
    private var recognizer: OfflineRecognizer? = null
    private var vad: Vad? = null
    private var audioRecord: AudioRecord? = null
    @Volatile private var active = false
    @Volatile private var loading = false
    @Volatile private var stopRequested = false
    @Volatile private var initFailed = false
    private var resultSeq = 0L
    @Volatile private var disposed = false
    private val readyFile = File(bridgeDir, "asr_ready.flag")

    fun start() {
        handler.post(flagPoll)
    }

    fun stop() {
        handler.removeCallbacksAndMessages(null)
        disposed = true
        stopListening()
        synchronized(lifecycleLock) {
            if (workerThread?.isAlive != true) {
                recognizer?.release()
                recognizer = null
                vad?.release()
                vad = null
            }
        }
    }

    fun onPermissionResult(granted: Boolean) {
        if (granted && shouldRun() && !active && !loading) startListening()
    }

    private val flagPoll = object : Runnable {
        override fun run() {
            try {
                val enabled = shouldRun()
                if (enabled && !active && !loading && !initFailed && hasRecordPermission()) {
                    startListening()
                } else if (!enabled && (active || loading)) {
                    stopListening()
                }
                if (!enabled) initFailed = false
            } catch (e: Exception) {
                Log.w(tag, "flagPoll: $e")
            }
            handler.postDelayed(this, FLAG_POLL_MS)
        }
    }

    private fun shouldRun(): Boolean =
        voiceFlagFile.exists() && assistantFlagFile.exists() && !trainingFlagFile.exists()

    private fun hasRecordPermission(): Boolean =
        ContextCompat.checkSelfPermission(activity, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    private fun startListening() {
        if (disposed || active || loading || workerThread?.isAlive == true) return
        stopRequested = false
        loading = true
        workerThread = Thread({ runWorker() }, "assistant-asr").apply {
            isDaemon = true
            start()
        }
    }

    private fun stopListening() {
        stopRequested = true
        active = false
        val thread = workerThread
        if (thread != null && thread.isAlive() && thread !== Thread.currentThread()) {
            thread.join(3000)
        }
        readyFile.delete()
        if (thread?.isAlive != true) workerThread = null
    }

    private fun runWorker() {
        var localRecognizer: OfflineRecognizer? = null
        var localVad: Vad? = null
        var localRecord: AudioRecord? = null
        try {
            localRecognizer = recognizer ?: createRecognizer().also { recognizer = it }
            localVad = vad ?: createVad().also { vad = it }
            localVad.reset()
            val bufferSize = AudioRecord.getMinBufferSize(
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
            ).coerceAtLeast(SAMPLE_RATE / 2)
            localRecord = AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize,
            )
            if (localRecord.state != AudioRecord.STATE_INITIALIZED) {
                throw IllegalStateException("AudioRecord not initialized")
            }
            synchronized(lifecycleLock) {
                if (stopRequested) return
                recognizer = localRecognizer
                vad = localVad
                audioRecord = localRecord
                active = true
            }
            Log.i(tag, "SenseVoice ASR listening started")
            audioLoop(localRecord, localVad, localRecognizer, bufferSize)
        } catch (e: Exception) {
            if (!stopRequested) {
                initFailed = true
                Log.e(tag, "ASR init/listen failed", e)
            }
        } finally {
            active = false
            loading = false
            synchronized(lifecycleLock) {
                if (audioRecord === localRecord) audioRecord = null

            }
            try {
                localRecord?.stop()
            } catch (_: Exception) {
            }
            localRecord?.release()
            readyFile.delete()
            if (disposed) {
                synchronized(lifecycleLock) {
                    recognizer?.release()
                    recognizer = null
                    vad?.release()
                    vad = null
                }
            }
        }
    }

    private fun audioLoop(
        record: AudioRecord,
        vad: Vad,
        recognizer: OfflineRecognizer,
        bufferSize: Int,
    ) {
        val shorts = ShortArray(bufferSize / 2)
        try {
            record.startRecording()
        } catch (e: Exception) {
            Log.e(tag, "startRecording failed", e)
            return
        }
        MediaPipePoseEngine.atomicWrite(readyFile, "1")
        var captureMuted = false
        while (active && !stopRequested) {
            val read = record.read(shorts, 0, shorts.size)
            if (read <= 0) continue
            if (VoicePlaybackGate.shouldMuteCapture() || File(bridgeDir, "assistant_thinking.flag").exists()) {
                if (!captureMuted) {
                    vad.reset()
                    captureMuted = true
                }
                continue
            }
            if (captureMuted) {
                vad.reset()
                captureMuted = false
            }
            val samples = FloatArray(read) { shorts[it] / 32768.0f }
            vad.acceptWaveform(samples)
            while (!vad.empty()) {
                val segment = vad.front()
                vad.pop()
                decodeSegment(recognizer, segment.samples)
            }
        }
    }

    private fun decodeSegment(recognizer: OfflineRecognizer, samples: FloatArray) {
        if (samples.isEmpty()) return
        val stream = recognizer.createStream()
        try {
            stream.acceptWaveform(samples, SAMPLE_RATE)
            recognizer.decode(stream)
            val text = recognizer.getResult(stream).text.trim()
            if (text.isNotEmpty()) {
                val payload = JSONObject()
                    .put("seq", ++resultSeq)
                    .put("text", text)
                MediaPipePoseEngine.atomicWrite(File(bridgeDir, ASR_RESULT_FILE), payload.toString())
                Log.i(tag, "asr: $text")
            }
        } catch (e: Exception) {
            Log.w(tag, "decode failed: $e")
        } finally {
            stream.release()
        }
    }

    private fun createRecognizer(): OfflineRecognizer {
        val config = OfflineRecognizerConfig(
            featConfig = FeatureConfig(sampleRate = SAMPLE_RATE, featureDim = FEATURE_DIM),
            modelConfig = OfflineModelConfig(
                senseVoice = OfflineSenseVoiceModelConfig(
                    model = "asr/model.onnx",
                    language = "zh",
                    useInverseTextNormalization = true,
                ),
                tokens = "asr/tokens.txt",
                numThreads = ASR_THREADS,
                provider = "cpu",
                debug = false,
            ),
        )
        return OfflineRecognizer(assetManager = activity.assets, config = config)
    }

    private fun createVad(): Vad {
        val config = VadModelConfig(
            sileroVadModelConfig = SileroVadModelConfig(
                model = "asr/silero_vad.onnx",
                threshold = VAD_THRESHOLD,
                minSpeechDuration = VAD_MIN_SPEECH_SECONDS,
                minSilenceDuration = VAD_MIN_SILENCE_SECONDS,
                maxSpeechDuration = VAD_MAX_SPEECH_SECONDS,
                windowSize = VAD_WINDOW_SIZE,
            ),
            sampleRate = SAMPLE_RATE,
            numThreads = 1,
            provider = "cpu",
            debug = false,
        )
        return Vad(assetManager = activity.assets, config = config)
    }

    companion object {
        const val ASSISTANT_ACTIVE_FLAG = "assistant_active.flag"
        const val ASR_RESULT_FILE = "asr_result.json"

        private const val SAMPLE_RATE = 16000
        private const val FEATURE_DIM = 80
        private const val FLAG_POLL_MS = 200L
        private const val ASR_THREADS = 2
        private const val VAD_THRESHOLD = 0.5f
        private const val VAD_MIN_SPEECH_SECONDS = 0.25f
        private const val VAD_MIN_SILENCE_SECONDS = 0.6f
        private const val VAD_MAX_SPEECH_SECONDS = 12.0f
        private const val VAD_WINDOW_SIZE = 512
    }
}
