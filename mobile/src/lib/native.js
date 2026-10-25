// Thin wrappers over Capacitor plugins. Each works in the browser too, for development.
import { Capacitor } from "@capacitor/core";
import { Geolocation } from "@capacitor/geolocation";
import { Network } from "@capacitor/network";
import { Preferences } from "@capacitor/preferences";
import { AppLauncher } from "@capacitor/app-launcher";
import { Motion } from "@capacitor/motion";

export const isNative = Capacitor.isNativePlatform();

export async function getLocation() {
  try {
    if (isNative) {
      const perm = await Geolocation.checkPermissions();
      if (perm.location !== "granted") await Geolocation.requestPermissions();
    }
    const pos = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 10000 });
    return { lat: pos.coords.latitude, lon: pos.coords.longitude };
  } catch {
    return null;
  }
}

export async function isOnline() {
  try {
    return (await Network.getStatus()).connected;
  } catch {
    return navigator.onLine;
  }
}

export function onNetworkChange(cb) {
  const handle = Network.addListener("networkStatusChange", (s) => cb(s.connected));
  return () => handle.then((h) => h.remove());
}

export async function load(key, fallback) {
  try {
    const { value } = await Preferences.get({ key });
    return value == null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}

export async function save(key, value) {
  await Preferences.set({ key, value: JSON.stringify(value) });
}

export async function openUrl(url) {
  try {
    if (isNative) {
      await AppLauncher.openUrl({ url });
      return;
    }
  } catch {
    /* fall through to the browser */
  }
  window.open(url, "_blank");
}

// Shake detection: calls cb when the phone is shaken hard a few times in a short window.
export function onShake(cb, { threshold = 28, hits = 3, windowMs = 1200 } = {}) {
  let times = [];
  let last = 0;
  const handle = Motion.addListener("accel", (e) => {
    const a = e.accelerationIncludingGravity || e.acceleration;
    if (!a) return;
    const mag = Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z);
    const now = Date.now();
    if (mag > threshold && now - last > 150) {
      last = now;
      times = times.filter((t) => now - t < windowMs);
      times.push(now);
      if (times.length >= hits) {
        times = [];
        cb();
      }
    }
  });
  return () => handle.then((h) => h.remove());
}
