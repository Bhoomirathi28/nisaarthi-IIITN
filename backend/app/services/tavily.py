"""Web search via Tavily for past incidents on the roads a route uses, and road closures.
Results are web reports, so they are labelled PROBABLE (OUTDATED when over a year old),
never KNOWN. Every report shows its date so an old story isn't read as a recent one."""
import asyncio
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from .. import config
from ..engine import confidence as C

URL = "https://api.tavily.com/search"
NEWS_DAYS = 730          # how far back to look for incidents on a road
OLD_AFTER_DAYS = 365     # older reports are labelled OUTDATED
CLOSURE_WORDS = re.compile(r"\b(closed|closure|diversion|diverted|blocked|shut)\b", re.I)
SUFFIXES = {"road": "rd", "rd": "road", "marg": "marg", "street": "st", "st": "street"}


def road_variants(road):
    """Ways a road is written in news: 'Wardha Road' -> {'wardha road', 'wardha rd'}.
    The full name is required, so 'Wardha Road' does not match a story about Wardha town."""
    name = re.sub(r"\s+", " ", road.strip().lower())
    out = {name}
    parts = name.rsplit(" ", 1)
    if len(parts) == 2 and parts[1] in SUFFIXES:
        out.add(f"{parts[0]} {SUFFIXES[parts[1]]}")
    return out


def mentions(text, road):
    text = re.sub(r"\s+", " ", (text or "").lower())
    return any(re.search(rf"\b{re.escape(v)}\b", text) for v in road_variants(road))


def _date(value):
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


def _label(published, now):
    if published and now - published > timedelta(days=OLD_AFTER_DAYS):
        return C.OUTDATED
    return C.PROBABLE


async def _search(client, query, days):
    r = await client.post(URL, headers={"Authorization": f"Bearer {config.TAVILY_API_KEY}"},
                          json={"query": query, "max_results": 8, "search_depth": "basic",
                                "topic": "news", "days": days})
    r.raise_for_status()
    return r.json().get("results", [])


def _report(x, kind, road, now):
    published = _date(x.get("published_date"))
    return {"kind": kind, "road": road, "title": x.get("title"), "url": x.get("url"),
            "snippet": (x.get("content") or "")[:220],
            "published": published.date().isoformat() if published else None,
            "label": _label(published, now), "source": "web", "fetched_at": now.isoformat()}


async def road_reports(road):
    """Past incident reports that name this road."""
    if not config.TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY not set")
    now = datetime.now(timezone.utc)
    query = f'"{road}" {config.CITY_NAME} accident OR crime OR robbery OR harassment OR incident'
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
        results = await _search(client, query, NEWS_DAYS)
    out = [_report(x, "incident", road, now) for x in results
           if mentions(f"{x.get('title', '')} {x.get('content', '')}", road)]
    out.sort(key=lambda r: r["published"] or "", reverse=True)
    return out[:3]


async def closures():
    """City-wide road closure news from the last few days."""
    if not config.TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY not set")
    now = datetime.now(timezone.utc)
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
        results = await _search(client, f"road closure {config.CITY_NAME} tonight", 3)
    # Keep only stories that are actually about a closed or diverted road
    about_closure = [x for x in results if CLOSURE_WORDS.search(f"{x.get('title', '')} {x.get('content', '')}")]
    return [_report(x, "closure", None, now) for x in about_closure[:3]]

