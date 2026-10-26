package `in`.nisaarthi.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ShakeDetectorTest {
    private var shakes = 0
    private fun detector(s: ShakeDetector.Sensitivity) = ShakeDetector(s) { shakes++ }

    /** n jolts of the given strength, gapMs apart, starting at startMs. Returns the time after the last one. */
    private fun jolts(d: ShakeDetector, n: Int, strength: Float, gapMs: Long, startMs: Long = 0): Long {
        var t = startMs
        repeat(n) { d.onReading(strength, 0f, 9.8f, t); t += gapMs }
        return t
    }

    @Test fun walkingNeverTriggers() {
        val d = detector(ShakeDetector.Sensitivity.NORMAL)
        var t = 0L
        repeat(2000) { d.onReading(3f, 2f, 11f, t); t += 20 }  // normal motion, ~12 m/s²
        assertEquals(0, shakes)
    }

    @Test fun threeHardShakesTrigger() {
        jolts(detector(ShakeDetector.Sensitivity.NORMAL), 3, 30f, 300)
        assertEquals(1, shakes)
    }

    @Test fun jolsTooFarApartDoNotTrigger() {
        jolts(detector(ShakeDetector.Sensitivity.NORMAL), 3, 30f, 900)  // spread over 1.8 s
        assertEquals(0, shakes)
    }

    @Test fun oneLongJoltCountsOnce() {
        val d = detector(ShakeDetector.Sensitivity.NORMAL)
        var t = 0L
        repeat(10) { d.onReading(30f, 0f, 9.8f, t); t += 10 }  // 100 ms of readings from one bump
        assertEquals(0, shakes)
    }

    @Test fun lowSensitivityIgnoresAPotholeThatNormalWouldCatch() {
        jolts(detector(ShakeDetector.Sensitivity.LOW), 3, 30f, 300)
        assertEquals(0, shakes)  // 30 m/s² is below LOW's threshold, and LOW needs 4 jolts
        jolts(detector(ShakeDetector.Sensitivity.LOW), 4, 36f, 300, startMs = 5_000)
        assertEquals(1, shakes)
    }

    @Test fun highSensitivityCatchesALighterShake() {
        jolts(detector(ShakeDetector.Sensitivity.HIGH), 3, 24f, 300)
        assertEquals(1, shakes)
    }

    @Test fun noSecondSosDuringCooldown() {
        val d = detector(ShakeDetector.Sensitivity.NORMAL)
        val t = jolts(d, 3, 30f, 300)
        jolts(d, 3, 30f, 300, startMs = t + 1_000)
        assertEquals(1, shakes)
        jolts(d, 3, 30f, 300, startMs = t + ShakeDetector.COOLDOWN_MS + 1_000)
        assertEquals(2, shakes)
    }

    @Test fun sensitivityNamesFromTheApp() {
        assertEquals(ShakeDetector.Sensitivity.LOW, ShakeDetector.Sensitivity.from("low"))
        assertEquals(ShakeDetector.Sensitivity.NORMAL, ShakeDetector.Sensitivity.from(null))
        assertEquals(ShakeDetector.Sensitivity.NORMAL, ShakeDetector.Sensitivity.from("bogus"))
    }

    @Test fun smsCarriesLocationOrSaysItIsMissing() {
        val tpl = "SOS! {lat},{lon} https://maps.google.com/?q={lat},{lon}"
        assertEquals("SOS! 21.144600,79.082200 https://maps.google.com/?q=21.144600,79.082200",
            SosMessage.build(tpl, "SOS! Location not found.", 21.1446, 79.0822))
        assertEquals("SOS! Location not found.", SosMessage.build(tpl, "SOS! Location not found.", null, null))
        assertEquals("+919876543210", SosMessage.cleanNumber("+91 98765-43210"))
        assertTrue(SosMessage.cleanNumber("(0712) 255").all { it.isDigit() })
        assertFalse(SosMessage.cleanNumber("abc").isNotEmpty())
    }
}
