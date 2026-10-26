"""Run: python -m pytest backend/tests  (or: cd backend && python -m pytest)"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.engine import confidence as C
from app.engine import hours, scoring

IST = timezone(timedelta(hours=5, minutes=30))
MOCK = json.loads((Path(__file__).resolve().parent.parent / "data" / "mock_data.json").read_text())


def at(h, m, day=6):  # 2026-10-31 is a Saturday; day offsets from there
    return datetime(2026, 10, 25 + day, h, m, tzinfo=IST)


def test_hours_basic():
    assert hours.open_at("24/7", at(2, 30)) is True
    assert hours.open_at("Mo-Su 08:00-23:00", at(2, 30)) is False
    assert hours.open_at("Mo-Su 22:00-05:00", at(2, 30)) is True  # overnight span
    assert hours.open_at("Mo-Su 18:00-03:00", at(2, 50)) is True
    assert hours.open_at("Mo-Su 18:00-03:00", at(3, 10)) is False
    assert hours.open_at(None, at(2, 30)) is None
    assert hours.open_at("sunrise-sunset", at(2, 30)) is None  # unparseable -> UNKNOWN, not a guess


def test_hours_days():
    sat = at(10, 0)
    assert sat.weekday() == 5
    assert hours.open_at("Mo-Fr 09:00-18:00", sat) is False
    assert hours.open_at("Mo-Sa 09:00-13:00,16:00-21:00; Su off", sat) is True


def test_confidence_labels():
    now = datetime.now(timezone.utc)
    assert C.source_label("live", now.isoformat()) == C.KNOWN
    assert C.source_label("live", (now - timedelta(hours=2)).isoformat()) == C.OUTDATED
    assert C.source_label("mock", None) == C.OUTDATED
    assert C.source_label("inferred", None) == C.PROBABLE
    assert C.source_label(None, None) == C.UNKNOWN


def _mock_route(name):
    r = MOCK["routes"][name]
    coords = [tuple(c) for c in r["coords"]]
    from app.engine import geo
    length = geo.cumulative(coords)[-1]
    return {"coords": coords, "duration_s": length / 1.3, "turns": r["turns"],
            "steps": [{"road_class": s["road_class"], "distance": length * s["share"]} for s in r["steps"]],
            "route_label": C.OUTDATED, "poi_label": C.OUTDATED}


def test_main_road_route_beats_dark_lane_route():
    places = [{**p, "source": "mock", "fetched_at": MOCK["fetched_at"]} for p in MOCK["places"]]
    dep = at(2, 15)
    a = scoring.score_route(_mock_route("balanced"), places, dep)
    b = scoring.score_route(_mock_route("short"), places, dep)
    assert a["reliability"] > b["reliability"]
    # the short route's own day-time shops are shut at 2:15 AM, so none of them may count as cover
    day_shops = {"Kirana store", "Mobile shop", "Bakery", "Hardware shop"}
    assert not day_shops & {p["name"] for p in b["cover_places"]}
    assert a["factors"]["coverage"]["value"]["covered_share"] > b["factors"]["coverage"]["value"]["covered_share"]
    # sample data is never reported as KNOWN (coverage turns UNKNOWN when a nearby place has no hours)
    assert a["confidence"] in (C.OUTDATED, C.UNKNOWN)


def test_feasibility():
    dep = at(2, 15)
    f = scoring.feasibility(dep, 30 * 60, at(3, 0))
    assert f["feasible"] is True and f["buffer_min"] == 15
