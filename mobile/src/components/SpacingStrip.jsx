import { useT } from "../i18n";
import { metres } from "../lib/time";

// Like the notebook sketch: dots for open places along the route.
// Evenly spread dots are good; a long empty stretch is drawn as a dashed red gap.
export default function SpacingStrip({ spacing }) {
  const { t } = useT();
  if (!spacing || !spacing.value) return null;
  const { positions_m: pos = [], length_m: len = 1, max_gap_m: gap } = spacing.value;
  const W = 300;
  const x = (m) => 12 + (m / len) * (W - 24);
  const stops = [0, ...pos, len];
  let gi = 0, gmax = -1;
  stops.slice(1).forEach((s, i) => { if (s - stops[i] > gmax) { gmax = s - stops[i]; gi = i; } });
  return (
    <figure className="strip">
      <svg viewBox={`0 0 ${W} 44`} width="100%" role="img" aria-label={t("longest_gap", { m: metres(gap) })}>
        <line x1="12" y1="20" x2={W - 12} y2="20" stroke="var(--line)" strokeWidth="2" />
        <line x1={x(stops[gi])} y1="20" x2={x(stops[gi + 1])} y2="20" stroke="var(--sindoor)"
          strokeWidth="3" strokeDasharray="5 4" />
        {pos.map((p, i) => (
          <circle key={i} cx={x(p)} cy="20" r="5" fill="var(--haldi)" stroke="var(--ink)" strokeWidth="1.5" />
        ))}
        <circle cx="12" cy="20" r="6" fill="none" stroke="var(--paper)" strokeWidth="2" />
        <rect x={W - 18} y="14" width="12" height="12" fill="none" stroke="var(--paper)" strokeWidth="2" />
        <text x="12" y="40" className="strip-label">{t("start")}</text>
        <text x={W - 12} y="40" textAnchor="end" className="strip-label">{t("end")}</text>
      </svg>
      <figcaption>{t("longest_gap", { m: metres(gap) })}</figcaption>
    </figure>
  );
}
