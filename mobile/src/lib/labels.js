// KNOWN data turns OUTDATED on the phone once it is older than the freshness window,
// e.g. a saved plan opened while offline.
export function aged(label, generatedAt, freshMinutes = 15) {
  if (label !== "KNOWN" || !generatedAt) return label;
  const age = (Date.now() - new Date(generatedAt).getTime()) / 60000;
  return age > freshMinutes ? "OUTDATED" : label;
}
