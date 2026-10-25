"""Tiny in-memory cache. When a live source fails, the last good copy is served
and labelled OUTDATED by its age, instead of failing or inventing data."""
from datetime import datetime, timezone

_store = {}


def put(key, value):
    _store[key] = (datetime.now(timezone.utc), value)


def get(key):
    item = _store.get(key)
    return (None, None) if item is None else item
