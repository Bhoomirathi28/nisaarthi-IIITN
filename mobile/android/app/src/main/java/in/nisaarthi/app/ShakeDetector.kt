package `in`.nisaarthi.app

import kotlin.math.sqrt

/**
 * Decides when the phone has been shaken on purpose: several hard jolts in a short window.
 * Same rule as the in-app detector (lib/native.js), with three sensitivity levels so riders
 * on bumpy two-wheeler rides can make it harder to trigger by accident.
 *
 * Pure logic with no Android types, so it is unit-tested on the computer.
 */
class ShakeDetector(var sensitivity: Sensitivity = Sensitivity.NORMAL, private val onShake: () -> Unit) {

    enum class Sensitivity(val thresholdMs2: Float, val hits: Int, val windowMs: Long) {
        // Acceleration including gravity, in m/s². Gravity alone is about 9.8.
        LOW(34f, 4, 1500),     // hardest to trigger: for two-wheeler riders
        NORMAL(28f, 3, 1200),  // matches the in-app detector
        HIGH(22f, 3, 1200);    // easiest to trigger

        companion object {
            fun from(name: String?) = values().firstOrNull { it.name.equals(name, ignoreCase = true) } ?: NORMAL
        }
    }

    private val hits = ArrayDeque<Long>()
    private var lastHitMs = Long.MIN_VALUE / 2
    private var lastShakeMs = Long.MIN_VALUE / 2

    /** Feed one accelerometer reading. Returns true when it completed a shake. */
    fun onReading(x: Float, y: Float, z: Float, nowMs: Long): Boolean {
        val magnitude = sqrt(x * x + y * y + z * z)
        if (magnitude < sensitivity.thresholdMs2) return false
        if (nowMs - lastHitMs < MIN_GAP_MS) return false  // one jolt produces many readings
        if (nowMs - lastShakeMs < COOLDOWN_MS) return false  // don't fire again while SOS is starting
        lastHitMs = nowMs
        while (hits.isNotEmpty() && nowMs - hits.first() > sensitivity.windowMs) hits.removeFirst()
        hits.addLast(nowMs)
        if (hits.size >= sensitivity.hits) {
            hits.clear()
            lastShakeMs = nowMs
            onShake()
            return true
        }
        return false
    }

    companion object {
        const val MIN_GAP_MS = 150L
        const val COOLDOWN_MS = 10_000L
    }
}
