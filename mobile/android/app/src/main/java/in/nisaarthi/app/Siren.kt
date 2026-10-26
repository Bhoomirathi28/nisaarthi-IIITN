package `in`.nisaarthi.app

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import kotlin.math.PI
import kotlin.math.sin

/**
 * Loud two-tone siren on the ALARM stream, so it plays at alarm volume even when media volume is low
 * or the phone is on silent (Do Not Disturb can still block it). The alarm volume is raised to the
 * maximum while it plays and put back afterwards. Generated in code, so no sound file is needed.
 */
class Siren(context: Context) {
    private val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    @Volatile private var thread: Thread? = null
    private var savedVolume = -1

    val playing get() = thread != null

    @Synchronized
    fun start() {
        if (thread != null) return
        savedVolume = audio.getStreamVolume(AudioManager.STREAM_ALARM)
        audio.setStreamVolume(AudioManager.STREAM_ALARM, audio.getStreamMaxVolume(AudioManager.STREAM_ALARM), 0)
        val t = Thread({ play() }, "nisaarthi-siren")
        thread = t
        t.start()
    }

    @Synchronized
    fun stop() {
        val t = thread ?: return
        thread = null
        t.interrupt()
        if (savedVolume >= 0) audio.setStreamVolume(AudioManager.STREAM_ALARM, savedVolume, 0)
        savedVolume = -1
    }

    private fun play() {
        val rate = 22050
        // One rise and fall of the siren: 950 Hz +/- 420 Hz, like the in-app Web Audio siren
        val cycle = buildCycle(rate, seconds = 0.62)
        val minBuf = AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val track = AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ALARM)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build())
            .setAudioFormat(AudioFormat.Builder()
                .setSampleRate(rate)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                .build())
            .setBufferSizeInBytes(maxOf(minBuf, cycle.size * 2))
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
        try {
            track.play()
            while (!Thread.currentThread().isInterrupted && thread != null) {
                track.write(cycle, 0, cycle.size)
            }
        } finally {
            track.stop()
            track.release()
        }
    }

    private fun buildCycle(rate: Int, seconds: Double): ShortArray {
        val n = (rate * seconds).toInt()
        val out = ShortArray(n)
        var phase = 0.0
        for (i in 0 until n) {
            val sweep = sin(2 * PI * i / n)               // -1..1, one up-and-down per cycle
            val freq = 950 + 420 * sweep
            phase += 2 * PI * freq / rate
            // Square-ish wave: clipped sine carries further than a pure tone
            val v = (sin(phase) * 3).coerceIn(-1.0, 1.0)
            out[i] = (v * Short.MAX_VALUE * 0.95).toInt().toShort()
        }
        return out
    }
}
