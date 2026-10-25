"""Builds the night plan: fetch routes and places (live, then cache, then mock), score every route,
attach confidence labels, and rank the safest feasible plan first."""
import asyncio
from datetime import datetime, timezone

from . import config
from .engine import confidence as C
from .engine import geo, scoring
from .services import cache, geoapify, mockdata, nebius, overpass, tavily, weather


def _thin(coords, max_points=400):
    if len(coords) <= max_points:
        return [list(c) for c in coords]
    step = len(coords) / max_points
    out = [list(coords[int(i * step)]) for i in range(max_points)]
    out.append(list(coords[-1]))
    return out


async def _with_fallback(key, live_fn, mock_fn):
    """live -> last cached copy -> mock. Returns (data, state)."""
    if not config.FORCE_MOCK:
        try:
            data = await live_fn()
            cache.put(key, data)
            return data, "live"
        except Exception:
            _, cached = cache.get(key)
            if cached is not None:
                return cached, "cached"
    data = mock_fn()
    return data, ("mock" if data else "none")


async def _routes(origin, dest, mode, stops=()):
    key = ("routes", mode) + tuple(round(x, 4) for pt in (origin, *stops, dest) for x in pt)
    return await _with_fallback(key, lambda: geoapify.routes(origin, dest, mode, stops),
                                lambda: mockdata.routes(origin, dest, mode, stops))


async def _places(bbox):
    key = ("places",) + tuple(round(x, 3) for x in bbox)
    return await _with_fallback(key, lambda: overpass.places(bbox), mockdata.places)


async def _weather(lat, lon):
    key = ("weather", round(lat, 2), round(lon, 2))
    data, state = await _with_fallback(key, lambda: weather.current(lat, lon), lambda: None)
    if data is None:
        return {"label": C.UNKNOWN}, "none"
    return {**data, "label": C.source_label(data["source"], data["fetched_at"], config.FRESH_MINUTES)}, state


async def _advisories():
    data, state = await _with_fallback(("advisories",), tavily.advisories, mockdata.advisories)
    for a in data or []:
        a["label"] = C.OUTDATED if a.get("source") == "mock" else C.PROBABLE
    return data or [], state


def _places_label(places):
    if not places:
        return C.UNKNOWN
    return C.worst({C.source_label(p.get("source"), p.get("fetched_at"), config.FRESH_MINUTES) for p in places})


async def plan(origin, dest, departure, deadline, mode, stops=()):
    now = datetime.now(timezone.utc)
    routes, routes_state = await _routes(origin, dest, mode, stops)
    bbox = geo.bbox([r["coords"] for r in routes], pad_deg=0.006)
    (places, places_state), (wx, wx_state), (adv, adv_state) = await asyncio.gather(
        _places(bbox), _weather(*dest), _advisories())

    if wx.get("label") == C.KNOWN and (departure - now).total_seconds() > 3600:
        wx["label"] = C.PROBABLE  # current weather used for a trip more than an hour away

    p_label = _places_label(places)
    scored = []
    for r in routes:
        r_label = C.source_label(r.get("source"), r.get("fetched_at"), config.FRESH_MINUTES)
        r = {**r, "route_label": r_label, "poi_label": p_label}
        res = scoring.score_route(r, places, departure, config.FRESH_MINUTES)
        res = scoring.apply_weather(res, wx)
        res["feasibility"] = scoring.feasibility(departure, res["duration_s"], deadline)
        res["reasons"] = scoring.reasons(res)
        res["type"] = r["type"]
        res["route_label"] = r_label
        res["coords"] = _thin(r["coords"])
        scored.append(res)

    ai = await nebius.score_routes(scored)
    for res, a in zip(scored, ai):
        res["ai"] = a if a else {"label": C.UNKNOWN}

    ranked = scoring.rank(scored)
    return {
        "generated_at": now.isoformat(),
        "departure": departure.isoformat(),
        "deadline": deadline.isoformat() if deadline else None,
        "mode": mode,
        "stops": [list(p) for p in stops],
        "routes": ranked,
        "weather": wx,
        "advisories": adv,
        "data_status": {"routes": routes_state, "places": places_state, "weather": wx_state,
                        "advisories": adv_state, "ai": "live" if any(ai) else "none"},
        "fresh_minutes": config.FRESH_MINUTES,
    }


async def help_nearby(lat, lon, at):
    pad = 0.02  # about 2 km
    bbox = (lat - pad, lon - pad, lat + pad, lon + pad)
    places, state = await _places(bbox)
    out = []
    for p in places:
        if p["kind"] not in ("police", "hospital", "pharmacy"):
            continue
        d = geo.haversine((lat, lon), (p["lat"], p["lon"]))
        if d > 3000:
            continue
        is_open, label = scoring.place_status(p, at, config.FRESH_MINUTES)
        out.append({**p, "distance_m": round(d), "open_now": is_open, "label": label})
    out.sort(key=lambda p: (p["kind"] != "police", p["distance_m"]))
    return {"places": out[:25], "state": state}


async def search_places(text, near=None):
    """Place search: live Geoapify -> cached copy -> sample places. Each result carries a label."""
    key = ("search", text.strip().lower(), *(round(x, 2) for x in near or ()))
    data, state = await _with_fallback(key, lambda: geoapify.autocomplete(text, near),
                                       lambda: mockdata.search(text))
    results = [{**p, "label": C.source_label(p.get("source"), p.get("fetched_at"), config.FRESH_MINUTES)}
               for p in data or []]
    return {"results": results, "state": state}
