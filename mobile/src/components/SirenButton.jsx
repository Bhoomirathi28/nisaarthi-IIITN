import { useState } from "react";
import { useT } from "../i18n";
import { sirenPlaying, startSiren, stopSiren } from "../lib/sos";

// Small round siren button for page headers. One tap starts, the next tap stops.
// No countdown: unlike the SOS SMS, a siren started by mistake does no harm.
export default function SirenButton() {
  const { t } = useT();
  // Keeps playing when the user moves between pages; the button on the next page shows it as on
  const [on, setOn] = useState(sirenPlaying());

  const toggle = () => {
    if (on) stopSiren(); else startSiren();
    setOn(!on);
  };

  return (
    <button type="button" className={`siren-btn${on ? " on" : ""}`} onClick={toggle}
      aria-pressed={on} aria-label={on ? t("siren_stop") : t("siren_play")}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M7 18v-6a5 5 0 0 1 10 0v6" /><path d="M5 18h14v3H5z" /><path d="M12 3v2M4.5 6.5l1.4 1.4M19.5 6.5l-1.4 1.4" />
      </svg>
      <span>{on ? t("siren_stop_short") : t("siren_short")}</span>
    </button>
  );
}
