"""Web search via Tavily for night-safety incident patterns and road closures.
Results are web reports, so they are always labelled PROBABLE, never KNOWN."""
import asyncio
from datetime import datetime, timezone

import httpx

from .. import config

URL = "https://api.tavily.com/search"


async def _search(client, query, kind):
    r = await client.post(URL, headers={"Authorization": f"Bearer {config.TAVILY_API_KEY}"},
                          json={"query": query, "max_results": 4, "search_depth": "basic", "topic": "news"})
    r.raise_for_status()
    now = datetime.now(timezone.utc).isoformat()
    return [{"kind": kind, "title": x.get("title"), "url": x.get("url"),
             "snippet": (x.get("content") or "")[:220], "source": "web", "fetched_at": now}
            for x in r.json().get("results", [])]


async def advisories():
    if not config.TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY not set")
    city = config.CITY_NAME
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
        res = await asyncio.gather(
            _search(client, f"night safety incident women {city}", "incident"),
            _search(client, f"road closure {city} tonight", "closure"),
            return_exceptions=True,
        )
    out = []
    for r in res:
        if isinstance(r, list):
            out.extend(r)
    return out
