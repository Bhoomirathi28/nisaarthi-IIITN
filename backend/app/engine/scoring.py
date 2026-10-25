"""Rule-based reliability score for a night-time route.

Factors come straight from the team's notes:
  open places along the route, fewer gaps between open places (evenly spaced, not clustered),
  distance on main roads, open help points nearby, fewer turns, open transport locations,
  CCTV cameras (OSM man_made=surveillance).
Every place is checked for whether it will still be open *when the worker passes it*,
not just right now.
"""
from datetime import timedelta

from . import confidence as C
from . import geo, hours

OPEN_PLACE_KINDS = {"shop", "food", "pharmacy", "fuel", "atm"}
HELP_KINDS = {"police", "hospital", "pharmacy"}
TRANSPORT_KINDS = {"transport"}
CCTV_KINDS = {"cctv"}
INSTITUTION_KINDS = {"police", "hospital"}  # normally staffed all night
MAIN_ROAD_CLASSES = {"motorway", "trunk", "primary", "secondary"}

ALONG_ROUTE_M = 150
HELP_RADIUS_M = 500

WEIGHTS = {
    "open_places": 0.20,
    "spacing": 0.20,
    "main_roads": 0.15,
    "help_points": 0.15,
    "turns": 0.10,
    "transport": 0.10,
    "cctv": 0.10,
}


def _clamp(x):
    return max(0.0, min(1.0, x))


def place_status(poi, eta, fresh_minutes, now=None):
    """Decide if a place is open at eta, and how sure we are.

    Returns (open: True|False|None, label).
    """
    data_label = C.source_label(poi.get("source"), poi.get("fetched_at"), fresh_minutes, now)
    kind = poi.get("kind")
    if kind in CCTV_KINDS:
        return None, data_label  # cameras have no hours
    is_open = hours.open_at(poi.get("opening_hours"), eta)
    if is_open is not None:
        return is_open, data_label
    if kind in INSTITUTION_KINDS:
        return True, C.worst([data_label, C.PROBABLE])
    return None, C.UNKNOWN


def score_route(route, pois, departure, fresh_minutes=15, now=None):
    coords = geo.densify(route["coords"])
    cum = geo.cumulative(coords)
    length_m = cum[-1] if cum else 0.0
    length_km = max(length_m / 1000.0, 0.2)
    duration_s = route.get("duration_s") or (length_m / 1.3)

    def eta_at(pos):
        frac = pos / length_m if length_m else 0
        return departure + timedelta(seconds=duration_s * frac)

    along = []
    for poi in pois:
        dist, pos = geo.project((poi["lat"], poi["lon"]), coords, cum)
        radius = HELP_RADIUS_M if poi["kind"] in HELP_KINDS else ALONG_ROUTE_M
        if dist > radius:
            continue
        eta = eta_at(pos)
        is_open, label = place_status(poi, eta, fresh_minutes, now)
        along.append({
            **poi,
            "distance_from_route_m": round(dist),
            "position_m": round(pos),
            "eta": eta.isoformat(),
            "open_when_passing": is_open,
            "label": label,
        })
    along.sort(key=lambda p: p["position_m"])

    near = [p for p in along if p["distance_from_route_m"] <= ALONG_ROUTE_M]
    open_places = [p for p in near if p["kind"] in OPEN_PLACE_KINDS and p["open_when_passing"]]
    factors = {}

    def labels_of(items, fallback):
        return C.worst([p["label"] for p in items]) if items else fallback

    # When a live query finds nothing, absence on OpenStreetMap is not proof: PROBABLE.
    empty_label = route.get("poi_label", C.PROBABLE)
    if empty_label == C.KNOWN:
        empty_label = C.PROBABLE

    # 1. Open places along the route
    per_km = len(open_places) / length_km
    factors["open_places"] = {
        "score": _clamp(per_km / 4.0),
        "value": {"count": len(open_places), "per_km": round(per_km, 1)},
        "label": labels_of(open_places, empty_label),
    }

    # 2. Fewer gaps between open places (evenly spaced beats clustered)
    stops = [0] + [p["position_m"] for p in open_places] + [length_m]
    gaps = [b - a for a, b in zip(stops, stops[1:])]
    max_gap = max(gaps) if gaps else length_m
    factors["spacing"] = {
        "score": _clamp(1 - (max_gap - 300) / 1200),
        "value": {"max_gap_m": round(max_gap), "positions_m": [p["position_m"] for p in open_places],
                  "length_m": round(length_m)},
        "label": labels_of(open_places, empty_label),
    }

    # 3. Distance on main roads
    steps = route.get("steps") or []
    classed = [s for s in steps if s.get("road_class")]
    if classed:
        main = sum(s["distance"] for s in classed if s["road_class"] in MAIN_ROAD_CLASSES)
        total = sum(s["distance"] for s in classed) or 1
        share = main / total
        factors["main_roads"] = {
            "score": _clamp(share),
            "value": {"share": round(share, 2), "main_m": round(main)},
            "label": route.get("route_label", C.UNKNOWN),
        }
    else:
        factors["main_roads"] = {"score": None, "value": None, "label": C.UNKNOWN}

    # 4. Open help points nearby
    helpers = [p for p in along if p["kind"] in HELP_KINDS and p["open_when_passing"]]
    factors["help_points"] = {
        "score": _clamp(len(helpers) / 3.0),
        "value": {"count": len(helpers)},
        "label": labels_of(helpers, empty_label),
    }

    # 5. Fewer turns
    turns = route.get("turns")
    if turns is None:
        factors["turns"] = {"score": None, "value": None, "label": C.UNKNOWN}
    else:
        tpk = turns / length_km
        factors["turns"] = {
            "score": _clamp(1 - tpk / 6.0),
            "value": {"count": turns, "per_km": round(tpk, 1)},
            "label": route.get("route_label", C.UNKNOWN),
        }

    # 6. Transport locations listed open
    transport = [p for p in near if p["kind"] in TRANSPORT_KINDS and p["open_when_passing"]]
    factors["transport"] = {
        "score": _clamp(len(transport) / 2.0),
        "value": {"count": len(transport)},
        "label": labels_of(transport, empty_label),
    }

    # 7. CCTV cameras
    cams = [p for p in near if p["kind"] in CCTV_KINDS]
    factors["cctv"] = {
        "score": _clamp((len(cams) / length_km) / 3.0),
        "value": {"count": len(cams)},
        "label": labels_of(cams, empty_label),
    }

    usable = {k: f for k, f in factors.items() if f["score"] is not None}
    wsum = sum(WEIGHTS[k] for k in usable) or 1
    reliability = sum(WEIGHTS[k] * f["score"] for k, f in usable.items()) / wsum
    for k, f in factors.items():
        f["weight"] = WEIGHTS[k]
        if f["score"] is not None:
            f["score"] = round(f["score"], 2)

    return {
        "reliability": round(reliability * 100),
        "factors": factors,
        "places": along,
        "length_m": round(length_m),
        "duration_s": round(duration_s),
        "confidence": C.worst([f["label"] for f in factors.values() if f["score"] is not None]),
        "unknown_factors": [k for k, f in factors.items() if f["score"] is None],
    }


def feasibility(departure, duration_s, deadline):
    arrival = departure + timedelta(seconds=duration_s)
    if deadline is None:
        return {"arrival": arrival.isoformat(), "buffer_min": None, "feasible": None}
    buffer_min = (deadline - arrival).total_seconds() / 60.0
    return {"arrival": arrival.isoformat(), "buffer_min": round(buffer_min), "feasible": buffer_min >= 0}


def apply_weather(result, weather):
    """Lower the score in bad weather; never raise it."""
    if not weather or weather.get("label") == C.UNKNOWN:
        return result
    penalty = 0
    if weather.get("thunderstorm"):
        penalty = 10
    elif weather.get("heavy_rain"):
        penalty = 6
    elif weather.get("rain") or weather.get("fog"):
        penalty = 3
    if penalty:
        result["reliability"] = max(0, result["reliability"] - penalty)
        result["weather_penalty"] = penalty
    return result


def reasons(result):
    """Short, translatable reason codes for the UI."""
    f = result["factors"]
    out = []
    for key, f_ in f.items():
        if f_["score"] is None:
            out.append({"code": f"{key}_unknown", "tone": "neutral"})
        elif f_["score"] >= 0.7:
            out.append({"code": f"{key}_good", "tone": "good", "value": f_["value"]})
        elif f_["score"] < 0.35:
            out.append({"code": f"{key}_weak", "tone": "weak", "value": f_["value"]})
    order = {"weak": 0, "good": 1, "neutral": 2}
    out.sort(key=lambda r: order[r["tone"]])
    return out


def rank(routes):
    """Safest feasible plan first; infeasible plans after, still ranked by safety."""
    def key(r):
        feas = r["feasibility"]["feasible"]
        return (0 if feas in (True, None) else 1, -r["reliability"])
    return sorted(routes, key=key)
