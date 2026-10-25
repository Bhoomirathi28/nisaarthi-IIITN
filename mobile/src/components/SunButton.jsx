import { useT } from "../i18n";

// The SOS button: a Madhubani sun with double-line rays and kachni hatching.
export default function SunButton({ onPress }) {
  const { t } = useT();
  const rays = Array.from({ length: 16 }, (_, i) => i * 22.5);
  return (
    <button className="sun" onClick={onPress} aria-label="SOS">
      <svg viewBox="0 0 240 240" width="100%" height="100%" aria-hidden="true">
        <g transform="translate(120 120)">
          {rays.map((a, i) => (
            <g key={a} transform={`rotate(${a})`}>
              <path d={i % 2 ? "M-9 -84 L0 -112 L9 -84 Z" : "M-11 -84 L0 -104 L11 -84 Z"}
                fill={i % 2 ? "var(--haldi)" : "var(--sindoor)"} stroke="var(--paper)" strokeWidth="1.4" />
              {i % 2 === 1 && <path d="M-3 -92 L3 -92 M-2 -98 L2 -98" stroke="var(--ink)" strokeWidth="1.3" />}
            </g>
          ))}
          <circle r="84" fill="var(--ink)" stroke="var(--haldi)" strokeWidth="2" />
          <circle r="77" fill="none" stroke="var(--haldi)" strokeWidth="1.2" strokeDasharray="2 5" />
          <circle r="70" fill="var(--sindoor)" stroke="var(--paper)" strokeWidth="2" />
          <circle r="62" fill="none" stroke="var(--paper)" strokeWidth="1" opacity=".55" />
          <text y="16" textAnchor="middle" className="sun-text">SOS</text>
        </g>
      </svg>
      <span className="visually-hidden">{t("sos_hint")}</span>
    </button>
  );
}
