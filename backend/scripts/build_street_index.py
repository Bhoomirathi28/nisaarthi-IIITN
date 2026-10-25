"""Run the street check on TrafficCAM and save the results.

  python scripts/build_street_index.py                 # all clips
  python scripts/build_street_index.py --night-only    # only clips recorded 7 PM - 6 AM
  python scripts/build_street_index.py --limit 50 --sheet

Writes data/street_index.json (scores only, no images) and, with --sheet,
data/night_contact_sheet.jpg: a grid of night clips with their scores, for the pitch.
"""
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.vision import street_check, trafficcam  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
FRAMES_PER_CLIP = 5


def sample(frames, n=FRAMES_PER_CLIP):
    if len(frames) <= n:
        return frames
    step = (len(frames) - 1) / (n - 1)
    return [frames[round(i * step)] for i in range(n)]


def contact_sheet(rows, out_path, cols=4, tile=(320, 180)):
    from PIL import Image, ImageDraw
    rows = rows[: cols * 6]
    if not rows:
        return
    sheet = Image.new("RGB", (cols * tile[0], ((len(rows) + cols - 1) // cols) * (tile[1] + 34)), (27, 24, 48))
    draw = ImageDraw.Draw(sheet)
    for i, r in enumerate(rows):
        x, y = (i % cols) * tile[0], (i // cols) * (tile[1] + 34)
        img = Image.open(r["_frame"]).convert("RGB")
        img.thumbnail(tile)
        sheet.paste(img, (x, y))
        label = f'{r["city"]} {r["recorded_at"][11:16]}  street {r["check"]["street_score"]}  {r["check"]["verdict"]}'
        draw.text((x + 6, y + tile[1] + 8), label, fill=(243, 232, 210))
    sheet.save(out_path, quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(BASE / "datasets" / "TrafficCAM" / "raw"))
    ap.add_argument("--night-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sheet", action="store_true")
    ap.add_argument("--out", default=str(BASE / "data" / "street_index.json"))
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        sys.exit(f"Dataset not found at {root}. Run scripts/download_trafficcam.sh first.")

    rows = []
    for clip in trafficcam.iter_clips(root):
        if args.night_only and not clip["night_by_time"]:
            continue
        people = vehicles = None
        if clip["annotations"]:
            people, vehicles = trafficcam.count_objects(clip["annotations"][0])
        result = street_check.check_clip(sample(clip["frames"]), people, vehicles)
        dark_by_light = result.brightness < 70 or result.ir_mode
        rows.append({
            "clip_id": clip["clip_id"], "city_code": clip["city_code"], "city": clip["city"],
            "recorded_at": clip["recorded_at"], "subset": clip["subset"],
            "night_by_time": clip["night_by_time"], "night_by_light": dark_by_light,
            "check": result.to_dict(), "_frame": str(clip["frames"][0]),
        })
        if len(rows) % 100 == 0:
            print(f"{len(rows)} clips checked…")
        if args.limit and len(rows) >= args.limit:
            break

    night = [r for r in rows if r["night_by_time"]]
    summary = {
        "source": "TrafficCAM (Deng et al., IEEE T-ITS), https://math-ml-x.github.io/TrafficCAM/",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "clips": len(rows),
        "night_clips": len(night),
        "night_by_time_and_light_agree": sum(r["night_by_time"] == r["night_by_light"] for r in rows),
        "clips_per_city": dict(Counter(r["city"] for r in rows)),
        "night_clips_per_city": dict(Counter(r["city"] for r in night)),
        "night_verdicts": dict(Counter(r["check"]["verdict"] for r in night)),
        "ir_mode_at_night": sum(r["check"]["ir_mode"] for r in night),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    out.write_text(json.dumps({"summary": summary, "clips": clean}, indent=1))
    print(json.dumps(summary, indent=2))
    print(f"Saved {out}")

    if args.sheet:
        picks = sorted(night, key=lambda r: r["check"]["street_score"])
        picks = picks[:8] + picks[-8:] if len(picks) > 16 else picks  # darkest and best lit
        sheet_path = out.with_name("night_contact_sheet.jpg")
        contact_sheet(picks, sheet_path)
        print(f"Saved {sheet_path}")


if __name__ == "__main__":
    main()
