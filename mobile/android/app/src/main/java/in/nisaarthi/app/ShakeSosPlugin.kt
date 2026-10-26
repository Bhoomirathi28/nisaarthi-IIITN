package `in`.nisaarthi.app

import android.Manifest
import android.app.NotificationManager
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.core.content.ContextCompat
import com.getcapacitor.JSObject
import com.getcapacitor.PermissionState
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.getcapacitor.annotation.Permission

/**
 * Bridge between the app (mobile/src/lib/shakeSos.js) and ShakeService.
 * Events to the app: "trip" {running, reason}, "sos" {state, secondsLeft, sent, failed, lat, lon}, "siren" {playing}.
 */
@CapacitorPlugin(
    name = "ShakeSos",
    permissions = [
        Permission(alias = "location", strings = [Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION]),
        Permission(alias = "sms", strings = [Manifest.permission.SEND_SMS]),
        Permission(alias = "notifications", strings = [Manifest.permission.POST_NOTIFICATIONS]),
    ]
)
class ShakeSosPlugin : Plugin() {

    override fun load() {
        ShakeService.listener = { event, data ->
            val js = JSObject()
            data.forEach { (k, v) -> js.put(k, v) }
            notifyListeners(event, js, true)  // keep events until the app is listening (e.g. opened by SOS)
        }
    }

    override fun handleOnDestroy() {
        ShakeService.listener = null
    }

    /** Start shake protection for this trip. The app passes contacts, texts in the user's language, and settings. */
    @PluginMethod
    fun start(call: PluginCall) {
        if (getPermissionState("location") != PermissionState.GRANTED) {
            call.reject("Location permission is needed for shake SOS", "location_permission")
            return
        }
        val config = call.data  // contacts, message, noLocationMessage, sensitivity, sirenAuto, endAt, countdown, texts
        val intent = Intent(context, ShakeService::class.java)
            .setAction(ShakeService.ACTION_START)
            .putExtra(ShakeService.EXTRA_CONFIG, config.toString())
        try {
            ContextCompat.startForegroundService(context, intent)
            call.resolve(statusObject())
        } catch (e: Exception) {
            call.reject("Could not start shake protection: ${e.message}", "start_failed")
        }
    }

    @PluginMethod
    fun stop(call: PluginCall) {
        if (ShakeService.running) {
            context.startService(Intent(context, ShakeService::class.java).setAction(ShakeService.ACTION_STOP))
        }
        call.resolve()
    }

    @PluginMethod
    fun status(call: PluginCall) = call.resolve(statusObject())

    @PluginMethod
    fun cancelSos(call: PluginCall) = sendAction(call, ShakeService.ACTION_CANCEL_SOS)

    @PluginMethod
    fun stopSiren(call: PluginCall) = sendAction(call, ShakeService.ACTION_STOP_SIREN)

    /** Android 14+: lets the SOS screen open over the lock screen. */
    @PluginMethod
    fun openFullScreenSettings(call: PluginCall) {
        if (Build.VERSION.SDK_INT >= 34) {
            openSettings(Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, Uri.parse("package:${context.packageName}")))
        }
        call.resolve()
    }

    /** Asks to stop battery optimisation, which otherwise lets some phones kill the service. */
    @PluginMethod
    fun openBatterySettings(call: PluginCall) {
        openSettings(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${context.packageName}")))
        call.resolve()
    }

    private fun sendAction(call: PluginCall, action: String) {
        if (ShakeService.running) context.startService(Intent(context, ShakeService::class.java).setAction(action))
        call.resolve()
    }

    private fun openSettings(intent: Intent) {
        runCatching { activity.startActivity(intent) }
            .onFailure { activity.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}"))) }
    }

    private fun statusObject(): JSObject {
        val nm = context.getSystemService(NotificationManager::class.java)
        val pm = context.getSystemService(PowerManager::class.java)
        return JSObject().apply {
            put("available", true)
            put("running", ShakeService.running)
            put("sos", ShakeService.sosState.name.lowercase())
            put("secondsLeft", ShakeService.secondsLeft())
            put("siren", ShakeService.sirenPlaying())
            put("smsAllowed", getPermissionState("sms") == PermissionState.GRANTED)
            put("notificationsAllowed", nm.areNotificationsEnabled())
            put("fullScreenAllowed", if (Build.VERSION.SDK_INT >= 34) nm.canUseFullScreenIntent() else true)
            put("batteryUnrestricted", pm.isIgnoringBatteryOptimizations(context.packageName))
        }
    }
}
