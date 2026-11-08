"""Text detail pass, no inpainting support needed: cut the area with text out of a render, enlarge it
for the CGI edit (labels become 2-6x larger), then paste the edited crop back into exactly the same
box: resized back, colour-matched to the original crop (per-channel mean/std), feathered at the edge,
alpha (the silhouette) untouched.

python -I tools/fix_text.py crop  --src RENDER --box x0,y0,x1,y1 --out CROP.png [--width 1024] [--auto-fit]
python -I tools/fix_text.py paste --src RENDER --box-from CROP.json --edited EDITED.png --out OUT.png [--feather 6]

--auto-fit grows the box (centred) to the nearest size whose enlargement is an exact multiple of 32 in
both directions, so the edit is never stretched on the way back. crop writes CROP.json with the final
box; paste reads it with --box-from (or takes --box directly).
"""
import argparse, json, math
import numpy as np
from PIL import Image, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("mode", choices=["crop", "paste"])
ap.add_argument("--src", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--box"); ap.add_argument("--box-from")
ap.add_argument("--width", type=int, default=1024)
ap.add_argument("--auto-fit", action="store_true")
ap.add_argument("--edited"); ap.add_argument("--feather", type=int, default=6)
a = ap.parse_args()
if a.box_from:
    x0, y0, x1, y1 = json.load(open(a.box_from, encoding="utf-8"))["box"]
else:
    x0, y0, x1, y1 = map(int, a.box.split(","))
src = Image.open(a.src).convert("RGBA")

if a.mode == "crop":
    MAX_PX = 1_048_576                      # larger canvases slow the image server down
    bx0, by0, bx1, by1 = x0, y0, x1, y1
    W = a.width - a.width % 32
    while True:
        x0, y0, x1, y1 = bx0, by0, bx1, by1
        if a.auto_fit:
            unit = W // 32                  # box width a multiple of unit -> scale * height step = 32 per m px
            bw = math.ceil((x1 - x0) / unit) * unit; m = bw // unit
            bh = math.ceil((y1 - y0) / m) * m
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            x0, y0 = int(round(cx - bw / 2)), int(round(cy - bh / 2)); x1, y1 = x0 + bw, y0 + bh
            x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(src.width, x0 + bw), min(src.height, y0 + bh)
        H = max(32, round((y1 - y0) * W / (x1 - x0) / 32) * 32)
        if W * H <= MAX_PX or W <= 256:
            break
        W -= 32
    crop = src.crop((x0, y0, x1, y1))
    crop.convert("RGB").resize((W, H), Image.LANCZOS).save(a.out)
    exact = abs(crop.height * W / crop.width - H) < 1e-6
    meta = {"out": a.out, "size": [W, H], "box": [x0, y0, x1, y1], "scale": round(W / crop.width, 4), "exact": exact}
    json.dump(meta, open(a.out.rsplit(".", 1)[0] + ".json", "w", encoding="utf-8"))
    print(json.dumps(meta))
else:
    crop = src.crop((x0, y0, x1, y1))
    ed = Image.open(a.edited).convert("RGB").resize(crop.size, Image.LANCZOS)
    e = np.asarray(ed).astype(np.float32); o = np.asarray(crop.convert("RGB")).astype(np.float32)
    # colour match: the edit may drift in tone; keep the original crop's statistics
    e = (e - e.mean((0, 1))) / (e.std((0, 1)) + 1e-3) * o.std((0, 1)) + o.mean((0, 1))
    ed = Image.fromarray(np.clip(e, 0, 255).astype(np.uint8))
    mask = Image.new("L", crop.size, 0)
    f = a.feather
    mask.paste(255, (f, f, crop.width - f, crop.height - f))
    mask = mask.filter(ImageFilter.GaussianBlur(f / 2))
    out = src.copy()
    patch = Image.composite(ed.convert("RGBA"), crop, mask)
    patch.putalpha(crop.getchannel("A"))          # never change the silhouette
    out.paste(patch, (x0, y0))
    out.save(a.out)
    print(json.dumps({"out": a.out, "box": [x0, y0, x1, y1]}))
