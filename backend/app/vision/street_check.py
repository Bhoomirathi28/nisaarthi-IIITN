"""Street check: how lit and how active a street looks in a camera frame.

Works on any frame: a CCTV still (TrafficCAM), or later a rider's phone (Rider Eyes).
Uses only numpy + Pillow, so it runs on a laptop with no GPU. Counts of people and
vehicles come from dataset annotations when available, or from an optional detector.

What it measures
  brightness     average light level of the scene (0-255 luma)
  dark_share     share of the frame that is very dark
  light_sources  share of the frame that is very bright (street lights, shopfronts, headlights)
  ir_mode        the camera switched to black-and-white infrared, which CCTV does when
                 there isn't enough light, so it signals a poorly lit street
  people / vehicles  activity on the street
"""
from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image

DARK_LUMA = 40
BRIGHT_LUMA = 200
IR_SATURATION = 0.06


@dataclass
class StreetCheck:
    brightness: float
    dark_share: float
    light_sources: float
    ir_mode: bool
    people: int | None
    vehicles: int | None
    lighting_score: int
    activity_score: int | None
    street_score: int
    verdict: str  # well_lit_busy, well_lit_quiet, dim_busy, dim_quiet, dark_busy, dark_empty

    def to_dict(self):
        return asdict(self)


def _load(img, max_side=640):
    if not isinstance(img, Image.Image):
        img = Image.open(img)
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))  # speed; lighting stats don't need full resolution
    return img


def lighting(img):
    rgb = np.asarray(img, dtype=np.float32) / 255.0
    luma = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]) * 255
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    saturation = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return {
        "brightness": float(luma.mean()),
        "dark_share": float((luma < DARK_LUMA).mean()),
        "light_sources": float((luma > BRIGHT_LUMA).mean()),
        # Black-and-white but not simply black: the camera is using infrared
        "ir_mode": bool(saturation.mean() < IR_SATURATION and luma.mean() > 35),
    }


def _clamp(x):
    return max(0.0, min(1.0, x))


def score(light, people=None, vehicles=None):
    lit = _clamp((light["brightness"] - 25) / 75)            # 25 = very dark, 100+ = well lit
    lit = 0.6 * lit + 0.25 * _clamp(light["light_sources"] / 0.04) + 0.15 * (1 - light["dark_share"])
    if light["ir_mode"]:
        lit = min(lit, 0.3)                                   # camera needed infrared: poor lighting
    lighting_score = round(100 * _clamp(lit))

    activity_score = None
    if people is not None or vehicles is not None:
        p, v = people or 0, vehicles or 0
        activity_score = round(100 * _clamp((p * 2 + v) / 12))  # a person counts double: eyes on the street

    if activity_score is None:
        street = lighting_score
    else:
        street = round(0.6 * lighting_score + 0.4 * activity_score)

    lit_word = "well_lit" if lighting_score >= 60 else "dim" if lighting_score >= 35 else "dark"
    busy = activity_score is not None and activity_score >= 35
    if lit_word == "dark":
        verdict = "dark_busy" if busy else "dark_empty"
    else:
        verdict = f"{lit_word}_{'busy' if busy else 'quiet'}"
    return lighting_score, activity_score, street, verdict


def check(img, people=None, vehicles=None):
    light = lighting(_load(img))
    lighting_score, activity_score, street, verdict = score(light, people, vehicles)
    return StreetCheck(
        brightness=round(light["brightness"], 1), dark_share=round(light["dark_share"], 3),
        light_sources=round(light["light_sources"], 4), ir_mode=light["ir_mode"],
        people=people, vehicles=vehicles, lighting_score=lighting_score,
        activity_score=activity_score, street_score=street, verdict=verdict,
    )


def check_clip(frames, people=None, vehicles=None):
    """Average over several frames of one clip; more stable than a single frame."""
    checks = [check(f, people, vehicles) for f in frames]
    if not checks:
        raise ValueError("no frames")
    mean = lambda k: sum(getattr(c, k) for c in checks) / len(checks)
    light = {"brightness": mean("brightness"), "dark_share": mean("dark_share"),
             "light_sources": mean("light_sources"),
             "ir_mode": sum(c.ir_mode for c in checks) > len(checks) / 2}
    lighting_score, activity_score, street, verdict = score(light, people, vehicles)
    return StreetCheck(
        brightness=round(light["brightness"], 1), dark_share=round(light["dark_share"], 3),
        light_sources=round(light["light_sources"], 4), ir_mode=light["ir_mode"],
        people=people, vehicles=vehicles, lighting_score=lighting_score,
        activity_score=activity_score, street_score=street, verdict=verdict,
    )
