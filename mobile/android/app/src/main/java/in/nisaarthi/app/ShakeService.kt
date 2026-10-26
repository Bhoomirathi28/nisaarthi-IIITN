package `in`.nisaarthi.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.os.VibrationEffect
import android.os.Vibrator
import android.telephony.SmsManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject

/**
 * Runs only during a trip. Listens for a deliberate shake even when the app is closed or the
 * screen is locked; on a shake it counts down (with Cancel), then sends the SOS SMS with the
 * location to every emergency contact, with no internet needed, and plays the siren.
 *
 * Started and stopped by ShakeSosPlugin. Its settings are saved, so Android can restart it.
 */
class ShakeService : Service(), SensorEventListener, LocationListener {

    enum class SosState { IDLE, COUNTDOWN, SENT }

    private lateinit var config: JSONObject
    private lateinit var detector: ShakeDetector
    private lateinit var siren: Siren
    private val handler = Handler(Looper.getMainLooper())
    private var wakeLock: PowerManager.WakeLock? = null
    private var lastFix: Location? = null
    private var secondsLeft = 0

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        siren = Siren(this)
        createChannels(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> { endTrip("stopped"); return START_NOT_STICKY }
            ACTION_CANCEL_SOS -> { cancelSos(); return START_STICKY }
            ACTION_STOP_SIREN -> { stopSiren(); return START_STICKY }
        }
        // ACTION_START, or Android restarting the service (intent == null): load the saved trip
        val saved = intent?.getStringExtra(EXTRA_CONFIG)?.also { prefs(this).edit().putString(KEY_CONFIG, it).apply() }
            ?: prefs(this).getString(KEY_CONFIG, null)
        if (saved == null) { stopSelf(); return START_NOT_STICKY }
        config = JSONObject(saved)
        if (config.optLong("endAt") in 1..System.currentTimeMillis()) { endTrip("timeout"); return START_NOT_STICKY }

        startInForeground()
        if (!::detector.isInitialized) {
            detector = ShakeDetector(ShakeDetector.Sensitivity.from(config.optString("sensitivity"))) { onShake() }
            listenForShakes()
            listenForLocation()
            scheduleTripEnd()
        } else {
            detector.sensitivity = ShakeDetector.Sensitivity.from(config.optString("sensitivity"))
        }
        running = true
        instance = this
        emit("trip", mapOf("running" to true))
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        instance = null
        (getSystemService(SENSOR_SERVICE) as SensorManager).unregisterListener(this)
        runCatching { (getSystemService(LOCATION_SERVICE) as LocationManager).removeUpdates(this) }
        handler.removeCallbacksAndMessages(null)
        siren.stop()
        wakeLock?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }

    // ---- Foreground notification ----

    private fun text(key: String, fallback: String) = config.optJSONObject("texts")?.optString(key)?.takeIf { it.isNotEmpty() } ?: fallback

    private fun startInForeground() {
        val n = NotificationCompat.Builder(this, CHANNEL_TRIP)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(text("runningTitle", "NISAARTHI"))
            .setContentText(text("runningText", "Shake the phone hard 3 times for SOS"))
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setContentIntent(openAppIntent(false))
            .addAction(0, text("endTrip", "End trip"), serviceIntent(ACTION_STOP, 1))
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIF_TRIP, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
        } else {
            startForeground(NOTIF_TRIP, n)
        }
    }

    // ---- Shake ----

    private fun listenForShakes() {
        val sm = getSystemService(SENSOR_SERVICE) as SensorManager
        // A wake-up accelerometer keeps working with the screen off without holding the CPU awake.
        val wakeUp = sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER, true)
        val sensor = wakeUp ?: sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER) ?: return
        // Readings may arrive up to 0.3 s late in a batch, which saves battery and is still fast enough.
        sm.registerListener(this, sensor, SensorManager.SENSOR_DELAY_GAME, 300_000, handler)
        if (wakeUp == null) {
            // Without a wake-up sensor the CPU must stay awake for readings to arrive; only for the trip.
            val pm = getSystemService(POWER_SERVICE) as PowerManager
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "nisaarthi:shake").apply {
                setReferenceCounted(false)
                acquire(tripMillisLeft().coerceAtLeast(60_000))
            }
        }
    }

    override fun onSensorChanged(e: SensorEvent) {
        // event timestamps are nanoseconds since boot; convert to milliseconds
        detector.onReading(e.values[0], e.values[1], e.values[2], e.timestamp / 1_000_000)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

    private fun onShake() {
        if (sosState != SosState.IDLE) return
        startCountdown()
    }

    // ---- Location (kept fresh during the trip so the SMS has it even with no signal later) ----

    @SuppressLint("MissingPermission")
    private fun listenForLocation() {
        if (!hasPermission(Manifest.permission.ACCESS_FINE_LOCATION) && !hasPermission(Manifest.permission.ACCESS_COARSE_LOCATION)) return
        val lm = getSystemService(LOCATION_SERVICE) as LocationManager
        for (provider in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
            if (runCatching { lm.isProviderEnabled(provider) }.getOrDefault(false)) {
                lm.requestLocationUpdates(provider, 30_000L, 20f, this, Looper.getMainLooper())
                lm.getLastKnownLocation(provider)?.let { onLocationChanged(it) }
            }
        }
    }

    override fun onLocationChanged(location: Location) {
        val old = lastFix
        // Prefer newer fixes; between fixes of similar age keep the more accurate one
        if (old == null || location.time - old.time > 60_000 || location.accuracy <= old.accuracy) lastFix = location
    }

    @Deprecated("Needed for older Android versions")
    override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) {}
    override fun onProviderEnabled(provider: String) {}
    override fun onProviderDisabled(provider: String) {}

    // ---- SOS ----

    private fun startCountdown() {
        sosState = SosState.COUNTDOWN
        secondsLeft = config.optInt("countdown", 5)
        vibrate(longArrayOf(0, 500, 200, 500, 200, 500))
        tick()
    }

    private fun tick() {
        if (sosState != SosState.COUNTDOWN) return
        if (secondsLeft <= 0) { sendSos(); return }
        showSosNotification(text("countdown", "Sending SOS in {n} s").replace("{n}", secondsLeft.toString()),
            listOf(text("cancel", "Cancel") to serviceIntent(ACTION_CANCEL_SOS, 2)))
        emit("sos", mapOf("state" to "countdown", "secondsLeft" to secondsLeft))
        secondsLeft -= 1
        handler.postDelayed({ tick() }, 1000)
    }

    private fun cancelSos() {
        if (sosState != SosState.COUNTDOWN) return
        sosState = SosState.IDLE
        handler.removeCallbacksAndMessages(null)
        scheduleTripEnd()
        vibrate(null)
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).cancel(NOTIF_SOS)
        emit("sos", mapOf("state" to "cancelled"))
    }

    private fun sendSos() {
        sosState = SosState.SENT
        val fix = lastFix
        val body = SosMessage.build(config.optString("message"), config.optString("noLocationMessage", "SOS!"),
            fix?.latitude, fix?.longitude)
        val contacts = config.optJSONArray("contacts")
        var sent = 0
        var failed = 0
        if (contacts != null && hasPermission(Manifest.permission.SEND_SMS)) {
            val sms = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) getSystemService(SmsManager::class.java)
                      else @Suppress("DEPRECATION") SmsManager.getDefault()
            val parts = sms.divideMessage(body)  // Indian scripts fit fewer characters per SMS
            for (i in 0 until contacts.length()) {
                val number = SosMessage.cleanNumber(contacts.getJSONObject(i).optString("phone"))
                if (number.isEmpty()) continue
                runCatching { sms.sendMultipartTextMessage(number, null, parts, null, null) }
                    .onSuccess { sent++ }.onFailure { failed++ }
            }
        } else {
            failed = contacts?.length() ?: 0
        }
        if (config.optBoolean("sirenAuto", true)) siren.start()
        vibrate(null)
        val title = if (sent > 0) text("sent", "SOS sent to {n} contacts").replace("{n}", sent.toString())
                    else text("sentFailed", "SOS SMS could not be sent. Call 112.")
        val actions = mutableListOf(text("call112", "Call 112") to dialIntent())
        if (siren.playing) actions.add(text("stopSiren", "Stop siren") to serviceIntent(ACTION_STOP_SIREN, 3))
        showSosNotification(title, actions)
        emit("sos", mapOf("state" to "sent", "sent" to sent, "failed" to failed,
            "lat" to fix?.latitude, "lon" to fix?.longitude, "siren" to siren.playing))
        // Ready for another SOS later; the "sent" notification stays until dismissed
        handler.postDelayed({ if (sosState == SosState.SENT) sosState = SosState.IDLE }, 60_000)
        scheduleTripEnd()
    }

    private fun stopSiren() {
        siren.stop()
        emit("siren", mapOf("playing" to false))
    }

    private fun showSosNotification(title: String, actions: List<Pair<String, PendingIntent>>) {
        val b = NotificationCompat.Builder(this, CHANNEL_SOS)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOnlyAlertOnce(true)
            .setAutoCancel(false)
            .setContentIntent(openAppIntent(true))
            // Opens the app over the lock screen (needs the "full-screen alerts" permission on Android 14+)
            .setFullScreenIntent(openAppIntent(true), true)
        actions.forEach { (label, pi) -> b.addAction(0, label, pi) }
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).notify(NOTIF_SOS, b.build())
    }

    // ---- Trip end ----

    private fun tripMillisLeft(): Long {
        val endAt = config.optLong("endAt")
        return if (endAt > 0) endAt - System.currentTimeMillis() else DEFAULT_TRIP_MS
    }

    private fun scheduleTripEnd() {
        handler.postDelayed({ if (sosState == SosState.IDLE) endTrip("timeout") else scheduleTripEnd() },
            tripMillisLeft().coerceAtLeast(60_000))
    }

    private fun endTrip(reason: String) {
        prefs(this).edit().remove(KEY_CONFIG).apply()
        emit("trip", mapOf("running" to false, "reason" to reason))
        running = false
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    // ---- Helpers ----

    private fun hasPermission(p: String) = ContextCompat.checkSelfPermission(this, p) == PackageManager.PERMISSION_GRANTED

    private fun vibrate(pattern: LongArray?) {
        val v = getSystemService(VIBRATOR_SERVICE) as? Vibrator ?: return
        if (pattern == null) v.cancel() else v.vibrate(VibrationEffect.createWaveform(pattern, -1))
    }

    private fun serviceIntent(action: String, code: Int): PendingIntent =
        PendingIntent.getService(this, code, Intent(this, ShakeService::class.java).setAction(action),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

    private fun openAppIntent(sos: Boolean): PendingIntent =
        PendingIntent.getActivity(this, if (sos) 10 else 11,
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                .putExtra(MainActivity.EXTRA_SOS, sos),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

    private fun dialIntent(): PendingIntent =
        PendingIntent.getActivity(this, 12, Intent(Intent.ACTION_DIAL, Uri.parse("tel:112"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE)

    private fun emit(event: String, data: Map<String, Any?>) {
        handler.post { listener?.invoke(event, data) }
    }

    companion object {
        const val ACTION_START = "in.nisaarthi.app.START"
        const val ACTION_STOP = "in.nisaarthi.app.STOP"
        const val ACTION_CANCEL_SOS = "in.nisaarthi.app.CANCEL_SOS"
        const val ACTION_STOP_SIREN = "in.nisaarthi.app.STOP_SIREN"
        const val EXTRA_CONFIG = "config"
        private const val KEY_CONFIG = "trip_config"
        private const val CHANNEL_TRIP = "trip"
        private const val CHANNEL_SOS = "sos"
        private const val NOTIF_TRIP = 1
        private const val NOTIF_SOS = 2
        private const val DEFAULT_TRIP_MS = 6 * 3600 * 1000L  // no deadline given: stop after 6 hours

        @Volatile var running = false
            private set
        @Volatile var sosState = SosState.IDLE
            private set
        @Volatile var instance: ShakeService? = null
            private set
        /** Set by the plugin to pass events to the app. */
        var listener: ((String, Map<String, Any?>) -> Unit)? = null

        fun secondsLeft() = instance?.secondsLeft ?: 0
        fun sirenPlaying() = instance?.siren?.playing ?: false

        fun prefs(c: Context) = c.getSharedPreferences("nisaarthi_shake", Context.MODE_PRIVATE)

        fun createChannels(c: Context) {
            val nm = c.getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(NotificationChannel(CHANNEL_TRIP, "Trip protection", NotificationManager.IMPORTANCE_LOW)
                .apply { description = "Shown while shake-for-SOS is on during a trip" })
            nm.createNotificationChannel(NotificationChannel(CHANNEL_SOS, "SOS", NotificationManager.IMPORTANCE_HIGH)
                .apply {
                    description = "SOS countdown and confirmation"
                    lockscreenVisibility = Notification.VISIBILITY_PUBLIC
                    enableVibration(true)
                })
        }
    }
}
