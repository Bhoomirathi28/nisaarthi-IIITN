"""Phase 3 backend: road reports, traffic, Nemotron parsing, routes page data. No network."""
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config, planner
from app.main import app
from app.services import geoapify, nebius, tavily, tomtom

IST = timezone(timedelta(hours=5, minutes=30))
client = TestClient(app)


@pytest.fixture
def offline(monkeypatch):
    for k in ("GEOAPIFY_API_KEY", "TAVILY_API_KEY", "NEBIUS_API_KEY", "TOMTOM_API_KEY"):
        monkeypatch.setattr(config, k, "")
    monkeypatch.setattr(config, "FORCE_MOCK", True)


# ---- Road reports (Tavily) ----

def test_report_must_name_the_full_road():
    assert tavily.mentions("Bike crash on Wardha Rd near Chinch Bhavan", "Wardha Road")
    assert tavily.mentions("Chain snatching on wardha road", "Wardha Road")
    # The town of Wardha is not Wardha Road
    assert not tavily.mentions("Wardha accident: seven killed as car falls off bridge", "Wardha Road")
    assert not tavily.mentions("Accident on Great Nag Road", "Wardha Road")


def test_reports_are_filtered_dated_and_old_ones_marked(monkeypatch):
    monkeypatch.setattr(config, "TAVILY_API_KEY", "test")
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=20)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    old = (now - timedelta(days=500)).strftime("%a, %d %b %Y %H:%M:%S GMT")

    async def fake_search(client, query, days):
        return [
            {"title": "Robbery on Great Nag Road", "content": "", "url": "u1", "published_date": recent},
            {"title": "Crash on Great Nag Rd last year", "content": "", "url": "u2", "published_date": old},
            {"title": "Nagpur weather update", "content": "rain expected", "url": "u3", "published_date": recent},
        ]
    monkeypatch.setattr(tavily, "_search", fake_search)
    out = asyncio.run(tavily.road_reports("Great Nag Road"))
    assert [r["url"] for r in out] == ["u1", "u2"]  # the weather story doesn't name the road
    assert out[0]["published"] and out[0]["label"] == "PROBABLE"
    assert out[1]["label"] == "OUTDATED"  # over a year old


def test_closure_news_must_be_about_a_closed_road(monkeypatch):
    monkeypatch.setattr(config, "TAVILY_API_KEY", "test")

    async def fake_search(client, query, days):
        return [{"title": "Traffic diverted near Zero Mile for metro work", "content": "", "url": "c1"},
                {"title": "Dry day lifted for counting", "content": "liquor shops reopen", "url": "c2"},
                {"title": "Woman killed in truck accident", "content": "", "url": "c3"}]
    monkeypatch.setattr(tavily, "_search", fake_search)
    assert [r["url"] for r in asyncio.run(tavily.closures())] == ["c1"]


def test_road_name_from_instruction():
    assert geoapify._road_name({"instruction": {"text": "Turn left onto Great Nag Road."}}) == "Great Nag Road"
    assert geoapify._road_name({"name": "Wardha Road"}) == "Wardha Road"
    assert geoapify._road_name({"instruction": {"text": "Drive southwest."}}) is None


def test_main_roads_skip_short_stretches():
    route = {"steps": [{"name": "Great Nag Road", "distance": 900}, {"name": "Medical Square", "distance": 55},
                       {"name": "Bus Stand Road", "distance": 400}, {"name": "Great Nag Road", "distance": 200}]}
    assert planner._main_roads(route) == ["Great Nag Road", "Bus Stand Road"]


# ---- Traffic (TomTom) ----

def test_walking_ignores_traffic():
    assert asyncio.run(tomtom.route_traffic([(21.1, 79.0), (21.2, 79.1)], datetime.now(IST), "walk")) is None


def test_later_departure_uses_probable_estimate(monkeypatch):
    monkeypatch.setattr(config, "TOMTOM_API_KEY", "test")
    later = datetime.now(IST) + timedelta(hours=3)
    tr = asyncio.run(tomtom.route_traffic([(21.1, 79.0), (21.2, 79.1)], later, "motorcycle"))
    assert tr["source"] == "estimate" and tr["label"] == "PROBABLE"


def test_live_traffic_slows_arrival(monkeypatch):
    monkeypatch.setattr(config, "TOMTOM_API_KEY", "test")
    monkeypatch.setattr(config, "FORCE_MOCK", False)
    monkeypatch.setattr(tomtom, "_points", {})

    async def fake_reading(client, lat, lon):
        return {"current": 20, "free": 40, "closed": False}
    monkeypatch.setattr(tomtom, "_reading", fake_reading)
    tr = asyncio.run(tomtom.route_traffic([(21.1, 79.0), (21.2, 79.1)], datetime.now(IST), "drive"))
    assert tr["source"] == "live" and tr["label"] == "KNOWN"
    assert tr["delay_factor"] == 2.0 and tr["level"] == "heavy"


# ---- Nemotron ----

def test_nemotron_one_call_for_all_routes(monkeypatch):
    monkeypatch.setattr(config, "NEBIUS_API_KEY", "test")
    monkeypatch.setattr(config, "NEBIUS_MODEL", "m")
    calls = []

    def handler(req):
        calls.append(req)
        text = '[{"route": 1, "safety_score": 40, "feasibility_score": 90, "note": "b"},' \
               ' {"route": 0, "safety_score": 70, "feasibility_score": 80, "note": "a"}]'
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})
    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    route = {"factors": {}, "length_m": 1000, "duration_s": 600, "feasibility": {"buffer_min": 5}}
    out = asyncio.run(nebius.score_routes([route, route]))
    assert len(calls) == 1
    assert [o["safety_score"] for o in out] == [70, 40]  # matched by route index, not reply order
    assert out[0]["label"] == "PROBABLE"


# ---- Plan response ----

def _plan(origin, dest):
    body = {"origin": origin, "destination": dest, "mode": "walk",
            "departure": "2026-10-31T02:15:00+05:30", "deadline": "2026-10-31T03:00:00+05:30"}
    return client.post("/plan", json=body).json()


def test_sample_trip_route_cards_have_what_the_page_needs(offline):
    d = client.get("/demo").json()
    res = _plan(d["origin"], d["destination"])
    r = res["routes"][0]
    cov = r["factors"]["coverage"]
    assert "open_places" not in r["factors"] and "spacing" not in r["factors"]
    assert {"covered_share", "longest_dark_m", "unknown_hours", "positions_m"} <= cov["value"].keys()
    assert any(x["code"].startswith("coverage_") for x in r["reasons"])
    assert {p["name"] for route in res["routes"] for p in route["police_on_route"]} >= {"Police station (sample)"}
    assert res["data_status"]["places"] == "mock"


def test_real_trip_never_gets_sample_places(offline):
    # Offline, away from the sample trip: places are UNKNOWN, not borrowed from the sample data
    res = _plan({"lat": 21.07, "lon": 78.96}, {"lat": 21.09, "lon": 78.99})
    r = res["routes"][0]
    assert res["data_status"]["places"] == "none"
    assert r["factors"]["coverage"]["score"] is None and r["factors"]["coverage"]["label"] == "UNKNOWN"
    assert r["police_on_route"] == [] and r["cover_places"] == []
