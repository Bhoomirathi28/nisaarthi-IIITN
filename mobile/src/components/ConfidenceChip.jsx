import { useT } from "../i18n";

// Colour plus a word plus a shape, so the label never depends on colour alone.
const MARK = { KNOWN: "●", PROBABLE: "◐", OUTDATED: "◌", UNKNOWN: "?" };

export default function ConfidenceChip({ label, small }) {
  const { t } = useT();
  const l = label || "UNKNOWN";
  return (
    <span className={`chip chip-${l.toLowerCase()} ${small ? "chip-sm" : ""}`} title={t(`${l}_d`)}>
      <span aria-hidden="true">{MARK[l]}</span> {t(l)}
    </span>
  );
}
