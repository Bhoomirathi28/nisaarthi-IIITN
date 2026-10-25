// "02:15" -> the next sensible Date for a night shift.
export function timeToDate(hhmm, after) {
  if (!hhmm) return null;
  const [h, m] = hhmm.split(":").map(Number);
  const now = new Date();
  const d = new Date(now);
  d.setHours(h, m, 0, 0);
  if (after) {
    while (d <= after) d.setDate(d.getDate() + 1); // reach-by must be after shift end
  } else if (now - d > 6 * 3600 * 1000) {
    d.setDate(d.getDate() + 1); // e.g. at 11 PM, "02:15" means tonight
  }
  return d;
}

// ISO string that keeps the phone's own UTC offset (e.g. +05:30).
export function toLocalIso(d) {
  const pad = (n) => String(Math.abs(n)).padStart(2, "0");
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00` +
    `${sign}${pad(Math.floor(Math.abs(off) / 60))}:${pad(Math.abs(off) % 60)}`
  );
}

export function clock(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function minutesSince(iso) {
  return Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
}

export function metres(m) {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}
