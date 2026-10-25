import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";
import { api } from "../api";
import RouteMap from "../components/RouteMap";
import PlaceSearch from "../components/PlaceSearch";
import ScoreRing from "../components/ScoreRing";
import ConfidenceChip from "../components/ConfidenceChip";
import SpacingStrip from "../components/SpacingStrip";
import { aged } from "../lib/labels";
import { getLocation, openUrl } from "../lib/native";
import { clock, metres, minutesSince } from "../lib/time";

const REPLAN_MS = 2 * 60 * 1000;
const MODES = ["walk", "motorcycle", "drive"];
const MAX_STOPS = 3;

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

export default function Plan({ trip, setTrip, plan, planning, error, online, home, setHome, runPlan }) {
  const { t } = useT();
  const [editing, setEditing] = useState(!plan);
  const [sel, setSel] = useState(0);
  const [, tick] = useState(0);
  const [here, setHere] = useState(null);
  const [picking, setPicking] = useState(null); // which field "Choose on map" is filling
  const [formError, setFormError] = useState(null);
  const mapRef = useRef(null);

  // Show where the worker is now while they fill in the trip
  useEffect(() => {
    if (editing && trip.originMode === "gps") getLocation().then(setHere);
  }, [editing, trip.originMode]);

  // Keep re-planning while this screen is open and a plan exists
  useEffect(() => {
    if (!plan || editing) return;
    const id = setInterval(() => runPlan(plan.trip || trip, { quiet: true }), REPLAN_MS);
    const clockId = setInterval(() => tick((n) => n + 1), 30000);
    return () => { clearInterval(id); clearInterval(clockId); };
  }, [plan, editing, runPlan]);

  useEffect(() => { setSel(0); }, [plan?.generated_at]);

  const update = (patch) => { setFormError(null); setTrip({ ...trip, demo: false, ...patch }); };
  const stops = trip.stops || [];
  const setStop = (i, p) => update({ stops: stops.map((s, j) => (j === i ? p : s)) });
  const placeName = (p) => (p ? p.name || t("pinned") : "");

  const setField = (field, p) => {
    if (field === "origin") update({ originMode: "fixed", origin: p });
    else if (field === "destination") update({ destination: p });
    else setStop(field, p);
  };
  const fieldLabel = (field) =>
    field === "origin" ? t("from") : field === "destination" ? t("to") : t("stop_n", { n: field + 1 });

  const chooseOnMap = (field) => {
    setPicking(field);
    mapRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const onMapTap = (pt) => {
    if (picking == null) return;
    setField(picking, { lat: pt.lat, lon: pt.lon, name: null });
    setPicking(null);
  };

  const useDemo = async () => {
    try {
      const d = await api.demo();
      setFormError(null);
      setTrip({ ...trip, originMode: "fixed", origin: d.origin, destination: d.destination, stops: [],
        shiftEnd: d.shift_end, reachBy: d.reach_by, mode: d.mode, demo: true });
    } catch {
      setFormError("server_down");
    }
  };

  const submit = async () => {
    if (!trip.destination) return setFormError("no_dest");
    if (stops.some((s) => !s)) return setFormError("err_stop_empty");
    if (trip.reachBy && trip.reachBy === trip.shiftEnd) return setFormError("err_same_time");
    setPicking(null);
    // On a network failure the last saved plan is shown with a banner, so only stay here for input problems
    if ((await runPlan(trip)) !== "invalid") setEditing(false);
  };

  const routes = plan?.routes || [];
  const r = routes[sel];
  const label = (l) => aged(l, plan?.generated_at, plan?.fresh_minutes);
  const age = plan ? minutesSince(plan.generated_at) : 0;
  const origin = plan?.trip?.origin || trip.origin;
  const dest = plan?.trip?.destination || trip.destination;

  if (editing || !plan) {
    const start = trip.originMode === "fixed" ? trip.origin : here;
    return (
      <div className="plan">
        <h1 className="screen-title">{t("plan_route")}</h1>
        <div ref={mapRef} className="map-wrap">
          <RouteMap origin={start} stops={stops} destination={trip.destination} onPick={onMapTap}
            picking={picking != null} height={220} />
          {picking != null && (
            <div className="map-pick-bar">
              <span>{t("tap_map_for", { field: fieldLabel(picking) })}</span>
              <button className="btn btn-text" onClick={() => setPicking(null)}>{t("cancel")}</button>
            </div>
          )}
        </div>

        <div className="panel form">
          <PlaceSearch id="trip-from" label={t("from")} near={here}
            display={trip.originMode === "gps" ? t("my_location") : placeName(trip.origin)}
            topOption={{ label: t("use_my_location"), onPick: () => update({ originMode: "gps", origin: null }) }}
            onSelect={(p) => setField("origin", p)} onChooseMap={() => chooseOnMap("origin")} />

          {stops.length > 0 && <span className="field-label stops-label">{t("stops_label")}</span>}
          {stops.map((s, i) => (
            <PlaceSearch key={i} id={`trip-stop-${i}`} label={t("stop_n", { n: i + 1 })} near={here}
              display={placeName(s)} onSelect={(p) => setStop(i, p)} onChooseMap={() => chooseOnMap(i)}
              onRemove={() => update({ stops: stops.filter((_, j) => j !== i) })}
              removeLabel={t("remove_stop", { n: i + 1 })} />
          ))}
          {stops.length < MAX_STOPS && (
            <button className="btn btn-text add-stop" onClick={() => update({ stops: [...stops, null] })}>
              + {t("add_stop")}
            </button>
          )}

          <PlaceSearch id="trip-to" label={t("to")} near={here} display={placeName(trip.destination)}
            onSelect={(p) => setField("destination", p)} onChooseMap={() => chooseOnMap("destination")} />
          <div className="row-gap">
            {home && <button className="btn btn-ghost" onClick={() => update({ destination: home })}>{t("use_home")}</button>}
            {trip.destination && !trip.demo && <button className="btn btn-ghost" onClick={() => setHome(trip.destination)}>{t("save_home")}</button>}
          </div>

          <div className="two-col">
            <label>
              <span className="field-label">{t("departure")}</span>
              <input type="time" value={trip.shiftEnd} onChange={(e) => update({ shiftEnd: e.target.value })} />
            </label>
            <label>
              <span className="field-label">{t("arrive_by")}</span>
              <input type="time" value={trip.reachBy} onChange={(e) => update({ reachBy: e.target.value })} />
            </label>
          </div>
          <fieldset className="segmented">
            <legend className="field-label">{t("mode")}</legend>
            {MODES.map((m) => (
              <label key={m} className={trip.mode === m ? "on" : ""}>
                <input type="radio" name="mode" value={m} checked={trip.mode === m} onChange={() => update({ mode: m })} />
                {t(`mode_${m}`)}
              </label>
            ))}
          </fieldset>
          {(formError || error) && <p className="banner" role="alert">{t(formError || error)}</p>}
          <button className="btn btn-primary btn-block btn-big" onClick={submit} disabled={planning || !trip.destination}>
            {planning ? t("finding") : t("search_routes")}
          </button>
          {!trip.destination && <p className="muted small center">{t("no_dest")}</p>}
          <button className="btn btn-text" onClick={useDemo}>{t("use_demo")}</button>
        </div>
      </div>
    );
  }

  return (
    <div className="plan">
      <div className="row-between">
        <h1 className="screen-title">{t("plan_route")}</h1>
        <button className="btn btn-text" onClick={() => setEditing(true)}>{t("edit_trip")}</button>
      </div>
      {(!online || error) && <p className="banner">{t(online ? error : "offline_banner")}</p>}

      <RouteMap routes={routes} selected={sel} origin={origin} destination={dest} />

      {r && (
        <section className="panel panel-framed result">
          <div className="result-head">
            <ScoreRing value={r.reliability} />
            <div className="result-meta">
              {sel === 0 && <p className="tag">{t("recommended")}</p>}
              <h2>{t(`route_${r.type}`)}</h2>
              <p>{t("arrive", { time: clock(r.feasibility.arrival) })} · {metres(r.length_m)}</p>
              {r.feasibility.buffer_min == null ? (
                <p className="muted small">{t("no_deadline")}</p>
              ) : r.feasibility.feasible ? (
                <p className="ok">{t("buffer_ok", { min: r.feasibility.buffer_min })}</p>
              ) : (
                <p className="late">{t("buffer_late", { min: -r.feasibility.buffer_min })}</p>
              )}
            </div>
          </div>
          <div className="row-between small">
            <span className="muted">{t("reliability")}</span>
            <ConfidenceChip label={label(r.confidence)} small />
          </div>

          <h3>{t("open_places_strip")}</h3>
          <SpacingStrip spacing={r.factors.spacing} />

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
        </section>
      )}

      {routes.length > 1 && (
        <section>
          <h3>{t("other_routes")}</h3>
          <div className="route-list">
            {routes.map((x, i) => i !== sel && (
              <button key={i} className="panel route-row" onClick={() => setSel(i)}>
                <ScoreRing value={x.reliability} size={48} />
                <span>
                  <strong>{t(`route_${x.type}`)}</strong>
                  <span className="muted small"> · {clock(x.feasibility.arrival)} · {metres(x.length_m)}</span>
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

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
          <h3>{t("advisories")}</h3>
          <ul className="advisories">
            {plan.advisories.map((a, i) => (
              <li key={i}>
                {a.url ? <button className="link" onClick={() => openUrl(a.url)}>{a.title}</button> : <span>{a.title}</span>}
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
        {plan.data_status?.routes === "mock" && <p className="muted small">{t("sample_note")}</p>}
      </section>

      <p className="muted small center">
        {t("updated", { ago: age < 1 ? t("just_now") : t("min_ago", { n: age }) })}. {t("replanning")}
      </p>
    </div>
  );
}
