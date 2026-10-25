"""Reader for the TrafficCAM dataset (fixed traffic cameras, eight Indian cities).

Dataset: https://math-ml-x.github.io/TrafficCAM/  (download: scripts/download_trafficcam.sh)
Paper:   Deng et al., "TrafficCAM: A Versatile Dataset for Traffic Flow Segmentation",
         IEEE Transactions on Intelligent Transportation Systems.
The repository has no licence file: use it with citation, and don't re-publish the images.

Layout after download:
  TrafficCAM/raw/FirstFrame_annotate/<CITY>_<unix_time>/frame0.json, frame0.jpg ... frame58.jpg
  TrafficCAM/raw/Fully_annotate/<CITY>_<unix_time>/frameN.json + frameN.jpg
The folder name gives the city code and the recording time, which is how night clips are found.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
NIGHT_START, NIGHT_END = 19, 6  # 7 PM to 6 AM local time

# Codes seen in folder names. Unknown codes are shown as-is rather than guessed.
CITY_NAMES = {"BLR": "Bengaluru"}

PERSON_WORDS = ("person", "pedestrian", "people", "human")
VEHICLE_WORDS = ("car", "bus", "truck", "bike", "motor", "auto", "rickshaw", "cycle", "van",
                 "vehicle", "lorry", "tempo", "scooter", "jeep", "tractor", "lcv")

_ID = re.compile(r"^([A-Za-z]+)_(\d{9,11})(?:\.\d+)?$")


def parse_clip_id(name):
    """'BLR_1651662434.7875617' -> ('BLR', datetime in IST). None if the name doesn't match."""
    m = _ID.match(name)
    if not m:
        return None
    code, ts = m.group(1).upper(), int(m.group(2))
    return code, datetime.fromtimestamp(ts, tz=IST)


def is_night(dt):
    return dt.hour >= NIGHT_START or dt.hour < NIGHT_END


def _frame_no(p):
    m = re.search(r"(\d+)", p.stem)
    return int(m.group(1)) if m else 0


def count_objects(annotation_path):
    """People and vehicle counts from one annotation file.

    Handles LabelMe-style {"shapes": [{"label": ...}]} and COCO-style
    {"annotations": [...], "categories": [...]}. Returns (None, None) for unknown formats.
    """
    try:
        data = json.loads(Path(annotation_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    labels = []
    if isinstance(data, dict) and isinstance(data.get("shapes"), list):
        labels = [str(s.get("label", "")) for s in data["shapes"]]
    elif isinstance(data, dict) and isinstance(data.get("annotations"), list):
        cats = {c.get("id"): str(c.get("name", "")) for c in data.get("categories", [])}
        labels = [cats.get(a.get("category_id"), "") for a in data["annotations"]]
    elif isinstance(data, list):
        labels = [str(x.get("label") or x.get("category") or "") for x in data if isinstance(x, dict)]
    else:
        return None, None
    labels = [l.lower() for l in labels]
    people = sum(any(w in l for w in PERSON_WORDS) for l in labels)
    vehicles = sum(any(w in l for w in VEHICLE_WORDS) for l in labels)
    return people, vehicles


def iter_clips(root):
    """Yield one dict per clip folder found under root (any depth)."""
    root = Path(root)
    for folder in sorted(p for p in root.rglob("*") if p.is_dir()):
        parsed = parse_clip_id(folder.name)
        if not parsed:
            continue
        frames = sorted(folder.glob("*.jpg"), key=_frame_no)
        if not frames:
            continue
        code, recorded = parsed
        annotations = sorted(folder.glob("*.json"), key=_frame_no)
        yield {
            "clip_id": folder.name,
            "city_code": code,
            "city": CITY_NAMES.get(code, code),
            "recorded_at": recorded.isoformat(),
            "night_by_time": is_night(recorded),
            "frames": frames,
            "annotations": annotations,
            "subset": "fully_annotated" if "Fully" in str(folder) else "first_frame_annotated",
        }
