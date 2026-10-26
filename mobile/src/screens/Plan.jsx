import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";
import { api } from "../api";
import RouteMap from "../components/RouteMap";
import PlaceSearch from "../components/PlaceSearch";
import SirenButton from "../components/SirenButton";
import { getLocation } from "../lib/native";

const MODES = ["walk", "motorcycle", "drive"];
const MAX_STOPS = 3;

// Phase 2 trip page: where from, optional stops, where to, when. Search opens the routes page.
export default function Plan({ trip, setTrip, planning, error, home, setHome, runPlan, onDone }) {
  const { t } = useT();
  const [here, setHere] = useState(null);
  const [picking, setPicking] = useState(null); // which field "Choose on map" is filling
  const [formError, setFormError] = useState(null);
  const mapRef = useRef(null);

  // Show where the worker is now while they fill in the trip
  useEffect(() => {
    if (trip.originMode === "gps") getLocation().then(setHere);
  }, [trip.originMode]);

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
    // On a network failure the routes page shows the last saved plan with a banner,
    // so only stay here for problems the user has to fix
    if ((await runPlan(trip)) !== "invalid") onDone();
  };

  const start = trip.originMode === "fixed" ? trip.origin : here;
  return (
    <div className="plan">
      <div className="page-head">
        <h1 className="screen-title">{t("plan_route")}</h1>
        <SirenButton />
      </div>
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
