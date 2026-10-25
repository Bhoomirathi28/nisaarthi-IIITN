import { useEffect, useState } from "react";
import { useT } from "../i18n";
import { api } from "../api";
import ConfidenceChip from "../components/ConfidenceChip";
import { IconPhone, IconPin } from "../components/Icons";
import { getLocation, load, openUrl, save } from "../lib/native";
import { call } from "../lib/sos";
import { metres } from "../lib/time";

export default function Help({ online }) {
  const { t } = useT();
  const [places, setPlaces] = useState(null);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      const cached = await load("lastHelp", null);
      if (cached) { setPlaces(cached.places); setStale(true); }
      const loc = await getLocation();
      if (!loc) { setError("location_denied"); return; }
      try {
        const res = await api.help(loc.lat, loc.lon);
        setPlaces(res.places); setStale(false);
        save("lastHelp", { places: res.places, at: new Date().toISOString() });
      } catch {
        setError(online ? "server_down" : "offline_banner");
      }
    })();
  }, []);

  const status = (p) => p.open_now === true ? t("open_now") : p.open_now === false ? t("closed_now") : t("hours_unknown");

  return (
    <div className="help">
      <h1 className="screen-title">{t("nav_help")}</h1>
      <button className="btn btn-sos btn-block btn-big" onClick={() => call("112")}>
        <IconPhone /> {t("call112")}
      </button>
      {error && <p className="banner">{t(error)}</p>}
      {places === null && !error && <p className="muted">{t("loading")}</p>}
      {places && places.length === 0 && <p className="muted">{t("no_help")}</p>}
      <ul className="help-list">
        {(places || []).map((p) => (
          <li key={p.id} className="panel help-item">
            <div className="row-between">
              <span className={`kind kind-${p.kind}`}>{t(`k_${p.kind}`)}</span>
              <ConfidenceChip label={stale && p.label === "KNOWN" ? "OUTDATED" : p.label} small />
            </div>
            <p className="help-name">{p.name || t(`k_${p.kind}`)}</p>
            <p className="muted small">{metres(p.distance_m)} · {status(p)}</p>
            <div className="row-gap">
              {p.phone && <button className="btn btn-ghost" onClick={() => call(p.phone)}><IconPhone /> {t("call")}</button>}
              <button className="btn btn-ghost" onClick={() => openUrl(`geo:${p.lat},${p.lon}?q=${p.lat},${p.lon}`)}>
                <IconPin /> {t("directions")}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
