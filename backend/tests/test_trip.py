"""Phase 2: trip page backend (place search, stops, Nagpur sample trip). No network needed."""
import pytest
from fastapi.testclient import TestClient

from app import config
from app.engine import geo
from app.main import app

client = TestClient(app)
NAGPUR = (config.CITY_LAT, config.CITY_LON)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(config, "FORCE_MOCK", True)
    monkeypatch.setattr(config, "GEOAPIFY_API_KEY", "")
    monkeypatch.setattr(config, "NEBIUS_API_KEY", "")


def test_demo_trip_is_in_nagpur():
    d = client.get("/demo").json()
    for p in (d["origin"], d["destination"]):
        assert geo.haversine(NAGPUR, (p["lat"], p["lon"])) < 15000


def test_search_falls_back_to_sample_places():
    res = client.get("/places/search", params={"text": "kamp"}).json()
    assert res["state"] == "mock"
    assert [p["name"] for p in res["results"]] == ["Kamptee"]
    assert res["results"][0]["label"] == "OUTDATED"  # sample data is never shown as KNOWN


def test_search_needs_three_letters_and_stays_near_city():
    assert client.get("/places/search", params={"text": "ka"}).json()["results"] == []
    for p in client.get("/places/search", params={"text": "sample"}).json()["results"]:
        assert geo.haversine(NAGPUR, (p["lat"], p["lon"])) <= config.SEARCH_RADIUS_KM * 1000


def test_search_unknown_text_returns_nothing_not_a_guess():
    assert client.get("/places/search", params={"text": "zzzz"}).json()["results"] == []


def _plan(stops):
    d = client.get("/demo").json()
    body = {"origin": d["origin"], "destination": d["destination"], "stops": stops,
            "departure": "2026-10-31T02:15:00+05:30", "deadline": "2026-10-31T03:00:00+05:30"}
    return client.post("/plan", json=body)


def test_plan_without_stops_uses_demo_routes():
    res = _plan([])
    assert res.status_code == 200
    assert {r["type"] for r in res.json()["routes"]} == {"balanced", "short", "less_maneuvers"}


def test_plan_passes_through_stops():
    stop = {"lat": 21.1446, "lon": 79.0822}
    res = _plan([stop]).json()
    assert res["stops"] == [[stop["lat"], stop["lon"]]]
    coords = res["routes"][0]["coords"]
    assert [stop["lat"], stop["lon"]] in coords
    assert res["routes"][0]["route_label"] == "UNKNOWN"  # no road data, so it says so


def test_plan_allows_at_most_three_stops():
    stop = {"lat": 21.14, "lon": 79.08}
    assert _plan([stop] * 3).status_code == 200
    assert _plan([stop] * 4).status_code == 422
