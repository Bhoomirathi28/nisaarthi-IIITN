"""Regenerates mock_data.json: a sample night trip in Nagpur used for demos and offline testing.
All places here are SAMPLE data, not real businesses. Run: python make_mock_data.py
"""
import json
from pathlib import Path

ORIGIN = {"lat": 21.1290, "lon": 79.0950, "name": "Hospital gate (sample)"}
DEST = {"lat": 21.1205, "lon": 79.0740, "name": "Home (sample)"}

ROUTES = {
    "balanced": {
        "coords": [(21.1290, 79.0950), (21.1278, 79.0910), (21.1265, 79.0865), (21.1250, 79.0820),
                   (21.1232, 79.0780), (21.1215, 79.0755), (21.1205, 79.0740)],
        "steps": [("primary", 0.45), ("secondary", 0.35), ("residential", 0.20)],
        "turns": 4,
    },
    "short": {
        "coords": [(21.1290, 79.0950), (21.1260, 79.0922), (21.1238, 79.0890), (21.1225, 79.0850),
                   (21.1220, 79.0810), (21.1210, 79.0770), (21.1205, 79.0740)],
        "steps": [("residential", 0.55), ("tertiary", 0.25), ("secondary", 0.20)],
        "turns": 9,
    },
    "less_maneuvers": {
        "coords": [(21.1290, 79.0950), (21.1302, 79.0890), (21.1295, 79.0830), (21.1270, 79.0780),
                   (21.1235, 79.0750), (21.1205, 79.0740)],
        "steps": [("trunk", 0.30), ("tertiary", 0.40), ("residential", 0.30)],
        "turns": 3,
    },
}

# (route, fraction along route, side offset in degrees, kind, name, opening_hours)
PLACES = [
    ("balanced", 0.08, 0.0003, "pharmacy", "24x7 medical store", "24/7"),
    ("balanced", 0.18, -0.0003, "food", "Night chai stall", "Mo-Su 22:00-05:00"),
    ("balanced", 0.30, 0.0003, "fuel", "Petrol pump", "24/7"),
    ("balanced", 0.42, -0.0003, "atm", "ATM kiosk", "24/7"),
    ("balanced", 0.55, 0.0003, "food", "Late-night snacks", "Mo-Su 18:00-03:00"),
    ("balanced", 0.68, -0.0003, "shop", "General store", "Mo-Su 07:00-23:00"),
    ("balanced", 0.78, 0.0003, "food", "Bun-maska counter", "Mo-Su 20:00-04:00"),
    ("balanced", 0.90, -0.0003, "pharmacy", "Medical store", "Mo-Su 08:00-02:00"),
    ("balanced", 0.25, 0.0002, "cctv", "CCTV camera", None),
    ("balanced", 0.50, -0.0002, "cctv", "CCTV camera", None),
    ("balanced", 0.72, 0.0002, "cctv", "CCTV camera", None),
    ("balanced", 0.95, -0.0002, "cctv", "CCTV camera", None),
    ("balanced", 0.35, 0.0004, "transport", "Bus stop", None),
    ("balanced", 0.62, -0.0004, "transport", "Auto stand", "24/7"),
    ("short", 0.06, 0.0003, "shop", "Kirana store", "Mo-Su 09:00-22:00"),
    ("short", 0.10, -0.0003, "shop", "Mobile shop", "Mo-Sa 10:00-21:00"),
    ("short", 0.13, 0.0003, "food", "Paan shop", "Mo-Su 10:00-01:00"),
    ("short", 0.16, -0.0003, "shop", "Bakery", "Mo-Su 07:00-22:00"),
    ("short", 0.60, 0.0003, "shop", "Hardware shop", "Mo-Sa 09:00-20:00"),
    ("short", 0.85, -0.0003, "food", "Tea stall", None),
    ("short", 0.40, 0.0002, "cctv", "CCTV camera", None),
    ("less_maneuvers", 0.20, 0.0003, "fuel", "Petrol pump", "Mo-Su 06:00-23:00"),
    ("less_maneuvers", 0.45, -0.0003, "transport", "Taxi stand", "24/7"),
    ("less_maneuvers", 0.88, 0.0003, "food", "Night chai stall", "Mo-Su 21:00-04:00"),
    ("less_maneuvers", 0.30, 0.0002, "cctv", "CCTV camera", None),
    ("less_maneuvers", 0.70, -0.0002, "cctv", "CCTV camera", None),
]

HELP = [
    {"kind": "police", "name": "Police station (sample)", "lat": 21.1246, "lon": 79.0832, "phone": "112"},
    {"kind": "police", "name": "Police chowki (sample)", "lat": 21.1272, "lon": 79.0945, "phone": "112"},
    {"kind": "hospital", "name": "Hospital (sample)", "lat": 21.1293, "lon": 79.0958, "phone": "108",
     "opening_hours": "24/7"},
]


# Sample places for place search when Geoapify is unavailable. Area centres are approximate.
SEARCH_PLACES = [
    {"name": ORIGIN["name"], "address": "Sample trip start", "lat": ORIGIN["lat"], "lon": ORIGIN["lon"]},
    {"name": DEST["name"], "address": "Sample trip end", "lat": DEST["lat"], "lon": DEST["lon"]},
    {"name": "Sitabuldi", "address": "Nagpur (approximate, sample)", "lat": 21.1446, "lon": 79.0822},
    {"name": "Nagpur Railway Station", "address": "Nagpur (approximate, sample)", "lat": 21.1526, "lon": 79.0880},
    {"name": "Dharampeth", "address": "Nagpur (approximate, sample)", "lat": 21.1405, "lon": 79.0640},
    {"name": "Sadar", "address": "Nagpur (approximate, sample)", "lat": 21.1600, "lon": 79.0800},
    {"name": "Hingna", "address": "Near Nagpur (approximate, sample)", "lat": 21.0710, "lon": 78.9620},
    {"name": "Kamptee", "address": "Near Nagpur (approximate, sample)", "lat": 21.2230, "lon": 79.1980},
    {"name": "Butibori MIDC", "address": "Near Nagpur (approximate, sample)", "lat": 20.9330, "lon": 78.9600},
]


def point_at(coords, frac):
    import math
    segs = [math.dist(a, b) for a, b in zip(coords, coords[1:])]
    target = sum(segs) * frac
    for (a, b), s in zip(zip(coords, coords[1:]), segs):
        if target <= s:
            t = target / s if s else 0
            return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        target -= s
    return coords[-1]


def main():
    places = []
    for i, (route, frac, off, kind, name, oh) in enumerate(PLACES):
        lat, lon = point_at(ROUTES[route]["coords"], frac)
        places.append({"id": f"mock-{i}", "kind": kind, "name": name, "lat": round(lat + off, 6),
                       "lon": round(lon - off, 6), "opening_hours": oh})
    for j, h in enumerate(HELP):
        places.append({"id": f"mock-help-{j}", "opening_hours": h.get("opening_hours"), **h})

    data = {
        "_note": "SAMPLE data for demos and offline mode. Not real places.",
        "fetched_at": "2026-10-01T00:00:00+05:30",
        "demo_trip": {
            "origin": ORIGIN, "destination": DEST,
            "shift_end": "02:15", "reach_by": "03:00", "mode": "walk",
        },
        "routes": {k: {"coords": [list(c) for c in v["coords"]],
                       "steps": [{"road_class": rc, "share": sh} for rc, sh in v["steps"]],
                       "turns": v["turns"]} for k, v in ROUTES.items()},
        "places": places,
        "search_places": SEARCH_PLACES,
        "advisories": [
            {"kind": "incident", "title": "Sample: poorly lit stretch reported near a lane on the short route",
             "url": None},
            {"kind": "closure", "title": "Sample: night roadwork on a side road, check before leaving", "url": None},
        ],
    }
    Path(__file__).with_name("mock_data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print("wrote", len(places), "places")


if __name__ == "__main__":
    main()
