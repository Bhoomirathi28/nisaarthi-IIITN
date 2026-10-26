"""/health key checks, with fake API responses (no network, no real keys)."""
import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import keycheck

KEYS = ["GEOAPIFY_API_KEY", "TAVILY_API_KEY", "NEBIUS_API_KEY", "TOMTOM_API_KEY", "MAPILLARY_TOKEN", "NEBIUS_MODEL"]


@pytest.fixture
def no_keys(monkeypatch):
    for k in KEYS:
        monkeypatch.setattr(config, k, "")


@pytest.fixture
def all_keys(monkeypatch):
    for k in KEYS:
        monkeypatch.setattr(config, k, "test")
    monkeypatch.setattr(config, "NEBIUS_MODEL", "nvidia/nemotron-test")


def fake(handler):
    return asyncio.run(keycheck.check_all(transport=httpx.MockTransport(handler)))


def test_health_without_keys_says_not_set(no_keys):
    res = TestClient(app).get("/health", params={"check": "true"}).json()
    assert res["sources"]["tomtom"] is False
    assert {v["status"] for v in res["keys"].values()} == {"not_set"}


def test_health_is_fast_without_check(no_keys):
    assert "keys" not in TestClient(app).get("/health").json()


def test_all_keys_working(all_keys):
    def handler(req):
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "nvidia/nemotron-test"}]})
        return httpx.Response(200, json={})
    assert {k: v["status"] for k, v in fake(handler).items()} == dict.fromkeys(keycheck.CHECKS, "working")


def test_rejected_key_and_wrong_model(all_keys, monkeypatch):
    monkeypatch.setattr(config, "NEBIUS_MODEL", "nvidia/typo")

    def handler(req):
        if "tomtom" in req.url.host:
            return httpx.Response(403)
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "nvidia/nemotron-test"}, {"id": "other/model"}]})
        return httpx.Response(200, json={})
    res = fake(handler)
    assert res["tomtom"]["status"] == "rejected"
    assert res["nebius"]["status"] == "model_not_found"
    assert res["nebius"]["nemotron_models"] == ["nvidia/nemotron-test"]  # suggests the right ID


def test_service_down_is_error_not_crash(all_keys):
    def handler(req):
        raise httpx.ConnectError("down")
    assert {v["status"] for v in fake(handler).values()} == {"error"}


def test_env_example_has_no_real_keys():
    """Keys belong in backend/.env (git-ignored), never in the committed .env.example."""
    example = (config.BASE_DIR / ".env.example").read_text(encoding="utf-8")
    filled = [line.split("=")[0] for line in example.splitlines()
              if line.split("=")[0].endswith(("_KEY", "_TOKEN")) and line.split("=", 1)[1].strip()]
    assert filled == [], f"Move these to backend/.env and leave them empty in .env.example: {filled}"
