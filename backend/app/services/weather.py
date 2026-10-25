"""Current weather from Open-Meteo (free, no key)."""
from datetime import datetime, timezone

import httpx

from .. import config

URL = "https://api.open-meteo.com/v1/forecast"


async def current(lat, lon):
    params = {"latitude": lat, "longitude": lon,
              "current": "precipitation,weather_code,wind_speed_10m,temperature_2m",
              "timezone": "auto"}
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
        r = await client.get(URL, params=params)
        r.raise_for_status()
        cur = r.json().get("current", {})
    code = cur.get("weather_code")
    precip = cur.get("precipitation") or 0
    return {
        "code": code,
        "temperature_c": cur.get("temperature_2m"),
        "precipitation_mm": precip,
        "wind_kmh": cur.get("wind_speed_10m"),
        "thunderstorm": code is not None and code >= 95,
        "heavy_rain": code in (65, 67, 82) or precip >= 4,
        "rain": code is not None and (51 <= code <= 67 or 80 <= code <= 82),
        "fog": code in (45, 48),
        "source": "live",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
