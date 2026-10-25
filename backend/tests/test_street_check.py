import json

import numpy as np
from PIL import Image, ImageDraw

from app.vision import street_check, trafficcam


def _img(kind):
    rng = np.random.default_rng(1)
    if kind == "dark":
        a = rng.normal(14, 5, (240, 320, 3))
    elif kind == "ir":
        g = rng.normal(90, 20, (240, 320)); a = np.stack([g, g, g], -1)
    else:  # lit night street
        a = rng.normal(55, 15, (240, 320, 3)); a[..., 0] += 25
    img = Image.fromarray(np.clip(a, 0, 255).astype("uint8"))
    if kind == "lit":
        d = ImageDraw.Draw(img)
        for i in range(6):
            d.ellipse([20 + i * 50, 20, 45 + i * 50, 45], fill=(255, 240, 200))
    return img


def test_lit_beats_dark():
    lit = street_check.check(_img("lit"), people=3, vehicles=5)
    dark = street_check.check(_img("dark"), people=0, vehicles=0)
    assert lit.street_score > dark.street_score
    assert dark.verdict == "dark_empty" and not dark.ir_mode


def test_infrared_caps_lighting():
    ir = street_check.check(_img("ir"))
    assert ir.ir_mode and ir.lighting_score <= 30


def test_clip_id_and_night():
    code, dt = trafficcam.parse_clip_id("BLR_1651662434.7875617")
    assert code == "BLR" and dt.hour == 16  # 4:37 PM IST
    assert not trafficcam.is_night(dt)
    assert trafficcam.parse_clip_id("not_a_clip") is None


def test_count_objects_labelme(tmp_path):
    p = tmp_path / "frame0.json"
    p.write_text(json.dumps({"shapes": [{"label": "car"}, {"label": "Pedestrian"}, {"label": "auto rickshaw"}]}))
    assert trafficcam.count_objects(p) == (1, 2)
