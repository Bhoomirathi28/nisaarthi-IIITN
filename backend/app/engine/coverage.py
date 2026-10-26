"""Coverage-based safety scoring: rewards open places spread along the whole route,
not a cluster of shops near the start.
 
The team's rule, in their words:
  "Route A has 5 shops but all the way till the destination; Route B has 10 shops but
   clustered at one place. Route A can be selected."
 
So the score is built on three measures, none of which is a plain shop count:
  covered_share   how much of the route is within COVER_RADIUS_M of a place that will be
                  open when the worker actually reaches it
  dark_stretch    the longest continuous stretch with nothing open nearby
  dark_at_end     whether the darkness sits near the destination, which matters more than
                  darkness near the start, where the worker is still at a staffed workplace
 
A place is checked at the worker's estimated time of arrival at that place, not at the
time they set off, and a place that shuts within CLOSING_SOON_MIN of their arrival counts
as half-covered rather than open.
 
This module only measures coverage. The overall route score in scoring.py takes the result
as one weighted factor alongside main roads, help points, turns, transport and CCTV.
"""
from datetime import timedelta
 
from . import confidence as C
from . import geo, hours
 
# A place lights up the road around it for roughly this far.
COVER_RADIUS_M = 300
# Reaching a place less than this before closing time is not real cover.
CLOSING_SOON_MIN = 10
# A dark stretch shorter than this is not worth worrying about; beyond the second value
# the stretch is treated as fully bad.
DARK_OK_M = 300
DARK_BAD_M = 1500
# The last part of the route, where darkness is weighted more heavily.
END_SHARE = 0.25
 
SAMPLE_STEP_M = 25
 
# Places that count as cover at night. Police and hospitals are handled separately in
# scoring.py as help points; they also light the road, so they are included here.
COVER_KINDS = {"shop", "food", "pharmacy", "fuel", "atm", "police", "hospital", "transport"}
ALWAYS_OPEN_KINDS = {"police", "hospital"}
 
 
def _clamp(x):
    return max(0.0, min(1.0, x))
 
 
def cover_status(poi, eta, fresh_minutes=15, now=None):
    """How much cover this place gives at time eta.
 
    Returns (weight, label) where weight is 1.0 open, 0.5 closing soon or probably open,
    0.0 closed, and None when the hours are unknown, which is never counted as cover.
    """
    data_label = C.source_label(poi.get("source"), poi.get("fetched_at"), fresh_minutes, now)
    schedule = hours.parse(poi.get("opening_hours"))
    if schedule is None:
        if poi.get("kind") in ALWAYS_OPEN_KINDS:
            return 0.5, C.worst([data_label, C.PROBABLE])
        return None, C.UNKNOWN
    if not hours.is_open(schedule, eta):
        return 0.0, data_label
    if not hours.is_open(schedule, eta + timedelta(minutes=CLOSING_SOON_MIN)):
        return 0.5, data_label  # open when they arrive, shutting as they pass
    return 1.0, data_label
 
 
def measure(route, pois, departure, fresh_minutes=15, now=None):
    """Walk the route in short steps and work out how much of it is covered.
 
    route needs "coords" (lat, lon pairs) and optionally "duration_s".
    Returns a dict with the coverage score and the numbers behind it, so the app can
    explain the score instead of just showing a number.
    """
    coords = geo.densify(route["coords"], SAMPLE_STEP_M)
    cum = geo.cumulative(coords)
    length_m = cum[-1] if cum else 0.0
    if length_m <= 0:
        return {"score": None, "label": C.UNKNOWN, "covered_share": None,
                "longest_dark_m": None, "dark_at_end": False, "open_places": [],
                "open_count": 0, "unknown_hours": 0, "length_m": 0}
    duration_s = route.get("duration_s") or (length_m / 1.3)
 
    def eta_at(metres):
        return departure + timedelta(seconds=duration_s * (metres / length_m))
 
    # Place every candidate on the route, then decide if it is open when passed.
    open_places, labels = [], []
    unknown_hours = 0  # nearby places we can't count because their hours are missing
    for poi in pois:
        if poi.get("kind") not in COVER_KINDS:
            continue
        dist, position = geo.project((poi["lat"], poi["lon"]), coords, cum)
        if dist > COVER_RADIUS_M:
            continue
        eta = eta_at(position)
        weight, label = cover_status(poi, eta, fresh_minutes, now)
        labels.append(label)
        if weight is None:
            unknown_hours += 1
        if not weight:
            continue
        # A place off to the side covers a shorter run of the road than one on it.
        reach = (COVER_RADIUS_M ** 2 - dist ** 2) ** 0.5
        open_places.append({
            "id": poi.get("id"), "name": poi.get("name"), "kind": poi.get("kind"),
            "lat": poi["lat"], "lon": poi["lon"],
            "position_m": round(position), "distance_from_route_m": round(dist),
            "eta": eta.isoformat(), "cover": weight, "label": label,
            "_from": max(0.0, position - reach), "_to": min(length_m, position + reach),
        })
 
    # Sample the route and ask, at each point, how well covered it is. This is what makes
    # five spread-out shops beat ten clustered ones: the clustered ten all cover the same
    # few hundred metres, and the rest of the route stays uncovered.
    steps = max(2, int(length_m // SAMPLE_STEP_M) + 1)
    covered = []
    for i in range(steps):
        at = length_m * i / (steps - 1)
        best = 0.0
        for p in open_places:
            if p["_from"] <= at <= p["_to"]:
                best = max(best, p["cover"])
        covered.append(best)
 
    covered_share = sum(covered) / len(covered)
 
    # Longest run with no cover at all, and whether it falls near the destination.
    longest, run, run_end = 0.0, 0.0, 0.0
    step_m = length_m / (steps - 1)
    for i, c in enumerate(covered):
        if c == 0:
            run += step_m
            if run > longest:
                longest, run_end = run, length_m * i / (steps - 1)
        else:
            run = 0.0
    dark_at_end = longest > DARK_OK_M and run_end >= length_m * (1 - END_SHARE)
 
    dark_penalty = _clamp((longest - DARK_OK_M) / (DARK_BAD_M - DARK_OK_M))
    score = _clamp(0.65 * covered_share + 0.35 * (1 - dark_penalty))
    if dark_at_end:
        score *= 0.85  # darkness on the last stretch home counts for more
 
    for p in open_places:
        p.pop("_from", None)
        p.pop("_to", None)
    open_places.sort(key=lambda p: p["position_m"])
 
    return {
        "score": round(score, 2),
        "label": C.worst(labels) if labels else C.PROBABLE,
        "covered_share": round(covered_share, 2),
        "longest_dark_m": round(longest),
        "dark_at_end": dark_at_end,
        "open_places": open_places,
        "open_count": len(open_places),
        "unknown_hours": unknown_hours,
        "length_m": round(length_m),
    }
 
 
def reason(result, t=None):
    """A short reason code and values for the UI to translate."""
    if result["score"] is None:
        return {"code": "coverage_unknown", "tone": "neutral"}
    pct = round(result["covered_share"] * 100)
    if result["dark_at_end"]:
        return {"code": "coverage_dark_near_home", "tone": "weak",
                "value": {"m": result["longest_dark_m"]}}
    if result["score"] >= 0.7:
        return {"code": "coverage_good", "tone": "good", "value": {"pct": pct}}
    if result["score"] < 0.4:
        return {"code": "coverage_weak", "tone": "weak",
                "value": {"pct": pct, "m": result["longest_dark_m"]}}
    return {"code": "coverage_mixed", "tone": "neutral",
            "value": {"pct": pct, "m": result["longest_dark_m"]}}
