// Reliability score inside a double ring, like the borders of a Madhubani panel.
export default function ScoreRing({ value, size = 92 }) {
  const r = 38;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, value ?? 0));
  const tone = v >= 70 ? "var(--neem)" : v >= 45 ? "var(--haldi)" : "var(--sindoor)";
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" role="img" aria-label={`${v} / 100`}>
      <circle cx="50" cy="50" r="46" fill="none" stroke="var(--line)" strokeWidth="1.2" />
      <circle cx="50" cy="50" r={r} fill="none" stroke="var(--ink-3)" strokeWidth="7" />
      <circle cx="50" cy="50" r={r} fill="none" stroke={tone} strokeWidth="7" strokeLinecap="round"
        strokeDasharray={`${(c * v) / 100} ${c}`} transform="rotate(-90 50 50)" />
      <circle cx="50" cy="50" r="30" fill="none" stroke="var(--line)" strokeWidth="1.2" />
      <text x="50" y="58" textAnchor="middle" className="ring-num">{v}</text>
    </svg>
  );
}
