import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";
import RouteMap from "../components/RouteMap";
import ScoreRing from "../components/ScoreRing";
import ConfidenceChip from "../components/ConfidenceChip";
import CoverageStrip from "../components/CoverageStrip";
import SirenButton from "../components/SirenButton";
import { IconPhone, IconPin } from "../components/Icons";
import { aged } from "../lib/labels";
import { openUrl } from "../lib/native";
import { call } from "../lib/sos";
import { clock, metres, minutesSince } from "../lib/time";

const REPLAN_MS = 2 * 60 * 1000;

function bookingLinks(o, d) {
  return [
    { name: "Uber", url: `https://m.uber.com/ul/?action=setPickup&pickup[latitude]=${o.lat}&pickup[longitude]=${o.lon}&dropoff[latitude]=${d.lat}&dropoff[longitude]=${d.lon}` },
    { name: "Ola", url: `https://book.olacabs.com/?lat=${o.lat}&lng=${o.lon}&drop_lat=${d.lat}&drop_lng=${d.lon}` },
    { name: "Rapido", url: "https://www.rapido.bike/" },
  ];
}

function weatherText(w, t) {
  if (!w || w.label === "UNKNOWN") return null;
  if (w.thunderstorm) return t("w_storm");
  if (w.heavy_rain) return t("w_heavy");
  if (w.rain) return t("w_rain");
  if (w.fog) return t("w_fog");
  return t("w_clear");
}

// "12 Oct 2026", or "date unknown", so an old story is never read as a recent one
function reportDate(iso, t) {
  if (!iso) return t("date_unknown");
  return new Date(`${iso}T00:00:00`).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}

function Deadline({ f, t }) {
  if (f.buffer_min == null) return <span className="muted small">{t("no_deadline")}</span>;
  return f.feasible
    ? <span className="ok">{t("buffer_ok", { min: f.buffer_min })}</span>
    : <span className="late">{t("buffer_late", { min: -f.buffer_min })}</span>;
}

function RouteDetails({ r, label, t }) {
  const roads = r.roads || [];
  return (
    <div className="route-details">
      <h3>{t("open_places_strip")}</h3>
      <CoverageStrip coverage={r.factors.coverage} />

      <h3>{t("why")}</h3>
      <ul className="reasons">
        {r.reasons.map((x) => (
          <li key={x.code} className={`reason-${x.tone}`}>{t(x.code, x.value || {})}</li>
        ))}
      </ul>
      <dl className="factors">
        {Object.entries(r.factors).map(([k, f]) => (
          <div key={k}>
            <dt>{t(`f_${k}`)}</dt>
            <dd>
              <span className="bar"><span style={{ width: `${(f.score ?? 0) * 100}%` }} /></span>
              <ConfidenceChip label={label(f.label)} small />
            </dd>
          </div>
        ))}
      </dl>
      {r.weather_penalty ? <p className="muted small">{t("w_penalty", { n: r.weather_penalty })}</p> : null}

      {r.traffic && (
        <div className="detail-block">
          <div className="row-between">
            <h3>{t("traffic")}</h3>
            <ConfidenceChip label={label(r.traffic.label)} small />
          </div>
          <p>{t(`traffic_${r.traffic.level}`)}{r.traffic.source === "estimate" ? ` · ${t("traffic_estimate")}` : ""}</p>
          {r.traffic.closures > 0 && <p className="late small">{t("traffic_closed", { n: r.traffic.closures })}</p>}
        </div>
      )}

      <div className="detail-block">
        <h3>{t("road_reports")}</h3>
        {r.road_reports?.length ? (
          <ul className="advisories">
            {r.road_reports.map((a, i) => (
              <li key={i}>
                <span>
                  <span className="report-meta">{a.road} · {reportDate(a.published, t)}</span>
                  {a.url ? <button className="link" onClick={() => openUrl(a.url)}>{a.title}</button> : <span>{a.title}</span>}
                </span>
                <ConfidenceChip label={a.label} small />
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted small">{roads.length ? t("no_reports", { roads: roads.join(", ") }) : t("no_road_names")}</p>
        )}
      </div>

      <div className="detail-block">
        <h3>{t("police_on_way")}</h3>
        {r.police_on_route?.length ? (
          <ul className="police-list">
            {r.police_on_route.slice(0, 4).map((p, i) => (
              <li key={i}>
                <span>
                  <strong>{p.name || t("k_police")}</strong>
                  <span className="muted small"> · {t("from_route", { m: metres(p.distance_from_route_m) })}</span>
                </span>
                <span className="row-gap">
                  <button className="btn btn-ghost" onClick={() => call(p.phone || "112")}><IconPhone /> {p.phone ? t("call") : t("call112")}</button>
                  <button className="btn btn-ghost" onClick={() => openUrl(`geo:${p.lat},${p.lon}?q=${p.lat},${p.lon}`)}><IconPin /> {t("directions")}</button>
                </span>
              </li>
            ))}
          </ul>
        ) : <p className="muted small">{t("no_police_on_way")}</p>}
      </div>

      <div className="ai-box">
        <span className="field-label">{t("ai_score")}</span>
        {r.ai && r.ai.safety_score != null ? (
          <>
            <p>{t("ai_safety", { n: r.ai.safety_score })} · {t("ai_feas", { n: r.ai.feasibility_score })}</p>
            {r.ai.note && <p className="muted small">{r.ai.note}</p>}
          </>
        ) : <p className="muted small">{t("ai_off")}</p>}
        <ConfidenceChip label={r.ai?.label || "UNKNOWN"} small />
      </div>
    </div>
  );
}

// Phase 3: all routes ranked safest-feasible first. Tap a card to see why.
export default function Routes({ plan, error, online, runPlan, onEdit }) {
  const { t } = useT();
  const [sel, setSel] = useState(0);
  const [, tick] = useState(0);
  const cardRefs = useRef([]);

  // Keep re-planning from the current location while this page is open
  useEffect(() => {
    const id = setInterval(() => runPlan(plan.trip, { quiet: true }), REPLAN_MS);
    const clockId = setInterval(() => tick((n) => n + 1), 30000);
    return () => { clearInterval(id); clearInterval(clockId); };
  }, [plan, runPlan]);

  useEffect(() => { setSel(0); }, [plan.generated_at]);

  const pick = (i) => {
    setSel(i);
    requestAnimationFrame(() => cardRefs.current[i]?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };

  const routes = plan.routes || [];
  const label = (l) => aged(l, plan.generated_at, plan.fresh_minutes);
  const age = minutesSince(plan.generated_at);
  const origin = plan.trip?.origin;
  const dest = plan.trip?.destination;
  const stops = (plan.trip?.stops || []).filter(Boolean);

  return (
    <div className="plan routes-page">
      <div className="page-head">
        <h1 className="screen-title">{t("routes_title")}</h1>
        <SirenButton />
      </div>
      <div className="row-between">
        <p className="muted small">{t("updated", { ago: age < 1 ? t("just_now") : t("min_ago", { n: age }) })} · {t("replanning")}</p>
        <button className="btn btn-text" onClick={onEdit}>{t("edit_trip")}</button>
      </div>
      {(!online || error) && <p className="banner">{t(online ? error : "offline_banner")}</p>}

      <RouteMap routes={routes} selected={sel} origin={origin} stops={stops} destination={dest} />

      <ol className="route-cards">
        {routes.map((r, i) => {
          const cov = r.factors.coverage;
          const unknown = cov?.value?.unknown_hours || 0;
          const open = i === sel;
          return (
            <li key={`${r.type}-${i}`} ref={(el) => { cardRefs.current[i] = el; }}
              className={`panel route-card${open ? " panel-framed open" : ""}`}>
              <button className="route-card-head" onClick={() => pick(i)} aria-expanded={open}>
                <ScoreRing value={r.reliability} size={open ? 76 : 60} />
                <span className="route-card-meta">
                  {i === 0 && r.feasibility.feasible !== false && <span className="tag">{t("recommended")}</span>}
                  <strong className="route-name">{t(`route_${r.type}`)}</strong>
                  <span>{t("arrive", { time: clock(r.feasibility.arrival) })} · {metres(r.length_m)}</span>
                  <Deadline f={r.feasibility} t={t} />
                </span>
                <ConfidenceChip label={label(r.confidence)} small />
              </button>
              {!open && <CoverageStrip coverage={cov} compact />}
              <p className="card-facts small">
                {cov?.score != null && <span>{t("covered_pct", { pct: Math.round(cov.value.covered_share * 100) })}</span>}
                {unknown > 0 && <span className="unknown-hours">◌ {t("unknown_hours", { n: unknown })}</span>}
                {r.factors.cctv?.score != null && <span>{t("cameras_at", { n: r.factors.cctv.value.count })}</span>}
              </p>
              {open && <RouteDetails r={r} label={label} t={t} />}
            </li>
          );
        })}
      </ol>

      <section className="panel">
        <h3>{t("book_ride")}</h3>
        <div className="row-gap">
          {origin && dest && bookingLinks(origin, dest).map((b) => (
            <button key={b.name} className="btn btn-ghost" onClick={() => openUrl(b.url)}>{b.name}</button>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="row-between">
          <h3>{t("weather")}</h3>
          <ConfidenceChip label={label(plan.weather?.label)} small />
        </div>
        <p>{weatherText(plan.weather, t) || t("UNKNOWN_d")}</p>
      </section>

      {plan.advisories?.length > 0 && (
        <section className="panel">
          <h3>{t("closures")}</h3>
          <ul className="advisories">
            {plan.advisories.map((a, i) => (
              <li key={i}>
                <span>
                  <span className="report-meta">{reportDate(a.published, t)}</span>
                  {a.url ? <button className="link" onClick={() => openUrl(a.url)}>{a.title}</button> : <span>{a.title}</span>}
                </span>
                <ConfidenceChip label={a.label} small />
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="panel legend">
        <h3>{t("labels_title")}</h3>
        {["KNOWN", "PROBABLE", "OUTDATED", "UNKNOWN"].map((l) => (
          <p key={l}><ConfidenceChip label={l} small /> <span className="muted small">{t(`${l}_d`)}</span></p>
        ))}
      </section>
    </div>
  );
}
