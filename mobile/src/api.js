const DEFAULT_URL = import.meta.env.VITE_API_URL || "http://10.0.2.2:8000";
let base = DEFAULT_URL;
let token = null;
export const setToken = (t) => { token = t; };

export const setApiBase = (url) => {
  base = (url || DEFAULT_URL).replace(/\/+$/, "");
};
export const getApiBase = () => base;
export const defaultApiBase = DEFAULT_URL;

async function request(path, options = {}, timeoutMs = 45000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${base}${path}`, {
      ...options,
      signal: ctrl.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
      },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request("/health", {}, 5000),
  demo: () => request("/demo", {}, 8000),
  plan: (body) => request("/plan", { method: "POST", body: JSON.stringify(body) }),
  signup: (body) => request("/users", { method: "POST", body: JSON.stringify(body) }, 15000),
  me: () => request("/users/me", {}, 8000),
  updateMe: (body) => request("/users/me", { method: "PATCH", body: JSON.stringify(body) }, 8000),
  updateContacts: (contacts) => request("/users/me/contacts", { method: "PUT", body: JSON.stringify({ contacts }) }, 8000),
  searchPlaces: (text, near) => {
    const q = new URLSearchParams({ text });
    if (near) { q.set("lat", near.lat); q.set("lon", near.lon); }
    return request(`/places/search?${q}`, {}, 8000);
  },
  help: (lat, lon) => request(`/help/nearby?lat=${lat}&lon=${lon}`, {}, 30000),
};
