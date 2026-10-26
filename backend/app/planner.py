"""Builds the night plan: fetch routes and places (live, then cache, then mock), score every route,
attach confidence labels, and rank the safest feasible plan first."""
import asyncio
import math
from collections import Counter
from datetime import datetime, timezone

from . import config
from .engine import confidence as C
from .engine import geo, scoring
from .services import cache, geoapify, mockdata, nebius, overpass, tavily, tomtom, weather

TILE_DEG = 0.03             # places are fetched and cached in squares about 3 km wide
CORRIDOR_DEG = 0.006        # about 600 m either side of a route
MAX_TILES = 24              # keeps a very long trip from using up the free API quota
ROADS_PER_ROUTE = 3
MIN_ROAD_M = 150            # ignore junction names and tiny stretches
ROAD_REPORT_CACHE_S = 7 * 24 * 3600
CLOSURES_CACHE_S = 3600
CCTV_RETRY_S = 10 * 60
CCTV_WAIT_S = 6
_cctv_failed_at = {}


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


# ---- Places: Geoapify -> Overpass -> saved copy, fetched per map square ----

def _tiles_near(points, pad=CORRIDOR_DEG):
    tiles = set()
    for lat, lon in points:
        for dla in (-pad, 0, pad):
            for dlo in (-pad, 0, pad):
                tiles.add((math.floor((lat + dla) / TILE_DEG), math.floor((lon + dlo) / TILE_DEG)))
    return sorted(tiles)


def _tile_box(tile):
    s, w = tile[0] * TILE_DEG, tile[1] * TILE_DEG
    return (s, w, s + TILE_DEG, w + TILE_DEG)


async def _tile_cctv(tile):
    """Cameras for one square from Overpass. None when unknown (Overpass busy)."""
    key = ("cctv", *tile)
    _, fresh = cache.get(key, config.PLACES_FRESH_MINUTES * 60)
    if fresh is not None:
        return fresh
    failed = _cctv_failed_at.get(tile)
    if failed and (datetime.now(timezone.utc) - failed).total_seconds() < CCTV_RETRY_S:
        return cache.get(key)[1]
    try:
        # Cameras are a bonus: never hold up a plan for long waiting on a busy Overpass
        cams = await asyncio.wait_for(overpass.cctv(_tile_box(tile)), CCTV_WAIT_S)
        cache.put(key, cams)
        return cams
    except Exception:
        _cctv_failed_at[tile] = datetime.now(timezone.utc)
        return cache.get(key)[1]


async def _tile_places(tile):
    """(places, cctv_known, state) for one square."""
    key = ("places", *tile)
    _, fresh = cache.get(key, config.PLACES_FRESH_MINUTES * 60)
    if fresh is not None:
        cams = await _tile_cctv(tile) if not fresh["cctv_known"] else []
        if cams is not None and not fresh["cctv_known"]:
            fresh = {"places": fresh["places"] + cams, "cctv_known": True}
            cache.put(key, fresh)
        return fresh["places"], fresh["cctv_known"], "live"
    if not config.FORCE_MOCK:
        box = _tile_box(tile)
        try:
            places, cams = await asyncio.gather(geoapify.places(box), _tile_cctv(tile))
            record = {"places": places + (cams or []), "cctv_known": cams is not None}
        except Exception:
            try:  # Overpass returns cameras too
                record = {"places": await overpass.places(box), "cctv_known": True}
            except Exception:
                record = None
        if record is not None:
            cache.put(key, record)
            return record["places"], record["cctv_known"], "live"
    _, old = cache.get(key)
    if old is not None:
        return old["places"], old["cctv_known"], "cached"
    return [], False, "none"


async def _places_along(point_lists):
    points = [p for pts in point_lists for p in pts[::5]] + [p for pts in point_lists for p in pts[-1:]]
    tiles = _tiles_near(points)[:MAX_TILES]
    results = await asyncio.gather(*[_tile_places(t) for t in tiles])
    places, seen = [], set()
    for ps, _, _ in results:
        for p in ps:
            if p["id"] not in seen:
                seen.add(p["id"])
                places.append(p)
    states = {s for _, _, s in results}
    state = "none" if states == {"none"} else "cached" if states - {"live"} else "live"
    cctv_known = all(k for _, k, s in results if s != "none") and state != "none"
    return places, cctv_known, state


# ---- Weather, reports ----

async def _weather(lat, lon):
    key = ("weather", round(lat, 2), round(lon, 2))
    data, state = await _with_fallback(key, lambda: weather.current(lat, lon), lambda: None)
    if data is None:
        return {"label": C.UNKNOWN}, "none"
    return {**data, "label": C.source_label(data["source"], data["fetched_at"], config.FRESH_MINUTES)}, state


def _main_roads(route):
    by_name = Counter()
    for s in route.get("steps") or []:
        if s.get("name"):
            by_name[s["name"]] += s.get("distance") or 0
    return [n for n, d in by_name.most_common(ROADS_PER_ROUTE) if d >= MIN_ROAD_M]


async def _road_reports(road):
    key = ("road-reports", road.lower(), config.CITY_NAME.lower())
    _, fresh = cache.get(key, ROAD_REPORT_CACHE_S)
    if fresh is not None:
        return fresh
    if not config.FORCE_MOCK:
        try:
            reports = await tavily.road_reports(road)
            cache.put(key, reports)
            return reports
        except Exception:
            pass
    return cache.get(key)[1] or []


async def _closures(demo):
    if demo and (config.FORCE_MOCK or not config.TAVILY_API_KEY):
        return [{**a, "label": C.OUTDATED, "published": None} for a in mockdata.advisories()], "mock"
    _, fresh = cache.get(("closures", config.CITY_NAME), CLOSURES_CACHE_S)
    if fresh is not None:
        return fresh, "live"
    data, state = await _with_fallback(("closures", config.CITY_NAME), tavily.closures, lambda: [])
    return data, state


def _places_label(places):
    if not places:
        return C.UNKNOWN
    return C.worst({C.source_label(p.get("source"), p.get("fetched_at"), config.PLACES_FRESH_MINUTES)
                    for p in places})


def _police_on_route(scored_places):
    return [{k: p.get(k) for k in ("name", "lat", "lon", "phone", "distance_from_route_m", "position_m", "label")}
            for p in scored_places if p["kind"] == "police"]


# ---- The plan ----

async def plan(origin, dest, departure, deadline, mode, stops=()):
    now = datetime.now(timezone.utc)
    routes, routes_state = await _routes(origin, dest, mode, stops)
    demo = routes_state == "mock" and mockdata.is_demo_trip(origin, dest, stops)

    async def places_task():
        if demo:  # the sample trip uses the sample places, nothing else ever does
            return [{**p} for p in mockdata.places()], True, "mock"
        return await _places_along([r["coords"] for r in routes])

    roads = sorted({road for r in routes for road in _main_roads(r)})
    (places, cctv_known, places_state), (wx, wx_state), (closures, closures_state), reports, traffic = \
        await asyncio.gather(
            places_task(), _weather(*dest), _closures(demo),
            asyncio.gather(*[_road_reports(road) for road in roads]),
            asyncio.gather(*[tomtom.route_traffic(r["coords"], departure, mode, now) for r in routes]))
    reports_by_road = dict(zip(roads, reports))

    if wx.get("label") == C.KNOWN and (departure - now).total_seconds() > 3600:
        wx["label"] = C.PROBABLE  # current weather used for a trip more than an hour away

    p_label = _places_label(places) if places_state != "none" else C.UNKNOWN
    scored = []
    for r, tr in zip(routes, traffic):
        r_label = C.source_label(r.get("source"), r.get("fetched_at"), config.FRESH_MINUTES)
        duration = r.get("duration_s")
        if tr and duration:
            duration = duration * tr["delay_factor"]
        r = {**r, "duration_s": duration, "route_label": r_label, "poi_label": p_label, "cctv_known": cctv_known}
        res = scoring.score_route(r, places, departure, config.PLACES_FRESH_MINUTES)
        res = scoring.apply_weather(res, wx)
        res["feasibility"] = scoring.feasibility(departure, res["duration_s"], deadline)
        res["reasons"] = scoring.reasons(res)
        res["type"] = r["type"]
        res["route_label"] = r_label
        res["coords"] = _thin(r["coords"])
        res["traffic"] = tr
        res["roads"] = _main_roads(r)
        res["road_reports"] = [x for road in res["roads"] for x in reports_by_road.get(road, [])]
        res["police_on_route"] = _police_on_route(res["places"])
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
        "advisories": closures,
        "data_status": {"routes": routes_state, "places": places_state, "weather": wx_state,
                        "advisories": closures_state, "ai": "live" if any(ai) else "none",
                        "traffic": (traffic[0] or {}).get("source", "none") if traffic else "none"},
        "fresh_minutes": config.FRESH_MINUTES,
    }


async def help_nearby(lat, lon, at):
    if mockdata.is_demo_area((lat, lon)) and config.FORCE_MOCK:
        places, state = mockdata.places(), "mock"
    else:
        # The squares covering about 2 km around the worker
        around = [(lat + dy, lon + dx) for dy in (-0.02, 0, 0.02) for dx in (-0.02, 0, 0.02)]
        places, _, state = await _places_along([around])
        if state == "none" and mockdata.is_demo_area((lat, lon)):
            places, state = mockdata.places(), "mock"
    out = []
    for p in places:
        if p["kind"] not in ("police", "hospital", "pharmacy"):
            continue
        d = geo.haversine((lat, lon), (p["lat"], p["lon"]))
        if d > 3000:
            continue
        is_open, label = scoring.place_status(p, at, config.PLACES_FRESH_MINUTES)
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
