package com.flet.jiandong_ai

import android.content.res.AssetManager
import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Desktop-generated PCM16 recordings, not a Qwen model running on the phone. */
class SerenaPrompts(private val assets: AssetManager) {
    private val clips: JSONObject? by lazy {
        try {
            val manifest = assets.open("voice/serena/manifest.json").bufferedReader().use {
                JSONObject(it.readText())
            }
            require(manifest.getInt("schema") == 1)
            require(manifest.getString("speaker") == "Serena")
            manifest.getJSONObject("clips")
        } catch (_: Exception) { null }
    }

    fun pathFor(text: String): String? {
        val name = clips?.optString(text.replace(Regex("\\s+"), ""), "") ?: return null
        // Do not allow arbitrary paths from a malformed manifest.
        if (!Regex("[a-f0-9]{24}\\.wav").matches(name)) return null
        return "voice/serena/$name"
    }

    fun read(path: String): PcmWav.Audio = PcmWav.decode(assets.open(path).use { it.readBytes() })
}

object PcmWav {
    data class Audio(val samples: FloatArray, val sampleRate: Int)

    fun decode(bytes: ByteArray): Audio {
        require(bytes.size >= 44)
        val data = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        fun tag(offset: Int) = String(bytes, offset, 4, Charsets.US_ASCII)
        require(tag(0) == "RIFF" && tag(8) == "WAVE")
        var offset = 12
        var rate = 0
        var pcmOffset = -1
        var pcmSize = 0
        while (offset + 8 <= bytes.size) {
            val size = data.getInt(offset + 4)
            require(size >= 0 && size <= bytes.size - offset - 8)
            when (tag(offset)) {
                "fmt " -> {
                    require(size >= 16)
                    require(data.getShort(offset + 8).toInt() == 1) // PCM
                    require(data.getShort(offset + 10).toInt() == 1) // mono
                    rate = data.getInt(offset + 12)
                    require(data.getShort(offset + 22).toInt() == 16)
                }
                "data" -> { pcmOffset = offset + 8; pcmSize = size }
            }
            offset += 8 + size + (size % 2)
        }
        require(rate == 24000 && pcmOffset >= 0 && pcmSize > 0 && pcmSize % 2 == 0)
        return Audio(FloatArray(pcmSize / 2) {
            data.getShort(pcmOffset + it * 2) / 32768.0f
        }, rate)
    }
}
