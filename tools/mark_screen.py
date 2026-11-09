"""Screen stage: find the display window on BODY.png, paint the whole window as dark glass, and cut the
hole at the exact native aspect, centred in the window.

python tools/mark_screen.py BODY.png --approx x,y,w,h --native 176x220 --out-skin SKIN.png
       --out-overlay CHECK.png [--window x0,y0,x1,y1] [--spec-mm w,h] [--margin-mm 0.5]

The window is the inside edge of the bezel: everything inside it is display glass (the black LCD
border and whatever the render drew on the screen). Automatic: each side of the seed rectangle
(--approx, the template's screen placed on the body) moves to the strongest edge in a band around it
where the inside is darker than the outside (bezel to glass). --window gives it by hand (body pixels).

The hole is the largest native-aspect rectangle inside the window less --margin-mm on every side, no
larger than the spec size (+8%), centred in the window. The window (rounded corners) is painted glass
colour first, so no rendered screen content is left around the hole.

Visible border: on the finished skin, the dark band from each hole edge out to the bezel; when one side
is wider (dark LCD border the window left unpainted), the hole is re-centred in the whole dark area.
Not on a dark front (the band runs more than 2 mm past the window): there the window alone counts.

Checks printed under "checks": hole centring in the window (mm, both axes), window centre vs the
body's axis (% of width), window size vs spec, and edge strength per side (a weak side means the
window was probably found in the wrong place).
"""
import argparse, json
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("body")
ap.add_argument("--approx", required=True)
ap.add_argument("--native", required=True)
ap.add_argument("--window", help="window x0,y0,x1,y1 on BODY.png (by hand; each side is refined to the nearest strong edge within 7 px)")
ap.add_argument("--no-refine", action="store_true")
ap.add_argument("--spec-mm", help="spec screen size w,h in mm")
ap.add_argument("--margin-mm", type=float, default=0.5)
ap.add_argument("--px-per-mm", type=float, default=12.0)
ap.add_argument("--out-skin", required=True); ap.add_argument("--out-overlay", required=True)
a = ap.parse_args()
ppm = a.px_per_mm
im = np.asarray(Image.open(a.body).convert("RGBA")).copy()
Y = cv2.GaussianBlur(cv2.cvtColor(im[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), 1.2)
x, y, w, h = map(int, a.approx.split(","))
nw, nh = map(int, a.native.lower().split("x"))
alpha = im[..., 3] >= 128


def body_axis(r0, r1):
    spans = np.array([(np.where(alpha[r])[0].min(), np.where(alpha[r])[0].max()) for r in range(r0, r1, 2) if alpha[r].any()], float)
    wd = spans[:, 1] - spans[:, 0] + 1; core = spans[np.abs(wd - np.median(wd)) <= 0.01 * np.median(wd)]
    core = core if len(core) >= 5 else spans
    return float(np.median(core.mean(1))), float(np.median(core[:, 1] - core[:, 0] + 1))


def profile(side, lo, hi):
    """median luminance across the side's central 50%, at positions lo..hi (x for left/right, y for top/bottom)."""
    pos = np.arange(lo, hi)
    if side in ("left", "right"):
        band = Y[int(y + 0.25 * h): int(y + 0.75 * h)]
        return pos, np.array([np.median(band[:, max(0, min(Y.shape[1] - 1, p))]) for p in pos])
    band = Y[:, int(x + 0.25 * w): int(x + 0.75 * w)]
    return pos, np.array([np.median(band[max(0, min(Y.shape[0] - 1, p))]) for p in pos])


def find_edge(side):
    """strongest step where outside is brighter than inside, in a band of -22%..+12% around the seed side."""
    size = w if side in ("left", "right") else h
    est = {"left": x, "right": x + w, "top": y, "bottom": y + h}[side]
    out_dir = -1 if side in ("left", "top") else 1
    lo, hi = sorted((est + out_dir * int(0.22 * size), est - out_dir * int(0.12 * size)))
    pos, p = profile(side, lo - 4, hi + 4)
    d = 3; score = np.zeros(len(p))
    for i in range(d, len(p) - d):
        outside, inside = (p[i - d], p[i + d]) if out_dir < 0 else (p[i + d], p[i - d])
        score[i] = outside - inside
    i = int(np.argmax(score)); edge = int(pos[i])
    strength = float(score[i] / max(np.median(np.abs(score[d:-d])), 1.0))
    return edge, round(strength, 1)


def refine(side, est, r=7):
    """a hand-given side moved to the strongest step (either direction) within +-r px."""
    pos, p = profile(side, est - r - 3, est + r + 4)
    sc = [abs(p[i + 3] - p[i - 3]) for i in range(3, len(p) - 3)]
    return int(pos[3 + int(np.argmax(sc))])


if a.window:
    WL, WT, WR, WB = map(int, a.window.split(","))
    if not a.no_refine:
        x, y, w, h = WL, WT, WR - WL, WB - WT     # profiles across the hand-given window's own sides
        WL, WR, WT, WB = refine("left", WL), refine("right", WR), refine("top", WT), refine("bottom", WB)
    strength = {"left": None, "right": None, "top": None, "bottom": None}
else:
    (WL, sl), (WR, sr), (WT, st), (WB, sb) = find_edge("left"), find_edge("right"), find_edge("top"), find_edge("bottom")
    strength = {"left": sl, "right": sr, "top": st, "bottom": sb}
ww, wh = WR - WL, WB - WT

# hole: native aspect, inside the window less the margin, capped at the spec size, centred in the window
m = a.margin_mm * ppm
fw, fh = ww - 2 * m, wh - 2 * m
if fw / fh > nw / nh: hw, hh = fh * nw / nh, fh
else: hw, hh = fw, fw * nh / nw
if a.spec_mm:
    sw_, sh_ = [float(v) * ppm * 1.08 for v in a.spec_mm.split(",")]
    k = min(1.0, sw_ / hw, sh_ / hh); hw, hh = hw * k, hh * k
hw, hh = int(round(hw)), int(round(hh))
cx, cy = (WL + WR) / 2, (WT + WB) / 2
L, T = int(round(cx - hw / 2)), int(round(cy - hh / 2)); R, B = L + hw, T + hh

# paint the window as glass (rounded corners), then cut the hole
skin = im.copy()
glass = Image.new("L", (skin.shape[1], skin.shape[0]), 0)
ImageDraw.Draw(glass).rounded_rectangle([WL, WT, WR - 1, WB - 1], radius=max(2, int(0.6 * ppm)), fill=255)
gm = np.asarray(glass) > 0
skin[gm, 0], skin[gm, 1], skin[gm, 2] = 14, 14, 16
skin[T:B, L:R, 3] = 0; skin[T:B, L:R, :3] = 0
Image.fromarray(skin, "RGBA").save(a.out_skin)


def visible_border():
    """what a viewer sees: on the finished skin, the dark band between the hole and the bezel, per side
    (median over the side's middle 60%), in px. The band ends where luminance rises above 24 (painted glass is 14)."""
    Ls = cv2.cvtColor(skin[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32); res = {}
    for side in ("left", "right", "top", "bottom"):
        vals = []
        if side in ("left", "right"):
            for r in range(int(T + 0.2 * hh), int(B - 0.2 * hh), 3):
                c, step = (L - 1, -1) if side == "left" else (R, 1); n = 0
                while 0 <= c < Ls.shape[1] and Ls[r, c] < 24 and n < 8 * ppm: c += step; n += 1
                vals.append(n)
        else:
            for c in range(int(L + 0.2 * hw), int(R - 0.2 * hw), 3):
                r, step = (T - 1, -1) if side == "top" else (B, 1); n = 0
                while 0 <= r < Ls.shape[0] and Ls[r, c] < 24 and n < 8 * ppm: r += step; n += 1
                vals.append(n)
        res[side] = float(np.median(vals))
    return res

vb = visible_border()
# dark front: on some side the dark band runs more than 2 mm past the window, so it is the phone's own dark
# body, not unpainted display glass; the visible border means nothing there and the hole stays centred in the window
ext = {"left": vb["left"] - (L - WL), "right": vb["right"] - (WR - R), "top": vb["top"] - (T - WT), "bottom": vb["bottom"] - (WB - B)}
dark_front = max(ext.values()) > 2 * ppm
if not dark_front and max(abs(vb["left"] - vb["right"]), abs(vb["top"] - vb["bottom"])) / ppm > 0.25:
    # balance: centre the hole in the whole dark area the viewer sees (painted window + any unpainted
    # dark glass beyond it), then cut again
    cx, cy = (L - vb["left"] + R + vb["right"]) / 2, (T - vb["top"] + B + vb["bottom"]) / 2
    L, T = int(round(cx - hw / 2)), int(round(cy - hh / 2)); R, B = L + hw, T + hh
    WL, WT = min(WL, L - int(round(m))), min(WT, T - int(round(m))); WR, WB = max(WR, R + int(round(m))), max(WB, B + int(round(m)))
    ww, wh = WR - WL, WB - WT
    skin = im.copy(); glass = Image.new("L", (skin.shape[1], skin.shape[0]), 0)
    ImageDraw.Draw(glass).rounded_rectangle([WL, WT, WR - 1, WB - 1], radius=max(2, int(0.6 * ppm)), fill=255)
    gm = np.asarray(glass) > 0; skin[gm, 0], skin[gm, 1], skin[gm, 2] = 14, 14, 16
    skin[T:B, L:R, 3] = 0; skin[T:B, L:R, :3] = 0
    Image.fromarray(skin, "RGBA").save(a.out_skin)
    vb = visible_border()
axis, bwid = body_axis(max(0, WT), min(im.shape[0], WB))
if dark_front:   # judge the border inside the window only
    vb = {"left": L - WL, "right": WR - R, "top": T - WT, "bottom": WB - B}
checks = {
    "dark_front": dark_front,
    "visible_border_mm": {k: round(v / ppm, 2) for k, v in vb.items()},
    "visible_border_diff_mm": round(max(abs(vb["left"] - vb["right"]), abs(vb["top"] - vb["bottom"])) / ppm, 2),
    "hole_centre_diff_mm": round(max(abs((L - WL) - (WR - R)), abs((T - WT) - (WB - B))) / ppm, 2),
    "margins_mm": {"left": round((L - WL) / ppm, 2), "right": round((WR - R) / ppm, 2), "top": round((T - WT) / ppm, 2), "bottom": round((WB - B) / ppm, 2)},
    "window_centre_x_pct": round(100 * abs(cx - axis) / bwid, 2),
    "window_mm": [round(ww / ppm, 2), round(wh / ppm, 2)],
    "edge_strength": strength,
}
if a.spec_mm:
    sw_, sh_ = [float(v) for v in a.spec_mm.split(",")]
    checks["window_vs_spec"] = [round(ww / ppm / sw_, 3), round(wh / ppm / sh_, 3)]

# check image: body (uncut) with the window outline (green), the hole (magenta, translucent), margins in mm
ov = Image.fromarray(im, "RGBA"); lay = Image.new("RGBA", ov.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
d.rectangle([L, T, R - 1, B - 1], fill=(255, 0, 255, 70), outline=(255, 0, 255, 255), width=2)
d.rectangle([WL, WT, WR - 1, WB - 1], outline=(0, 255, 0, 255), width=2)
d.line([(axis, WT - 30), (axis, WB + 30)], fill=(255, 255, 0, 200), width=1)
ov.alpha_composite(lay); pad = int(4 * ppm)
crop = ov.crop((max(0, WL - pad), max(0, WT - pad), min(ov.width, WR + pad), min(ov.height, WB + pad))).convert("RGB")
crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS); dd = ImageDraw.Draw(crop)
try: f = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 22)
except OSError: f = ImageFont.load_default()
mg = checks["margins_mm"]; dd.rectangle([0, 0, crop.width, 30], fill=(0, 0, 0))
dd.text((6, 3), f"margins L {mg['left']}  R {mg['right']}  T {mg['top']}  B {mg['bottom']} mm   window {checks['window_mm'][0]}x{checks['window_mm'][1]} mm", fill=(255, 255, 0), font=f)
crop.save(a.out_overlay)

print(json.dumps({"approx": [x, y, w, h], "window_px": [WL, WT, ww, wh], "screen_px": [L, T, hw, hh],
                  "screen_mm": [round(L / ppm, 2), round(T / ppm, 2), round(hw / ppm, 2), round(hh / ppm, 2)],
                  "aspect_w_h": round(hw / hh, 4), "native_aspect_w_h": round(nw / nh, 4),
                  "aspect_error_pct": round(100 * ((hw / hh) / (nw / nh) - 1), 2), "manual": bool(a.window), "checks": checks}))
