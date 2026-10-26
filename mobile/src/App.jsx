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

const DEFAULT_SETTINGS = { server: "", shake: true, sirenAuto: true };
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
    })();
    return onNetworkChange(setOnline);
  }, []);

  // Retry anything unsynced when the internet comes back
  useEffect(() => {
    if (online && session && (session.pending || session.contactsDirty)) {
      syncSession(session, contacts).then(setSession);
    }
  }, [online]);

  useEffect(() => {
    if (!ready || !settings.shake) return;
    return onShake(() => setSos(true));
  }, [ready, settings.shake]);

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
      return "ok";
    } catch {
      setPlanError((await isOnline()) ? "server_down" : "offline_banner");
      return "failed";
    } finally {
      setPlanning(false);
    }
  }, [trip]);

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
              onEdit={() => { setPlanError(null); setRouteView("trip"); }} />
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
        {sos && <SosOverlay contacts={contacts} sirenAuto={settings.sirenAuto} onClose={() => setSos(false)} />}
      </div>
    </LangContext.Provider>
  );
}
