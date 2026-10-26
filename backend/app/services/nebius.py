"""Safety / feasibility score from NVIDIA Nemotron on Nebius Token Factory (OpenAI-compatible API).
This is an AI estimate on top of the rule-based score, so it is labelled PROBABLE."""
import asyncio
import json
import re

import httpx

from .. import config

SYSTEM = (
    "You rate night-time routes for workers going home after a late shift in an Indian city. "
    "You receive measured factors for one route. Use only those numbers; do not invent facts. "
    "Reply with JSON only, no markdown: "
    '{"safety_score": <0-100>, "feasibility_score": <0-100>, "note": "<one short sentence>"}'
)


def _payload(route):
    f = route["factors"]
    return {
        "length_m": route["length_m"],
        "duration_min": round(route["duration_s"] / 60),
        "reach_buffer_min": route["feasibility"]["buffer_min"],
        "factors": {k: {"score": v["score"], "value": v["value"], "confidence": v["label"]} for k, v in f.items()},
        "weather_penalty": route.get("weather_penalty", 0),
    }


async def _one(client, route):
    body = {
        "model": config.NEBIUS_MODEL,
        "temperature": 0.2,
        "max_tokens": 300,
        # Nemotron reasons before answering by default and used up the token limit; we only need the JSON
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": json.dumps(_payload(route))}],
    }
    url = config.NEBIUS_BASE_URL.rstrip("/") + "/chat/completions"
    r = await client.post(url, headers={"Authorization": f"Bearer {config.NEBIUS_API_KEY}"}, json=body)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"] or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"\{.*\}", text, flags=re.S)
    data = json.loads(m.group(0)) if m else {}
    return {
        "safety_score": int(data.get("safety_score")) if data.get("safety_score") is not None else None,
        "feasibility_score": int(data.get("feasibility_score")) if data.get("feasibility_score") is not None else None,
        "note": data.get("note"),
        "model": config.NEBIUS_MODEL,
        "label": "PROBABLE",
    }


async def score_routes(routes):
    if not (config.NEBIUS_API_KEY and config.NEBIUS_MODEL):
        return [None] * len(routes)
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT + 8) as client:
        res = await asyncio.gather(*[_one(client, r) for r in routes], return_exceptions=True)
    return [r if isinstance(r, dict) else None for r in res]
