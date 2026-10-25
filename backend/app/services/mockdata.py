import json
import math
from functools import lru_cache

from .. import config
from ..engine import geo

SPEED_MPS = {"walk": 1.3, "motorcycle": 7.0, "drive": 8.0}


@lru_cache(maxsize=1)
def load():
    with open(config.MOCK_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _route_from(coords, steps_spec, turns, mode, type_):
    coords = [tuple(c) for c in coords]
    length = geo.cumulative(coords)[-1]
    speed = SPEED_MPS.get(mode, 1.3)
    return {
        "type": type_,
        "coords": coords,
        "distance_m": length,
        "duration_s": length / speed + turns * (4 if mode != "walk" else 0),
        "steps": [{"road_class": s["road_class"], "distance": length * s["share"]} for s in steps_spec],
        "turns": turns,
        "source": "mock",
        "fetched_at": load()["fetched_at"],
    }


def routes(origin, dest, mode, stops=()):
    data = load()
    trip = data["demo_trip"]
    near_demo = not stops and (geo.haversine(origin, (trip["origin"]["lat"], trip["origin"]["lon"])) < 400 and
                 geo.haversine(dest, (trip["destination"]["lat"], trip["destination"]["lon"])) < 400)
    out = []
    if near_demo:
        for type_, r in data["routes"].items():
            out.append(_route_from(r["coords"], r["steps"], r["turns"], mode, type_))
        return out
    # Outside the demo trip: straight lines through any stops, with road details UNKNOWN.
    coords = [origin, *stops, dest]
    length = geo.cumulative(coords)[-1]
    out.append({
        "type": "straight_line", "coords": coords, "distance_m": length,
        "duration_s": length * 1.3 / SPEED_MPS.get(mode, 1.3), "steps": [], "turns": None,
        "source": None, "fetched_at": None,
    })
    return out


def places():
    data = load()
    return [{**p, "source": "mock", "fetched_at": data["fetched_at"]} for p in data["places"]]


def advisories():
    data = load()
    return [{**a, "source": "mock", "fetched_at": data["fetched_at"]} for a in data["advisories"]]


def demo_trip():
    return load()["demo_trip"]


def search(text, limit=6):
    """Sample places whose name contains the text (used when live search is unavailable)."""
    data = load()
    q = text.strip().lower()
    hits = [p for p in data.get("search_places", []) if q in p["name"].lower()]
    return [{**p, "source": "mock", "fetched_at": data["fetched_at"]} for p in hits[:limit]]
