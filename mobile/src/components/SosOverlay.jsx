import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";
import { getLocation } from "../lib/native";
import { call, sendSosSms, startSiren, stopSiren } from "../lib/sos";
import { cancelSos, stopNativeSiren } from "../lib/shakeSos";

// SOS started by the native shake service (Phase 4): the phone itself counts down, sends the SMS
// and plays the siren, even with the app closed. This screen mirrors it and controls it.
function NativeSos({ contacts, native, onClose }) {
  const { t } = useT();
  const loc = native.lat != null ? { lat: native.lat, lon: native.lon } : null;
  const body = () => (loc ? t("sms_body", { lat: loc.lat.toFixed(6), lon: loc.lon.toFixed(6) }) : t("sms_no_loc"));

  if (native.state === "countdown") {
    return (
      <div className="sos-overlay" role="alertdialog" aria-modal="true" aria-live="assertive">
        <p className="sos-count" aria-hidden="true">{native.secondsLeft}</p>
        <p className="sos-msg">{t("sending_in", { n: native.secondsLeft })}</p>
        <button className="btn btn-ghost btn-big" onClick={() => { cancelSos(); onClose(); }}>{t("cancel")}</button>
      </div>
    );
  }
  return (
    <div className="sos-overlay" role="alertdialog" aria-modal="true" aria-live="assertive">
      <h2 className="sos-title">{t("sos_sent_title")}</h2>
      <p className="sos-msg">
        {native.sent > 0 ? t("sos_sent_n", { n: native.sent }) : t("sos_sms_failed")}
      </p>
      {loc ? <p className="sos-loc">{loc.lat.toFixed(5)}, {loc.lon.toFixed(5)}</p>
           : native.sent != null && <p className="sos-msg">{t("sms_no_loc")}</p>}
      <div className="sos-actions">
        <button className="btn btn-sos btn-big" onClick={() => call("112")}>{t("call112")}</button>
        {native.sent === 0 && contacts.length > 0 && (
          // Automatic sending failed (no SMS permission or no signal): open the SMS app instead
          <button className="btn btn-primary btn-big" onClick={() => sendSosSms(contacts, body())}>{t("send_sms")}</button>
        )}
        {native.siren && (
          <button className="btn btn-big btn-siren on" onClick={stopNativeSiren} aria-pressed="true">{t("siren_stop")}</button>
        )}
        <button className="btn btn-text" onClick={onClose}>{t("close")}</button>
      </div>
    </div>
  );
}

// 5-second countdown first, so an accidental shake can be cancelled.
export default function SosOverlay({ contacts, sirenAuto, native, onClose }) {
  if (native) return <NativeSos contacts={contacts} native={native} onClose={onClose} />;
  return <WebSos contacts={contacts} sirenAuto={sirenAuto} onClose={onClose} />;
}

// SOS started inside the app (SOS button, or a shake while the app is open and no trip service runs)
function WebSos({ contacts, sirenAuto, onClose }) {
  const { t } = useT();
  const [count, setCount] = useState(5);
  const [fired, setFired] = useState(false);
  const [loc, setLoc] = useState(null);
  const [siren, setSiren] = useState(false);
  const locRef = useRef(null);

  useEffect(() => {
    getLocation().then((l) => { locRef.current = l; setLoc(l); });
    return () => stopSiren();
  }, []);

  useEffect(() => {
    if (fired) return;
    if (count === 0) { fire(); return; }
    const id = setTimeout(() => setCount((c) => c - 1), 1000);
    return () => clearTimeout(id);
  }, [count, fired]);

  const body = () => {
    const l = locRef.current;
    return l ? t("sms_body", { lat: l.lat.toFixed(6), lon: l.lon.toFixed(6) }) : t("sms_no_loc");
  };

  function fire() {
    setFired(true);
    if (sirenAuto) { startSiren(); setSiren(true); }
    if (contacts.length) sendSosSms(contacts, body());
  }

  const toggleSiren = () => {
    if (siren) stopSiren(); else startSiren();
    setSiren(!siren);
  };

  return (
    <div className="sos-overlay" role="alertdialog" aria-modal="true" aria-live="assertive">
      {!fired ? (
        <>
          <p className="sos-count" aria-hidden="true">{count}</p>
          <p className="sos-msg">{t("sending_in", { n: count })}</p>
          <button className="btn btn-ghost btn-big" onClick={onClose}>{t("cancel")}</button>
        </>
      ) : (
        <>
          <h2 className="sos-title">{t("sos_sent_title")}</h2>
          {loc && <p className="sos-loc">{loc.lat.toFixed(5)}, {loc.lon.toFixed(5)}</p>}
          {!contacts.length && <p className="sos-msg">{t("no_contacts_sos")}</p>}
          <div className="sos-actions">
            <button className="btn btn-sos btn-big" onClick={() => call("112")}>{t("call112")}</button>
            {contacts.length > 0 && (
              <button className="btn btn-primary btn-big" onClick={() => sendSosSms(contacts, body())}>
                {t("send_sms")}
              </button>
            )}
            <button className={`btn btn-big btn-siren${siren ? " on" : ""}`} onClick={toggleSiren} aria-pressed={siren}>
              {siren ? t("siren_stop") : t("siren_play")}
            </button>
            <button className="btn btn-text" onClick={onClose}>{t("close")}</button>
          </div>
        </>
      )}
    </div>
  );
}
