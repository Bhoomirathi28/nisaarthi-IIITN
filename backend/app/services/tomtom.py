"""Traffic on a route from TomTom Traffic Flow (free tier), for two-wheeler and car trips.

Live traffic only describes the roads right now, so it is used only when the worker leaves
within LIVE_WINDOW_MIN. Otherwise, or when TomTom fails, a time-of-night estimate is used and
labelled PROBABLE. Walking is not affected by traffic."""
import asyncio
from datetime import datetime, timezone

import httpx

from .. import config
from ..engine import confidence as C
from ..engine import geo

URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
POINTS_PER_ROUTE = 5
LIVE_WINDOW_MIN = 30
POINT_CACHE_S = 10 * 60  # re-plans every 2 minutes reuse readings for 10 minutes
_points = {}  # (lat, lon) rounded -> (time, reading)


def _sample(coords, n=POINTS_PER_ROUTE):
    """n points spread along the route, skipping the very ends."""
    cum = geo.cumulative(coords)
    total = cum[-1] or 1
    out, j = [], 0
    for i in range(1, n + 1):
        target = total * i / (n + 1)
        while j < len(cum) - 1 and cum[j + 1] < target:
            j += 1
        out.append(coords[j])
    return out


async def _reading(client, lat, lon):
    key = (round(lat, 3), round(lon, 3))
    hit = _points.get(key)
    now = datetime.now(timezone.utc)
    if hit and (now - hit[0]).total_seconds() < POINT_CACHE_S:
        return hit[1]
    r = await client.get(URL, params={"point": f"{lat},{lon}", "key": config.TOMTOM_API_KEY, "unit": "KMPH"})
    r.raise_for_status()
    seg = r.json().get("flowSegmentData") or {}
    reading = {"current": seg.get("currentSpeed"), "free": seg.get("freeFlowSpeed"),
               "closed": bool(seg.get("roadClosure"))}
    _points[key] = (now, reading)
    return reading


def estimate(departure):
    """Time-of-night estimate when live traffic can't be used. Night roads in Indian cities are
    mostly free-flowing after 11 PM; the evening is slower."""
    h = departure.hour
    factor = 1.0 if (h >= 23 or h < 5) else 1.1 if h in (21, 22, 5, 6) else 1.25
    return {"level": "light" if factor == 1.0 else "moderate", "delay_factor": factor, "closures": 0,
            "source": "estimate", "label": C.PROBABLE}


async def route_traffic(coords, departure, mode, now=None):
    if mode == "walk":
        return None
    now = now or datetime.now(timezone.utc)
    soon = (departure - now).total_seconds() <= LIVE_WINDOW_MIN * 60
    if not (config.TOMTOM_API_KEY and soon) or config.FORCE_MOCK:
        return estimate(departure)
    try:
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
            readings = await asyncio.gather(*[_reading(client, la, lo) for la, lo in _sample(coords)])
    except Exception:
        return estimate(departure)
    ratios = [r["free"] / r["current"] for r in readings if r["current"] and r["free"]]
    if not ratios:
        return estimate(departure)
    factor = max(1.0, sum(ratios) / len(ratios))  # never faster than free flow
    level = "light" if factor < 1.15 else "moderate" if factor < 1.5 else "heavy"
    return {"level": level, "delay_factor": round(factor, 2), "closures": sum(r["closed"] for r in readings),
            "source": "live", "label": C.KNOWN, "fetched_at": now.isoformat()}
