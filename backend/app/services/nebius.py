"""Safety / feasibility score from NVIDIA Nemotron on Nebius Token Factory (OpenAI-compatible API).
This is an AI estimate on top of the rule-based score, so it is labelled PROBABLE."""
import json
import re

import httpx

from .. import config

SYSTEM = (
    "You rate night-time routes for workers going home after a late shift in an Indian city. "
    "You receive measured factors for several routes, plus any web reports of past incidents on their roads "
    "(with dates; old reports matter less). Use only that data; do not invent facts. "
    "Reply with JSON only, no markdown: a list with one object per route, in the same order: "
    '[{"route": <index>, "safety_score": <0-100>, "feasibility_score": <0-100>, "note": "<one short sentence>"}]'
)


def _payload(i, route):
    f = route["factors"]
    return {
        "route": i,
        "length_m": route["length_m"],
        "duration_min": round(route["duration_s"] / 60),
        "reach_buffer_min": route["feasibility"]["buffer_min"],
        "factors": {k: {"score": v["score"], "value": v["value"], "confidence": v["label"]} for k, v in f.items()},
        "weather_penalty": route.get("weather_penalty", 0),
        "traffic": (route.get("traffic") or {}).get("level"),
        "incident_reports": [{"road": r["road"], "date": r["published"], "title": r["title"]}
                             for r in route.get("road_reports", [])],
    }


def _num(x):
    try:
        return max(0, min(100, int(x)))
    except (TypeError, ValueError):
        return None


async def score_routes(routes):
    """One call for all routes, so the model can compare them. Returns one result (or None) per route."""
    if not (config.NEBIUS_API_KEY and config.NEBIUS_MODEL) or not routes:
        return [None] * len(routes)
    body = {
        "model": config.NEBIUS_MODEL,
        "temperature": 0.2,
        "max_tokens": 200 + 120 * len(routes),
        # Nemotron reasons before answering by default and used up the token limit; we only need the JSON
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": json.dumps([_payload(i, r) for i, r in enumerate(routes)])}],
    }
    url = config.NEBIUS_BASE_URL.rstrip("/") + "/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT + 18) as client:
            r = await client.post(url, headers={"Authorization": f"Bearer {config.NEBIUS_API_KEY}"}, json=body)
            r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"] or ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
        m = re.search(r"\[.*\]", text, flags=re.S)
        items = json.loads(m.group(0)) if m else []
    except Exception:
        return [None] * len(routes)
    out = [None] * len(routes)
    for i, item in enumerate(x for x in items if isinstance(x, dict)):
        idx = item.get("route", i)
        if isinstance(idx, int) and 0 <= idx < len(routes):
            out[idx] = {"safety_score": _num(item.get("safety_score")),
                        "feasibility_score": _num(item.get("feasibility_score")),
                        "note": item.get("note"), "model": config.NEBIUS_MODEL, "label": "PROBABLE"}
    return out
