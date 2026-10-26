import { useCallback, useEffect, useMemo, useState } from "react";
import { LangContext, translate } from "./i18n";
import { api, setApiBase } from "./api";
import { getLocation, isOnline, load, onNetworkChange, onShake, save } from "./lib/native";
import { timeToDate, toLocalIso } from "./lib/time";
import BottomNav from "./components/BottomNav";
import SosOverlay from "./components/SosOverlay";
import Home from "./screens/Home";
import Plan from "./screens/Plan";
import Routes from "./screens/Routes";
import Help from "./screens/Help";
import Contacts from "./screens/Contacts";
import Settings from "./screens/Settings";
import SignUp from "./screens/SignUp";
import { createSession, loadSession, syncSession } from "./lib/session";
import { endTrip, onShakeEvents, shakeAvailable, startTrip, status as shakeStatus } from "./lib/shakeSos";

const DEFAULT_SETTINGS = { server: "", shake: true, sirenAuto: true, sensitivity: "normal" };
const ARRIVED_M = 150; // shake protection ends when a re-plan finds the worker this close to home

function metresBetween(a, b) {
  const r = Math.PI / 180, dLat = (b.lat - a.lat) * r, dLon = (b.lon - a.lon) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(h));
}
// Places are { lat, lon, name, address }; name is null for a spot picked on the map. Up to 3 stops, in order.
const DEFAULT_TRIP = { originMode: "gps", origin: null, destination: null, stops: [], shiftEnd: "02:15", reachBy: "03:00", mode: "walk", demo: false };

export default function App() {
  const [ready, setReady] = useState(false);
  const [lang, setLang] = useState("en");
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [contacts, setContacts] = useState([]);
  const [home, setHome] = useState(null);
  const [trip, setTrip] = useState(DEFAULT_TRIP);
  const [plan, setPlan] = useState(null);
  const [planError, setPlanError] = useState(null);
  const [planning, setPlanning] = useState(false);
  const [online, setOnline] = useState(true);
  const [tab, setTab] = useState("home");
  const [routeView, setRouteView] = useState("trip"); // the Route tab shows the trip page or the routes page
  const [sos, setSos] = useState(false);
  const [session, setSession] = useState(null);
  const [shake, setShake] = useState({ available: shakeAvailable, running: false }); // native shake-for-SOS status
  const [nativeSos, setNativeSos] = useState(null); // SOS started by the native service: countdown or sent

  // Load everything saved on the phone
  useEffect(() => {
    (async () => {
      const sess = await loadSession();
      const [l, s, c, h, p, tr] = await Promise.all([
        load("lang", "en"), load("settings", DEFAULT_SETTINGS), load("contacts", []),
        load("home", null), load("lastPlan", null), load("trip", DEFAULT_TRIP),
      ]);
      setLang(l); setSettings({ ...DEFAULT_SETTINGS, ...s }); setContacts(c); setHome(h); setPlan(p);
      if (p?.trip && p.routes?.[0]?.factors?.coverage) setRouteView("routes"); // skip plans saved by older versions
      setTrip({ ...DEFAULT_TRIP, ...tr });
      setApiBase(s.server);
      setOnline(await isOnline());
      setSession(sess);
      if (sess) setTab("plan");
      setReady(true);
      if (sess) setSession(await syncSession(sess, c));
      // Opened by an SOS from the background service: show where it is
      const st = await shakeStatus();
      setShake(st);
      if (st.sos === "countdown" || st.sos === "sent") setNativeSos({ state: st.sos, secondsLeft: st.secondsLeft, siren: st.siren });
    })();
    return onNetworkChange(setOnline);
  }, []);

  // Retry anything unsynced when the internet comes back
  useEffect(() => {
    if (online && session && (session.pending || session.contactsDirty)) {
      syncSession(session, contacts).then(setSession);
    }
  }, [online]);

  // In-app shake detector. While the native trip service runs, it handles shakes instead (no double SOS).
  useEffect(() => {
    if (!ready || !settings.shake || shake.running) return;
    return onShake(() => setSos(true));
  }, [ready, settings.shake, shake.running]);

  // Events from the native shake service
  useEffect(() => onShakeEvents({
    sos: (e) => setNativeSos((prev) => (e.state === "cancelled" ? null : { ...prev, ...e })),
    siren: (e) => setNativeSos((prev) => (prev ? { ...prev, siren: e.playing } : prev)),
    trip: () => shakeStatus().then(setShake),
  }), []);

  const t = useCallback((k, v) => translate(lang, k, v), [lang]);
  const ctx = useMemo(() => ({ lang, t }), [lang, t]);

  const persist = (key, setter) => (value) => { setter(value); save(key, value); };
  const updateLang = persist("lang", setLang);
  const updateContacts = async (list) => {
    setContacts(list);
    save("contacts", list);
    if (!session) return;
    const dirty = { ...session, contactsDirty: !session.pending };
    await save("session", dirty);
    setSession(await syncSession(dirty, list));
  };

  const finishSignUp = async (details) => {
    const s = await createSession(details);
    setSession(s);
    setContacts(await load("contacts", []));
    setTab("plan");
    setSession(await syncSession(s, details.contacts));
  };
  const updateHome = persist("home", setHome);
  const updateTrip = persist("trip", setTrip);
  const updateSettings = (s) => { setSettings(s); save("settings", s); setApiBase(s.server); };

  // Shake protection runs only during a trip: from Search routes until End trip, arrival, or the service's time limit
  const startProtection = async (p, st = settings) => {
    if (!shakeAvailable || !st.shake) return;
    setShake(await startTrip({ contacts, settings: st, plan: p, t: (k, v) => translate(lang, k, v) }));
  };
  const stopProtection = async () => { await endTrip(); setShake(await shakeStatus()); };
  const refreshShake = async () => setShake(await shakeStatus());

  // A settings change during a trip applies straight away
  useEffect(() => {
    if (!shake.running) return;
    if (!settings.shake) stopProtection();
    else startProtection(plan, settings);
  }, [settings.shake, settings.sensitivity, settings.sirenAuto]);

  // Build and send a plan request. Used for the first plan and every 2-minute re-plan.
  // Returns "ok", "invalid" (fix the trip first) or "failed" (network or server).
  const runPlan = useCallback(async (tr = trip, { quiet = false } = {}) => {
    if (!tr.destination) { setPlanError("no_dest"); return "invalid"; }
    let origin = tr.origin;
    if (tr.originMode === "gps") {
      origin = await getLocation();
      if (!origin) { setPlanError("location_denied"); return "invalid"; }
    }
    const dep = timeToDate(tr.shiftEnd);
    const deadline = tr.reachBy ? timeToDate(tr.reachBy, dep) : null;
    // Re-plans start from now if the shift has already ended
    const departure = dep && dep > new Date() ? dep : new Date();
    if (!quiet) setPlanning(true);
    setPlanError(null);
    try {
      const res = await api.plan({
        origin: { lat: origin.lat, lon: origin.lon },
        destination: { lat: tr.destination.lat, lon: tr.destination.lon },
        stops: (tr.stops || []).filter(Boolean).map((p) => ({ lat: p.lat, lon: p.lon })),
        mode: tr.mode,
        departure: toLocalIso(departure), deadline: deadline ? toLocalIso(deadline) : null,
      });
      const withTrip = { ...res, trip: { ...tr, origin } };
      setPlan(withTrip);
      save("lastPlan", withTrip);
      if (!quiet) startProtection(withTrip);  // a new search starts (or updates) shake protection
      else if (shake.running && metresBetween(origin, tr.destination) < ARRIVED_M) stopProtection();  // arrived
      return "ok";
    } catch {
      setPlanError((await isOnline()) ? "server_down" : "offline_banner");
      return "failed";
    } finally {
      setPlanning(false);
    }
  }, [trip, shake.running, settings, contacts, lang]);

  if (!ready) return <div className="app" />;

  if (!session) {
    return (
      <LangContext.Provider value={ctx}>
        <div className="app"><main className="screen screen-solo">
          <SignUp lang={lang} setLang={updateLang} onDone={finishSignUp} />
        </main></div>
      </LangContext.Provider>
    );
  }

  return (
    <LangContext.Provider value={ctx}>
      <div className="app">
        <main className="screen">
          {tab === "home" && (
            <Home plan={plan} online={online} sosHint={settings.shake ? "sos_hint" : "sos_hint_noshake"}
              onSos={() => setSos(true)} goPlan={() => { setRouteView("trip"); setTab("plan"); }}
              goRoutes={() => { setRouteView("routes"); setTab("plan"); }} goSettings={() => setTab("settings")} />
          )}
          {tab === "plan" && (routeView === "routes" && plan ? (
            <Routes plan={plan} error={planError} online={online} runPlan={runPlan}
              onEdit={() => { setPlanError(null); setRouteView("trip"); }}
              shake={shake} shakeOn={settings.shake} onEndTrip={stopProtection} onRefreshShake={refreshShake}
              onStartShake={() => startProtection(plan)} />
          ) : (
            <Plan trip={trip} setTrip={updateTrip} planning={planning} error={planError}
              home={home} setHome={updateHome} runPlan={runPlan} onDone={() => setRouteView("routes")} />
          ))}
          {tab === "help" && <Help online={online} />}
          {tab === "contacts" && <Contacts contacts={contacts} setContacts={updateContacts} />}
          {tab === "settings" && (
            <Settings lang={lang} setLang={updateLang} settings={settings} setSettings={updateSettings}
              onBack={() => setTab("home")} />
          )}
        </main>
        <BottomNav tab={tab} setTab={setTab} />
        {nativeSos ? (
          <SosOverlay contacts={contacts} native={nativeSos} onClose={() => setNativeSos(null)} />
        ) : sos && (
          <SosOverlay contacts={contacts} sirenAuto={settings.sirenAuto} onClose={() => setSos(false)} />
        )}
      </div>
    </LangContext.Provider>
  );
}
