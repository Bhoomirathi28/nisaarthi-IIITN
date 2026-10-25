"""Places from OpenStreetMap via Overpass: shops, food, pharmacies, petrol pumps, ATMs,
police, hospitals, transport, and CCTV (man_made=surveillance)."""
from datetime import datetime, timezone

import httpx

from .. import config

QUERY = """
[out:json][timeout:25];
(
  nwr["shop"]({b});
  nwr["amenity"~"^(pharmacy|fuel|hospital|clinic|police|cafe|restaurant|fast_food|atm|bus_station|taxi)$"]({b});
  node["highway"="bus_stop"]({b});
  nwr["railway"="station"]({b});
  node["man_made"="surveillance"]({b});
);
out center tags 400;
"""

AMENITY_KIND = {
    "pharmacy": "pharmacy", "fuel": "fuel", "hospital": "hospital", "clinic": "hospital",
    "police": "police", "cafe": "food", "restaurant": "food", "fast_food": "food", "atm": "atm",
    "bus_station": "transport", "taxi": "transport",
}


def _kind(tags):
    if tags.get("man_made") == "surveillance":
        return "cctv"
    if tags.get("amenity") in AMENITY_KIND:
        return AMENITY_KIND[tags["amenity"]]
    if tags.get("highway") == "bus_stop" or tags.get("railway") == "station":
        return "transport"
    if "shop" in tags:
        return "shop"
    return None


async def places(bbox):
    s, w, n, e = bbox
    q = QUERY.format(b=f"{s},{w},{n},{e}")
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT + 15) as client:
        r = await client.post(config.OVERPASS_URL, data={"data": q})
        r.raise_for_status()
        elements = r.json().get("elements", [])
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for el in elements:
        tags = el.get("tags", {})
        kind = _kind(tags)
        if not kind:
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        out.append({
            "id": f"osm-{el['type']}-{el['id']}",
            "kind": kind,
            "name": tags.get("name") or tags.get("name:en"),
            "lat": lat, "lon": lon,
            "opening_hours": tags.get("opening_hours"),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "source": "live",
            "fetched_at": now,
        })
    return out
