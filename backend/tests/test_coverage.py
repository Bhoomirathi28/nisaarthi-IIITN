"""The team's rule: 5 shops spread along the route must beat 10 shops clustered at the start."""
from datetime import datetime, timedelta, timezone

from app.engine import coverage

IST = timezone(timedelta(hours=5, minutes=30))
DEPART = datetime(2026, 10, 27, 2, 15, tzinfo=IST)  # 2:15 AM, end of a night shift

# A straight 3 km route. 0.009 degrees of latitude is roughly 1 km.
START = (21.1458, 79.0882)  # near Nagpur
ROUTE = {"coords": [START, (START[0] + 0.027, START[1])], "duration_s": 3000}


def shop(km, name, hours_text="24/7", offset=0.0):
    """A place `km` along the route, `offset` degrees to the side."""
    return {"id": name, "name": name, "kind": "shop", "opening_hours": hours_text,
            "lat": START[0] + km * 0.009, "lon": START[1] + offset,
            "source": "live", "fetched_at": datetime.now(timezone.utc).isoformat()}


def test_spread_beats_clustered():
    route_a = [shop(k, f"A{k}") for k in (0.5, 1.1, 1.7, 2.3, 2.9)]        # 5 spread out
    route_b = [shop(0.1 + i * 0.05, f"B{i}") for i in range(10)]            # 10 in 500 m
    a = coverage.measure(ROUTE, route_a, DEPART)
    b = coverage.measure(ROUTE, route_b, DEPART)
    assert a["score"] > b["score"], (a, b)
    assert a["covered_share"] > b["covered_share"]
    assert b["longest_dark_m"] > a["longest_dark_m"]
    assert b["open_count"] == 10 and a["open_count"] == 5  # fewer places, better route


def test_closed_shops_do_not_count():
    day_shops = [shop(k, f"D{k}", "Mo-Su 09:00-22:00") for k in (0.5, 1.1, 1.7, 2.3, 2.9)]
    result = coverage.measure(ROUTE, day_shops, DEPART)
    assert result["open_count"] == 0
    assert result["covered_share"] == 0


def test_closing_soon_is_half_cover():
    # Walking, the 0.5 km mark is reached about 02:23. A shop shutting at 02:30 is open
    # on arrival but gone within 10 minutes, so it is only half cover.
    half = coverage.measure(ROUTE, [shop(0.5, "closing", "Mo-Su 18:00-02:30")], DEPART)
    assert half["open_places"][0]["cover"] == 0.5
    # One shutting at 03:30 is real cover.
    full = coverage.measure(ROUTE, [shop(0.5, "open", "Mo-Su 18:00-03:30")], DEPART)
    assert full["open_places"][0]["cover"] == 1.0
    # One that already shut at 02:20 is no cover at all.
    shut = coverage.measure(ROUTE, [shop(0.5, "shut", "Mo-Su 18:00-02:20")], DEPART)
    assert shut["open_count"] == 0


def test_darkness_near_home_is_worse():
    near_start_dark = [shop(k, f"S{k}") for k in (1.6, 2.0, 2.4, 2.8)]   # dark first 1.5 km
    near_home_dark = [shop(k, f"H{k}") for k in (0.2, 0.6, 1.0, 1.4)]    # dark last 1.5 km
    a = coverage.measure(ROUTE, near_start_dark, DEPART)
    b = coverage.measure(ROUTE, near_home_dark, DEPART)
    assert b["dark_at_end"] and not a["dark_at_end"]
    assert b["score"] < a["score"]


def test_unknown_hours_are_not_counted_as_open():
    unknown = [shop(k, f"U{k}", None) for k in (0.5, 1.5, 2.5)]
    result = coverage.measure(ROUTE, unknown, DEPART)
    assert result["open_count"] == 0
    assert result["label"] == "UNKNOWN"


def test_police_station_counts_as_partial_cover():
    police = [{**shop(1.5, "chowki", None), "kind": "police"}]
    result = coverage.measure(ROUTE, police, DEPART)
    assert result["open_places"][0]["cover"] == 0.5
    assert result["open_places"][0]["label"] == "PROBABLE"
