"""Checks each API key with one small live call, for /health?check=true.
Statuses: working, not_set, rejected (key refused), model_not_found (Nebius), error (network or service problem).
Costs per check: Geoapify 1 request, Tavily 1 credit, Nebius none (model list), TomTom 1 request,
Mapillary 1 request."""
import asyncio

import httpx

from .. import config


def _rejected(r):
    return r.status_code in (401, 403)


async def geoapify(client):
    r = await client.get("https://api.geoapify.com/v1/geocode/autocomplete",
                         params={"text": config.CITY_NAME, "limit": 1, "format": "json",
                                 "apiKey": config.GEOAPIFY_API_KEY})
    if _rejected(r):
        return {"status": "rejected"}
    r.raise_for_status()
    return {"status": "working"}


async def tavily(client):
    r = await client.post("https://api.tavily.com/search",
                          headers={"Authorization": f"Bearer {config.TAVILY_API_KEY}"},
                          json={"query": config.CITY_NAME, "max_results": 1, "search_depth": "basic"})
    if _rejected(r):
        return {"status": "rejected"}
    r.raise_for_status()
    return {"status": "working"}


async def nebius(client):
    url = config.NEBIUS_BASE_URL.rstrip("/") + "/models"
    r = await client.get(url, headers={"Authorization": f"Bearer {config.NEBIUS_API_KEY}"})
    if _rejected(r):
        return {"status": "rejected"}
    r.raise_for_status()
    ids = {m.get("id") for m in r.json().get("data", [])}
    if not config.NEBIUS_MODEL:
        return {"status": "model_not_set", "detail": "Key works. Copy a model ID from the catalog into NEBIUS_MODEL."}
    if config.NEBIUS_MODEL not in ids:
        nemotron = sorted(i for i in ids if i and "nemotron" in i.lower())
        return {"status": "model_not_found", "detail": f"'{config.NEBIUS_MODEL}' is not in the catalog.",
                "nemotron_models": nemotron}
    return {"status": "working", "model": config.NEBIUS_MODEL}


async def tomtom(client):
    r = await client.get("https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json",
                         params={"point": f"{config.CITY_LAT},{config.CITY_LON}", "key": config.TOMTOM_API_KEY})
    if _rejected(r):
        return {"status": "rejected"}
    r.raise_for_status()
    return {"status": "working"}


async def mapillary(client):
    r = await client.get("https://graph.mapillary.com/images",
                         params={"bbox": f"{config.CITY_LON},{config.CITY_LAT},{config.CITY_LON + 0.01},{config.CITY_LAT + 0.01}",
                                 "fields": "id", "limit": 1},
                         headers={"Authorization": f"OAuth {config.MAPILLARY_TOKEN}"})
    if _rejected(r) or r.status_code == 500 and "OAuth" in r.text:  # Mapillary answers a bad token with 500
        return {"status": "rejected"}
    r.raise_for_status()
    return {"status": "working", "photos_near_city_centre": bool(r.json().get("data"))}


CHECKS = {
    "geoapify": (lambda: config.GEOAPIFY_API_KEY, geoapify),
    "tavily": (lambda: config.TAVILY_API_KEY, tavily),
    "nebius": (lambda: config.NEBIUS_API_KEY, nebius),
    "tomtom": (lambda: config.TOMTOM_API_KEY, tomtom),
    "mapillary": (lambda: config.MAPILLARY_TOKEN, mapillary),
}


async def _run(name, client):
    key, fn = CHECKS[name]
    if not key():
        return {"status": "not_set"}
    try:
        return await fn(client)
    except httpx.HTTPStatusError as e:
        return {"status": "error", "detail": f"HTTP {e.response.status_code}"}
    except Exception as e:  # network down, timeout, bad JSON
        return {"status": "error", "detail": type(e).__name__}


async def check_all(transport=None):
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT, transport=transport) as client:
        results = await asyncio.gather(*[_run(n, client) for n in CHECKS])
    return dict(zip(CHECKS, results))
