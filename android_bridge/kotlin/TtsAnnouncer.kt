package com.flet.jiandong_ai

import android.app.Activity
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import com.k2fsa.sherpa.onnx.OfflineTts
import com.k2fsa.sherpa.onnx.OfflineTtsConfig
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig
import org.json.JSONObject
import java.io.File
import java.util.Locale
import java.util.concurrent.CountDownLatch
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

/**
 * Speaks accessibility text for the voice (视障) mode.
 *
 * voice_enabled.flag is the master switch. Each source has its own scene gate:
 *  - tts.json  (seq + text) — only while voice_session_active.flag exists.
 *  - hud.json  — only while training_active.flag exists; announces title /
 *    reps / rest / summaryText changes; subtitle (纠错) announcements are
 *    de-duplicated with a 5s cooldown and queued so they never cut off counting.
 * Channel activation captures the current file as a seen baseline, and files
 * last modified before this app process started are always ignored.
 *
 * Engine cascade: packaged Serena recordings → system TextToSpeech (中文) → sherpa-onnx OfflineTts
 * (vits-aishell3 from assets/tts/, for ROMs without any TTS engine) →
 * vibration cues.
 */
class TtsAnnouncer(private val activity: Activity) : TextToSpeech.OnInitListener {
    private val tag = "TtsAnnouncer"
    private val bridgeDir = File(activity.getExternalFilesDir(null) ?: activity.filesDir, "jiandong_pose")
    private val flagFile = File(bridgeDir, "voice_enabled.flag")
    private val voiceSessionFlagFile = File(bridgeDir, "voice_session_active.flag")
    private val trainingFlagFile = File(bridgeDir, VoiceCommandBridge.TRAINING_FLAG_NAME)
    private val processStartedAt = System.currentTimeMillis()
    private val handler = Handler(Looper.getMainLooper())

    private var tts: TextToSpeech? = null
    @Volatile private var ttsReady = false
    @Volatile private var chineseOk = false

    // sherpa-onnx offline fallback (lazily loaded on a worker thread).
    @Volatile private var sherpaTts: OfflineTts? = null
    @Volatile private var sherpaFailed = false
    @Volatile private var closed = false
    private val sherpaLock = Any()
    private val sherpaQueue = LinkedBlockingQueue<SherpaJob>()
    @Volatile private var sherpaWorker: Thread? = null
    private val systemSpeechPending = AtomicInteger(0)
    private val sherpaSpeechPending = AtomicInteger(0)

    @Volatile private var playbackGeneration = 0L
    private class SherpaJob(val text: String, val recording: String? = null, val generation: Long)
    private val serenaPrompts = SerenaPrompts(activity.assets)

    private var polling = false
    private var ttsChannelActive = false
    private var hudChannelActive = false
    private var lastTtsSeq = -1L
    private var lastTtsStamp = 0L
    private var lastHudStamp = 0L
    private var lastTitle = ""
    private var lastReps = -1
    private var lastResting = false
    private var lastRestSeconds = -1
    private var lastSummary = ""
    private var lastSubtitle = ""
    private var lastSubtitleAt = 0L
    private var lastTrainingSpeechSeq = -1L
    private var trainingSpeechPriority = false

    fun start() {
        tts = TextToSpeech(activity.applicationContext, this).apply {
            setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) = Unit

                override fun onDone(utteranceId: String?) {
                    systemSpeechFinished()
                }

                @Suppress("DEPRECATION", "OVERRIDE_DEPRECATION")
                override fun onError(utteranceId: String?) {
                    systemSpeechFinished()
                }
            })
        }
        handler.post(flagPoll)
    }

    fun stop() {
        closed = true
        handler.removeCallbacksAndMessages(null)
        polling = false
        playbackGeneration++
        tts?.stop()
        cancelSystemSpeech()
        tts?.shutdown()
        tts = null
        ttsReady = false
        discardSherpaQueue()
        sherpaWorker?.interrupt()
        sherpaWorker = null
        synchronized(sherpaLock) {
            sherpaTts?.release()
            sherpaTts = null
        }
    }

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) {
            Log.w(tag, "system TTS init failed; trying sherpa-onnx offline TTS")
            ttsReady = false
            ensureSherpaAsync()
            return
        }
        val engine = tts ?: return
        val availability = engine.setLanguage(Locale.CHINESE)
        val localChineseVoice = engine.voices?.filter {
            it.locale.language == Locale.CHINESE.language && !it.isNetworkConnectionRequired
        }?.sortedBy { it.name }?.firstOrNull()
        chineseOk = availability != TextToSpeech.LANG_MISSING_DATA &&
            availability != TextToSpeech.LANG_NOT_SUPPORTED && localChineseVoice != null
        if (localChineseVoice != null && engine.setVoice(localChineseVoice) == TextToSpeech.ERROR) {
            chineseOk = false
        }
        if (chineseOk && engine.setSpeechRate(SYSTEM_SPEECH_RATE) == TextToSpeech.ERROR) {
            Log.w(tag, "system TTS rejected speech rate $SYSTEM_SPEECH_RATE")
        }
        ttsReady = true
        if (!chineseOk) {
            Log.w(tag, "Chinese TTS data missing; trying sherpa-onnx offline TTS")
            ttsReady = false
            ensureSherpaAsync()
        }
    }

    // ---- sherpa-onnx OfflineTts fallback ----

    private fun ensureSherpaAsync() {
        if (closed) return
        if (sherpaWorker != null) return
        val worker = Thread({
            while (!closed) {
                val job = try {
                    sherpaQueue.take()
                } catch (_: InterruptedException) {
                    return@Thread
                }
                try {
                    if (job.generation != playbackGeneration) continue
                    if (job.recording != null) {
                        try {
                            val audio = serenaPrompts.read(job.recording)
                            playPcm(audio.samples, audio.sampleRate, job.generation)
                        } catch (e: Exception) {
                            Log.w(tag, "Serena recording unavailable; using local TTS", e)
                            ensureOfflineEngine()
                            speakWithSherpa(job.text, job.generation)
                        }
                    } else if (job.text.isNotEmpty()) {
                        ensureOfflineEngine()
                        speakWithSherpa(job.text, job.generation)
                    }
                } catch (e: Exception) {
                    Log.w(tag, "Local speech playback failed", e)
                    vibrate()
                } finally {
                    sherpaSpeechFinished()
                }
            }
        }, "sherpa-tts").apply { isDaemon = true }
        sherpaWorker = worker
        worker.start()
    }

    private fun ensureOfflineEngine() {
            synchronized(sherpaLock) {
                if (!closed && sherpaTts == null && !sherpaFailed) {
                    sherpaTts = try {
                        createOfflineTts().also {
                            Log.i(tag, "sherpa TTS ready: rate=${it.sampleRate()} speakers=${it.numSpeakers()}")
                        }
                    } catch (e: Exception) {
                        Log.e(tag, "sherpa TTS init failed; falling back to vibration", e)
                        sherpaFailed = true
                        null
                    }
                }
            }
    }

    private fun createOfflineTts(): OfflineTts {
        val ruleFsts = listOf("phone.fst", "date.fst", "number.fst", "new_heteronym.fst")
            .filter { assetExists("tts/$it") }
            .joinToString(",") { "tts/$it" }
        val config = OfflineTtsConfig(
            model = OfflineTtsModelConfig(
                vits = OfflineTtsVitsModelConfig(
                    model = "tts/model.onnx",
                    lexicon = "tts/lexicon.txt",
                    tokens = "tts/tokens.txt",
                    dataDir = "",
                    dictDir = "",
                    noiseScale = 0.667f,
                    noiseScaleW = 0.8f,
                    lengthScale = 1.0f,
                ),
                numThreads = 2,
                provider = "cpu",
                debug = false,
            ),
            ruleFsts = ruleFsts,
            ruleFars = "",
            maxNumSentences = 2,
            silenceScale = 0.2f,
        )
        return OfflineTts(assetManager = activity.assets, config = config)
    }

    private fun assetExists(path: String): Boolean = try {
        activity.assets.open(path).close()
        true
    } catch (_: Exception) {
        false
    }

    private fun speakWithSherpa(text: String, generation: Long) {
        val audio = try {
            synchronized(sherpaLock) {
                val engine = sherpaTts ?: run { vibrate(); return }
                if (closed || generation != playbackGeneration) return
                engine.generate(text, sid = SHERPA_SPEAKER_ID, speed = SHERPA_SPEED)
            }
        } catch (e: Exception) {
            Log.w(tag, "sherpa generate failed: $e")
            vibrate()
            return
        }
        playPcm(audio.samples, audio.sampleRate, generation)
    }

    private fun playPcm(samples: FloatArray, sampleRate: Int, generation: Long) {
        if (sampleRate <= 0 || generation != playbackGeneration) return
        val speechPcm = ShortArray(samples.size) { i ->
            (samples[i].coerceIn(-1f, 1f) * 32767f).toInt().toShort()
        }
        val tailFrames = sampleRate * PCM_TAIL_SILENCE_MS / 1000
        val pcm = ShortArray(speechPcm.size + tailFrames)
        speechPcm.copyInto(pcm)
        val totalFrames = pcm.size
        val minBuffer = AudioTrack.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        val playbackDone = CountDownLatch(1)
        val track = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setSampleRate(sampleRate)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setBufferSizeInBytes(maxOf(minBuffer, totalFrames * 2))
            .setTransferMode(AudioTrack.MODE_STATIC)
            .build()
        try {
            track.setNotificationMarkerPosition(totalFrames)
            track.setPlaybackPositionUpdateListener(
                object : AudioTrack.OnPlaybackPositionUpdateListener {
                    override fun onMarkerReached(track: AudioTrack?) {
                        playbackDone.countDown()
                    }

                    override fun onPeriodicNotification(track: AudioTrack?) = Unit
                },
                handler,
            )
            var offset = 0
            while (offset < totalFrames) {
                val written = track.write(pcm, offset, totalFrames - offset)
                if (written <= 0) {
                    throw IllegalStateException("AudioTrack write failed: $written")
                }
                offset += written
            }
            track.play()
            val expectedMs = totalFrames * 1000L / sampleRate
            val playbackDeadline = System.currentTimeMillis() + expectedMs + PLAYBACK_COMPLETION_GUARD_MS
            var completed = false
            while (generation == playbackGeneration && System.currentTimeMillis() < playbackDeadline) {
                if (playbackDone.await(50, TimeUnit.MILLISECONDS)) { completed = true; break }
            }
            if (generation != playbackGeneration) return
            if (!completed) {
                Log.w(tag, "playback marker timed out; waiting for playhead")
                val deadline = System.currentTimeMillis() + PLAYBACK_COMPLETION_GUARD_MS
                while (track.playbackHeadPosition < totalFrames &&
                    generation == playbackGeneration && System.currentTimeMillis() < deadline
                ) {
                    Thread.sleep(20)
                }
                if (track.playbackHeadPosition < totalFrames) {
                    Log.w(tag, "playback playhead incomplete: ${track.playbackHeadPosition}/$totalFrames")
                }
            }
        } catch (e: InterruptedException) {
            Thread.currentThread().interrupt()
            Log.w(tag, "AudioTrack playback interrupted")
        } catch (e: Exception) {
            Log.w(tag, "AudioTrack playback failed: $e")
        } finally {
            try {
                track.stop()
            } catch (_: Exception) {
            }
            track.release()
        }
    }

    // ---- polling ----

    private val flagPoll = object : Runnable {
        override fun run() {
            val enabled = flagFile.exists()
            if (enabled && !polling) {
                polling = true
                ttsChannelActive = false
                hudChannelActive = false
                resetTtsState()
                resetHudState()
                handler.post(fastPoll)
            } else if (!enabled && polling) {
                polling = false
                playbackGeneration++
                ttsChannelActive = false
                hudChannelActive = false
                handler.removeCallbacks(fastPoll)
                tts?.stop()
                cancelSystemSpeech()
                discardSherpaQueue()
            }
            handler.postDelayed(this, FLAG_POLL_MS)
        }
    }

    private val fastPoll = object : Runnable {
        override fun run() {
            if (!polling) return
            try {
                syncChannels()
                if (ttsChannelActive) pollTtsJson()
                if (hudChannelActive) pollHudJson()
                pollTrainingSpeech()
            } catch (_: Exception) {
            }
            try {
                MediaPipePoseEngine.atomicWrite(File(bridgeDir, "tts_status.json"),
                    JSONObject().put("seq", lastTtsSeq)
                        .put("busy", VoicePlaybackGate.shouldMuteCapture()).toString())
            } catch (_: Exception) { }
            handler.postDelayed(this, FAST_POLL_MS)
        }
    }

    private fun syncChannels() {
        val ttsActive = voiceSessionFlagFile.exists()
        if (ttsActive && !ttsChannelActive) {
            ttsChannelActive = true
            primeTtsBaseline(channelCutoff(voiceSessionFlagFile))
        } else if (!ttsActive && ttsChannelActive) {
            ttsChannelActive = false
            resetTtsState()
        }

        val hudActive = trainingFlagFile.exists()
        if (hudActive && !hudChannelActive) {
            hudChannelActive = true
            primeHudBaseline(channelCutoff(trainingFlagFile))
        } else if (!hudActive && hudChannelActive) {
            hudChannelActive = false
            resetHudState()
        }
    }

    private fun channelCutoff(flag: File): Long =
        maxOf(processStartedAt, flag.lastModified())

    private fun primeTtsBaseline(cutoff: Long) {
        resetTtsState()
        val file = File(bridgeDir, "tts.json")
        if (!file.exists() || file.lastModified() > cutoff) return
        lastTtsStamp = file.lastModified()
        try {
            lastTtsSeq = JSONObject(file.readText()).optLong("seq", -1L)
        } catch (_: Exception) {
        }
    }

    private fun primeHudBaseline(cutoff: Long) {
        resetHudState()
        val file = File(bridgeDir, "hud.json")
        if (!file.exists() || file.lastModified() > cutoff) return
        lastHudStamp = file.lastModified()
        val hud = try {
            JSONObject(file.readText())
        } catch (_: Exception) {
            return
        }
        lastTitle = hud.optString("title", "").trim()
        lastReps = hud.optInt("reps", -1)
        lastResting = hud.optBoolean("resting", false)
        lastRestSeconds = hud.optInt("restSeconds", -1)
        lastSummary = hud.optString("summaryText", "").trim()
        lastSubtitle = hud.optString("subtitle", "").trim()
    }

    private fun pollTtsJson() {
        val file = File(bridgeDir, "tts.json")
        if (!file.exists() || file.lastModified() < processStartedAt) return
        val stamp = file.lastModified()
        if (stamp == lastTtsStamp) return
        val payload = try {
            JSONObject(file.readText())
        } catch (_: Exception) {
            return
        }
        val seq = payload.optLong("seq", -1L)
        if (seq <= lastTtsSeq) {
            lastTtsStamp = stamp
            return
        }
        lastTtsSeq = seq
        lastTtsStamp = stamp
        val text = payload.optString("text", "").trim()
        if (text.isNotEmpty()) speak(text, queueMode = TextToSpeech.QUEUE_FLUSH)
    }

    private fun pollTrainingSpeech() {
        val file = File(bridgeDir, "training_speech.json")
        if (!file.exists() || file.lastModified() < processStartedAt) return
        val message = JSONObject(file.readText())
        val seq = message.optLong("seq", -1L)
        if (seq == lastTrainingSpeechSeq) return
        lastTrainingSpeechSeq = seq
        val text = message.optString("text").trim()
        if (text.isNotEmpty()) {
            trainingSpeechPriority = true
            Log.i(tag, "training announcement: $text")
            speak(text, TextToSpeech.QUEUE_FLUSH)
        }
    }

    private fun pollHudJson() {
        if (trainingSpeechPriority && VoicePlaybackGate.shouldMuteCapture()) return
        trainingSpeechPriority = false
        val file = File(bridgeDir, "hud.json")
        if (!file.exists() || file.lastModified() < processStartedAt) return
        if (file.lastModified() == lastHudStamp) return
        lastHudStamp = file.lastModified()
        val hud = try {
            JSONObject(file.readText())
        } catch (_: Exception) {
            return
        }

        val summary = hud.optString("summaryText", "").trim()
        if (summary.isNotEmpty() && summary != lastSummary) {
            lastSummary = summary
            speak(summary, queueMode = TextToSpeech.QUEUE_FLUSH)
            return
        }

        val resting = hud.optBoolean("resting", false)
        if (resting != lastResting) {
            lastResting = resting
            lastRestSeconds = -1
            if (resting) {
                speak(hud.optString("restLabel", "组间休息").ifBlank { "组间休息" },
                    queueMode = TextToSpeech.QUEUE_FLUSH)
            }
        } else if (resting) {
            val seconds = hud.optInt("restSeconds", -1)
            if (seconds != lastRestSeconds && (seconds <= 3 || seconds % 10 == 0) && seconds > 0) {
                lastRestSeconds = seconds
                speak("$seconds", queueMode = TextToSpeech.QUEUE_ADD)
            }
        }

        val title = hud.optString("title", "").trim()
        if (title.isNotEmpty() && title != lastTitle) {
            lastTitle = title
            speak(title, queueMode = TextToSpeech.QUEUE_FLUSH)
        }

        if (resting) return

        val reps = hud.optInt("reps", -1)
        if (reps >= 0 && reps != lastReps) {
            val announced = lastReps >= 0 && reps > lastReps
            lastReps = reps
            if (announced && reps > 0) {
                val unit = hud.optString("unit", "次").ifBlank { "次" }
                speak("$reps $unit", queueMode = TextToSpeech.QUEUE_FLUSH)
            }
        }

        val subtitle = hud.optString("subtitle", "").trim()
        val now = System.currentTimeMillis()
        if (subtitle.isNotEmpty() && subtitle != lastSubtitle &&
            now - lastSubtitleAt >= SUBTITLE_COOLDOWN_MS
        ) {
            lastSubtitle = subtitle
            lastSubtitleAt = now
            speak(subtitle, queueMode = TextToSpeech.QUEUE_ADD)
        }
    }

    // ---- output ----

    private fun decrementPending(counter: AtomicInteger): Boolean {
        while (true) {
            val current = counter.get()
            if (current <= 0) return false
            if (counter.compareAndSet(current, current - 1)) return true
        }
    }

    private fun systemSpeechQueued() {
        systemSpeechPending.incrementAndGet()
        VoicePlaybackGate.speechStarted()
    }

    private fun systemSpeechFinished() {
        if (decrementPending(systemSpeechPending)) VoicePlaybackGate.speechEnded()
    }

    private fun cancelSystemSpeech() {
        val pending = systemSpeechPending.getAndSet(0)
        repeat(pending) { VoicePlaybackGate.speechEnded() }
    }

    private fun sherpaSpeechQueued() {
        sherpaSpeechPending.incrementAndGet()
        VoicePlaybackGate.speechStarted()
    }

    private fun sherpaSpeechFinished() {
        if (decrementPending(sherpaSpeechPending)) VoicePlaybackGate.speechEnded()
    }

    private fun discardSherpaQueue() {
        val discarded = mutableListOf<SherpaJob>()
        sherpaQueue.drainTo(discarded)
        repeat(discarded.size) { sherpaSpeechFinished() }
    }

    private fun speak(text: String, queueMode: Int) {
        if (queueMode == TextToSpeech.QUEUE_FLUSH) playbackGeneration++
        val recording = serenaPrompts.pathFor(text)
        if (recording != null) {
            if (queueMode == TextToSpeech.QUEUE_FLUSH) {
                tts?.stop()
                cancelSystemSpeech()
                discardSherpaQueue()
            }
            ensureSherpaAsync()
            sherpaSpeechQueued()
            sherpaQueue.offer(SherpaJob(text, recording, playbackGeneration))
            return
        }
        val systemTts = tts
        if (ttsReady && chineseOk && systemTts != null) {
            if (queueMode == TextToSpeech.QUEUE_FLUSH) cancelSystemSpeech()
            systemSpeechQueued()
            val status = systemTts.speak(text, queueMode, null, "jd-${System.nanoTime()}")
            if (status == TextToSpeech.SUCCESS) return
            systemSpeechFinished()
            Log.w(tag, "system TTS speak failed: $status")
        }
        if (!sherpaFailed) {
            ensureSherpaAsync()
            if (queueMode == TextToSpeech.QUEUE_FLUSH) discardSherpaQueue()
            // Count queued-but-not-yet-played jobs as speech so QUEUE_ADD keeps
            // the mic muted until the final queued utterance has finished.
            sherpaSpeechQueued()
            sherpaQueue.offer(SherpaJob(text, generation = playbackGeneration))
            return
        }
        // Vibration is not speech: no playback gate here.
        vibrate()
    }

    private fun vibrate() {
        try {
            val vibrator: Vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val manager = activity.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
                manager?.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                activity.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
            } ?: return
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator.vibrate(VibrationEffect.createOneShot(200, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                vibrator.vibrate(200)
            }
        } catch (_: Exception) {
        }
    }

    private fun resetTtsState() {
        lastTtsSeq = -1L
        lastTtsStamp = 0L
    }

    private fun resetHudState() {
        lastHudStamp = 0L
        lastTitle = ""
        lastReps = -1
        lastResting = false
        lastRestSeconds = -1
        lastSummary = ""
        lastSubtitle = ""
        lastSubtitleAt = 0L
    }

    companion object {
        private const val FLAG_POLL_MS = 1000L
        private const val FAST_POLL_MS = 100L
        private const val SUBTITLE_COOLDOWN_MS = 5000L
        private const val SYSTEM_SPEECH_RATE = 0.9f
        private const val PCM_TAIL_SILENCE_MS = 250
        private const val PLAYBACK_COMPLETION_GUARD_MS = 2000L
        // vits-zh-aishell3 has 174 speakers (sid 0..173); 66 is a neutral female voice.
        private const val SHERPA_SPEAKER_ID = 66
        private const val SHERPA_SPEED = 0.9f
    }
}
