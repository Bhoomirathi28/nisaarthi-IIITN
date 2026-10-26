package `in`.nisaarthi.app

import java.util.Locale

/** Builds the SOS SMS from the template the app sends in the user's language. */
object SosMessage {
    /**
     * template uses {lat} and {lon}, e.g. "SOS! I need help. My location: {lat},{lon} https://maps.google.com/?q={lat},{lon}".
     * When there is no location fix, noLocation is sent instead, so the SMS never carries a made-up place.
     */
    fun build(template: String, noLocation: String, lat: Double?, lon: Double?): String {
        if (lat == null || lon == null) return noLocation
        val la = String.format(Locale.US, "%.6f", lat)
        val lo = String.format(Locale.US, "%.6f", lon)
        return template.replace("{lat}", la).replace("{lon}", lo)
    }

    /** Keeps only dialable characters: "+91 98765-43210" -> "+919876543210". */
    fun cleanNumber(phone: String): String = phone.filter { it.isDigit() || it == '+' }
}
