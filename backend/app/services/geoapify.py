"""Geoapify: routing (three candidate routes: balanced, short, less_maneuvers) and place search."""
import asyncio
import re
from datetime import datetime, timezone

import httpx

from .. import config

URL = "https://api.geoapify.com/v1/routing"
AUTOCOMPLETE_URL = "https://api.geoapify.com/v1/geocode/autocomplete"
MODES = {"walk": "walk", "motorcycle": "motorcycle", "drive": "drive"}
TYPES = ["balanced", "short", "less_maneuvers"]


ONTO = re.compile(r"\b(?:onto|along|on)\s+(.+?)(?:\.|,|$)")


def _road_name(step):
    """Road name from the step, or from its instruction ("Turn left onto Great Nag Road.")."""
    if step.get("name"):
        return step["name"]
    m = ONTO.search((step.get("instruction") or {}).get("text") or "")
    return m.group(1).strip() if m else None


def _parse(feature, type_):
    props = feature["properties"]
    geom = feature["geometry"]
    lines = geom["coordinates"] if geom["type"] == "MultiLineString" else [geom["coordinates"]]
    coords = [(lat, lon) for line in lines for lon, lat in line]
    steps = []
    for leg in props.get("legs", []):
        for s in leg.get("steps", []):
            steps.append({"distance": s.get("distance", 0), "road_class": s.get("road_class"),
                          "name": _road_name(s)})
    return {
        "type": type_,
        "coords": coords,
        "distance_m": props.get("distance"),
        "duration_s": props.get("time"),
        "steps": steps,
        "turns": max(0, len(steps) - 1),
        "source": "live",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


async def _one(client, points, mode, type_):
    params = {
        "waypoints": "|".join(f"{lat},{lon}" for lat, lon in points),
        "mode": MODES.get(mode, "walk"),
        "type": type_,
        "details": "route_details",
        "apiKey": config.GEOAPIFY_API_KEY,
    }
    r = await client.get(URL, params=params)
    r.raise_for_status()
    feats = r.json().get("features") or []
    return _parse(feats[0], type_) if feats else None


async def routes(origin, dest, mode, stops=()):
    if not config.GEOAPIFY_API_KEY:
        raise RuntimeError("GEOAPIFY_API_KEY not set")
    points = [origin, *stops, dest]
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
        results = await asyncio.gather(*[_one(client, points, mode, t) for t in TYPES],
                                       return_exceptions=True)
    out, seen = [], set()
    for r in results:
        if isinstance(r, dict):
            key = round(r["distance_m"] or 0, -1)
            if key not in seen:  # drop duplicate routes
                seen.add(key)
                out.append(r)
    if not out:
        raise RuntimeError("no routes returned")
    return out


async def autocomplete(text, near=None, limit=6):
    """Places matching text, limited to SEARCH_RADIUS_KM around the city and ranked
    nearest to `near` (the user's position) or the city centre."""
    if not config.GEOAPIFY_API_KEY:
        raise RuntimeError("GEOAPIFY_API_KEY not set")
    bias_lat, bias_lon = near or (config.CITY_LAT, config.CITY_LON)
    params = {
        "text": text,
        "filter": f"circle:{config.CITY_LON},{config.CITY_LAT},{int(config.SEARCH_RADIUS_KM * 1000)}",
        "bias": f"proximity:{bias_lon},{bias_lat}",
        "limit": limit,
        "format": "json",
        "apiKey": config.GEOAPIFY_API_KEY,
    }
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
        r = await client.get(AUTOCOMPLETE_URL, params=params)
        r.raise_for_status()
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for res in r.json().get("results") or []:
        if res.get("lat") is None or res.get("lon") is None:
            continue
        out.append({
            "name": res.get("address_line1") or res.get("name") or res.get("formatted"),
            "address": res.get("address_line2") or "",
            "lat": res["lat"], "lon": res["lon"],
            "source": "live", "fetched_at": now,
        })
    return out


# ---- Places (shops, food, pharmacies, police, ...) ----

PLACES_URL = "https://api.geoapify.com/v2/places"
# Geoapify drops results when too many categories go in one request, so ask in small groups.
PLACE_GROUPS = [
    "commercial,catering",
    "healthcare.pharmacy,healthcare.hospital",
    "service.vehicle.fuel,service.financial.atm,service.police",
    "public_transport",
]
# First matching prefix wins, most specific first (a pharmacy is also "commercial").
KIND_BY_CATEGORY = [
    ("healthcare.pharmacy", "pharmacy"), ("commercial.health_and_beauty.pharmacy", "pharmacy"),
    ("healthcare.hospital", "hospital"), ("service.police", "police"),
    ("service.vehicle.fuel", "fuel"), ("service.financial.atm", "atm"),
    ("public_transport", "transport"), ("catering", "food"), ("commercial", "shop"),
]


def _place_kind(categories):
    for prefix, kind in KIND_BY_CATEGORY:
        if any(c == prefix or c.startswith(prefix + ".") for c in categories):
            return kind
    return None


async def places(bbox):
    """Places in a (south, west, north, east) box, from OpenStreetMap data via Geoapify."""
    if not config.GEOAPIFY_API_KEY:
        raise RuntimeError("GEOAPIFY_API_KEY not set")
    s, w, n, e = bbox
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
        async def group(cats):
            r = await client.get(PLACES_URL, params={"categories": cats, "filter": f"rect:{w},{s},{e},{n}",
                                                     "limit": 500, "apiKey": config.GEOAPIFY_API_KEY})
            r.raise_for_status()
            return r.json().get("features") or []
        results = await asyncio.gather(*[group(c) for c in PLACE_GROUPS])
    now = datetime.now(timezone.utc).isoformat()
    out, seen = [], set()
    for feature in (f for fs in results for f in fs):
        p = feature.get("properties", {})
        pid = p.get("place_id")
        kind = _place_kind(p.get("categories") or [])
        if not kind or pid in seen or p.get("lat") is None:
            continue
        seen.add(pid)
        raw = (p.get("datasource") or {}).get("raw") or {}
        out.append({
            "id": f"gpf-{pid}",
            "kind": kind,
            "name": p.get("name"),
            "lat": p["lat"], "lon": p["lon"],
            "opening_hours": p.get("opening_hours") or raw.get("opening_hours"),
            "phone": (p.get("contact") or {}).get("phone") or raw.get("phone"),
            "source": "live",
            "fetched_at": now,
        })
    return out
