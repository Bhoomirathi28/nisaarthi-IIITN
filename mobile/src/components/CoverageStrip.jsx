import { useT } from "../i18n";
import { metres } from "../lib/time";

// The route as a line from start to home: a dot for each place open when you reach it
// (hollow when it only half counts: closing soon, or police/hospital with unknown hours),
// and the longest stretch with nothing open drawn as a dashed red gap.
export default function CoverageStrip({ coverage, compact = false }) {
  const { t } = useT();
  const v = coverage?.value;
  if (!v || coverage.score == null) return null;
  const { positions_m: pos = [], cover = [], length_m: len = 1, longest_dark_m: dark } = v;
  const W = 300;
  const H = compact ? 26 : 44;
  const y = compact ? 12 : 20;
  const x = (m) => 12 + (m / (len || 1)) * (W - 24);
  const stops = [0, ...pos, len];
  let gi = 0, gmax = -1;
  stops.slice(1).forEach((s, i) => { if (s - stops[i] > gmax) { gmax = s - stops[i]; gi = i; } });
  const label = t("longest_gap", { m: metres(dark) });
  return (
    <figure className={`strip${compact ? " strip-compact" : ""}`}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={label}>
        <line x1="12" y1={y} x2={W - 12} y2={y} stroke="var(--line)" strokeWidth="2" />
        {dark > 0 && (
          <line x1={x(stops[gi])} y1={y} x2={x(stops[gi + 1])} y2={y} stroke="var(--sindoor)"
            strokeWidth="3" strokeDasharray="5 4" />
        )}
        {pos.map((p, i) => (
          <circle key={i} cx={x(p)} cy={y} r={compact ? 4 : 5} strokeWidth="1.5"
            fill={cover[i] === 1 ? "var(--haldi)" : "var(--ink)"} stroke={cover[i] === 1 ? "var(--ink)" : "var(--haldi)"} />
        ))}
        <circle cx="12" cy={y} r={compact ? 4.5 : 6} fill="none" stroke="var(--paper)" strokeWidth="2" />
        <rect x={W - (compact ? 16 : 18)} y={y - (compact ? 4.5 : 6)} width={compact ? 9 : 12} height={compact ? 9 : 12}
          fill="none" stroke="var(--paper)" strokeWidth="2" />
        {!compact && <text x="12" y="40" className="strip-label">{t("start")}</text>}
        {!compact && <text x={W - 12} y="40" textAnchor="end" className="strip-label">{t("end")}</text>}
      </svg>
      {!compact && <figcaption>{label}</figcaption>}
    </figure>
  );
}
