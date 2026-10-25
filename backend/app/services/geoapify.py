"""Geoapify: routing (three candidate routes: balanced, short, less_maneuvers) and place search."""
import asyncio
from datetime import datetime, timezone

import httpx

from .. import config

URL = "https://api.geoapify.com/v1/routing"
AUTOCOMPLETE_URL = "https://api.geoapify.com/v1/geocode/autocomplete"
MODES = {"walk": "walk", "motorcycle": "motorcycle", "drive": "drive"}
TYPES = ["balanced", "short", "less_maneuvers"]


def _parse(feature, type_):
    props = feature["properties"]
    geom = feature["geometry"]
    lines = geom["coordinates"] if geom["type"] == "MultiLineString" else [geom["coordinates"]]
    coords = [(lat, lon) for line in lines for lon, lat in line]
    steps = []
    for leg in props.get("legs", []):
        for s in leg.get("steps", []):
            steps.append({"distance": s.get("distance", 0), "road_class": s.get("road_class")})
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
