"""CCTV cameras detected in Mapillary street photos (object--cctv-camera map features).

Detections come from Mapillary's image recognition, so they are labelled PROBABLE, never KNOWN.
Mapillary also tells us whether anyone has photographed an area at all: a square with photos but
no cameras is "no cameras seen", a square with no photos is UNKNOWN (absence is not proof).
Free token: https://www.mapillary.com/dashboard/developers"""
import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from .. import config

API = "https://graph.mapillary.com"
CAMERA = "object--cctv-camera"
MAX_AGE_DAYS = 3 * 365  # a camera last seen longer ago than this may be gone; don't count it


def _bbox(bbox):
    s, w, n, e = bbox
    return f"{w},{s},{e},{n}"


def _when(ms_or_iso):
    if ms_or_iso is None:
        return None
    try:
        if isinstance(ms_or_iso, (int, float)):
            return datetime.fromtimestamp(ms_or_iso / 1000, tz=timezone.utc)
        return datetime.fromisoformat(str(ms_or_iso).replace("Z", "+00:00"))
    except (ValueError, OSError):
        return None


async def cameras(bbox, transport=None):
    """(cameras, surveyed) for a (south, west, north, east) box. Raises if Mapillary can't be reached."""
    if not config.MAPILLARY_TOKEN:
        raise RuntimeError("MAPILLARY_TOKEN not set")
    auth = {"Authorization": f"OAuth {config.MAPILLARY_TOKEN}"}
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT, transport=transport, headers=auth) as client:
        features, images = await asyncio.gather(
            client.get(f"{API}/map_features", params={"bbox": _bbox(bbox), "object_values": CAMERA,
                                                      "fields": "id,geometry,last_seen_at"}),
            client.get(f"{API}/images", params={"bbox": _bbox(bbox), "fields": "id", "limit": 1}))
        features.raise_for_status()
        images.raise_for_status()
    now = datetime.now(timezone.utc)
    out = []
    for f in features.json().get("data", []):
        coords = (f.get("geometry") or {}).get("coordinates")
        seen = _when(f.get("last_seen_at"))
        if not coords or (seen and now - seen > timedelta(days=MAX_AGE_DAYS)):
            continue
        out.append({
            "id": f"mly-{f['id']}", "kind": "cctv", "name": None,
            "lat": coords[1], "lon": coords[0],
            "last_seen": seen.date().isoformat() if seen else None,
            "source": "inferred",  # image recognition -> PROBABLE
            "fetched_at": now.isoformat(),
        })
    surveyed = bool(images.json().get("data")) or bool(out)
    return out, surveyed
