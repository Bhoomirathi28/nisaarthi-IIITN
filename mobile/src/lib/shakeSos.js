// Bridge to the native shake-for-SOS service (android/.../ShakeSosPlugin.kt).
// Runs only during a trip: started when the routes page opens, stopped on "End trip", on arrival,
// or by the service itself an hour after the reach-by time. In the browser it does nothing,
// and the in-app shake detector (lib/native.js) is used instead.
import { Capacitor, registerPlugin } from "@capacitor/core";

const ShakeSos = registerPlugin("ShakeSos");
export const shakeAvailable = Capacitor.isNativePlatform() && Capacitor.getPlatform() === "android";

const HOUR = 3600 * 1000;

export async function status() {
  if (!shakeAvailable) return { available: false, running: false };
  try {
    return await ShakeSos.status();
  } catch {
    return { available: false, running: false };
  }
}

// Location is required (the SMS carries it); SMS and notifications are asked for at the same time.
export async function askPermissions() {
  if (!shakeAvailable) return null;
  try {
    return await ShakeSos.requestPermissions({ permissions: ["location", "sms", "notifications"] });
  } catch {
    return null;
  }
}

/** Start (or update) protection for this trip. t: translate function, for texts in the user's language. */
export async function startTrip({ contacts, settings, plan, t }) {
  if (!shakeAvailable) return { available: false, running: false };
  const deadline = plan?.deadline ? new Date(plan.deadline).getTime() : null;
  const departure = plan?.departure ? new Date(plan.departure).getTime() : Date.now();
  const endAt = deadline ? deadline + HOUR : Math.max(Date.now(), departure) + 6 * HOUR;
  await askPermissions();
  try {
    await ShakeSos.start({
      contacts: contacts.map(({ name, phone }) => ({ name, phone })),
      message: t("sms_body"),          // {lat} and {lon} are filled in on the phone
      noLocationMessage: t("sms_no_loc"),
      sensitivity: settings.sensitivity || "normal",
      sirenAuto: settings.sirenAuto !== false,
      countdown: 5,
      endAt,
      texts: {
        runningTitle: t("shake_on_title"),
        runningText: t("shake_on_text"),
        endTrip: t("end_trip"),
        countdown: t("sos_countdown_n"),
        cancel: t("cancel"),
        sent: t("sos_sent_n"),
        sentFailed: t("sos_sms_failed"),
        stopSiren: t("siren_stop"),
        call112: t("call112"),
      },
    });
  } catch (e) {
    return { available: true, running: false, error: e?.code || "start_failed" };
  }
  return status();
}

export async function endTrip() {
  if (shakeAvailable) await ShakeSos.stop().catch(() => {});
}

export const cancelSos = () => shakeAvailable && ShakeSos.cancelSos().catch(() => {});
export const stopNativeSiren = () => shakeAvailable && ShakeSos.stopSiren().catch(() => {});
export const openFullScreenSettings = () => ShakeSos.openFullScreenSettings().catch(() => {});
export const openBatterySettings = () => ShakeSos.openBatterySettings().catch(() => {});

/** Listen to "sos", "trip" and "siren" events. Returns an unsubscribe function. */
export function onShakeEvents(handlers) {
  if (!shakeAvailable) return () => {};
  const subs = Object.entries(handlers).map(([event, cb]) => ShakeSos.addListener(event, cb));
  return () => subs.forEach((s) => Promise.resolve(s).then((h) => h.remove()));
}
