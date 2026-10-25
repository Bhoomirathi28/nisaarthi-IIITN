// Places the user picked from search, kept on the phone so search still works offline.
import { load, save } from "./native";

const KEY = "recentPlaces";
const MAX = 8;

export async function recentPlaces() {
  return load(KEY, []);
}

export async function rememberPlace(p) {
  const list = (await recentPlaces()).filter((x) => x.lat !== p.lat || x.lon !== p.lon);
  const saved = { name: p.name, address: p.address || "", lat: p.lat, lon: p.lon, fetched_at: new Date().toISOString() };
  await save(KEY, [saved, ...list].slice(0, MAX));
}
