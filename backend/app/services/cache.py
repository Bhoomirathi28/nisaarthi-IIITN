"""Small cache kept in memory and saved to disk, so it survives server restarts.
When a live source fails, the last good copy is served and labelled by its age
(OUTDATED when old), instead of failing or inventing data."""
import json
from datetime import datetime, timezone

from .. import config

_store = {}
_loaded = False


def _path():
    return config.BASE_DIR / "data" / "cache.json"


def _load():
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
        for k, (at, value) in raw.items():
            _store[k] = (datetime.fromisoformat(at), value)
    except (OSError, ValueError):
        pass  # no cache yet, or a damaged file: start empty


MAX_AGE_S = 3 * 24 * 3600  # older copies are dropped when saving


def _save():
    now = datetime.now(timezone.utc)
    for k in [k for k, (at, _) in _store.items() if (now - at).total_seconds() > MAX_AGE_S]:
        del _store[k]
    try:
        data = {k: (at.isoformat(), v) for k, (at, v) in _store.items()}
        tmp = _path().with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(_path())
    except OSError:
        pass  # the cache is a convenience; never fail a request because of it


def _key(key):
    return json.dumps(key) if not isinstance(key, str) else key


def put(key, value, persist=True):
    _load()
    _store[_key(key)] = (datetime.now(timezone.utc), value)
    if persist:
        _save()


def get(key, max_age_s=None):
    """(saved_at, value), or (None, None) if missing or older than max_age_s."""
    _load()
    item = _store.get(_key(key))
    if item is None:
        return None, None
    if max_age_s is not None and (datetime.now(timezone.utc) - item[0]).total_seconds() > max_age_s:
        return None, None
    return item
