import pytest

from app.services import cache


@pytest.fixture(autouse=True)
def empty_cache(monkeypatch):
    """Tests never read or write the real cache file in backend/data."""
    monkeypatch.setattr(cache, "_store", {})
    monkeypatch.setattr(cache, "_loaded", True)
    monkeypatch.setattr(cache, "_save", lambda: None)
