"""Screen stage (separate from the cutout): take an approximate screen rectangle from a marker
(a vision model or a person), snap each side to the strongest straight edge nearby, cut the hole.

python -I tools/mark_screen.py BODY.png --approx x,y,w,h --native 176x220 --out-skin SKIN.png
       --out-overlay OVERLAY.png [--search 0.06] [--inset 0]
Prints the refined rect (px and mm), its aspect vs the native panel, and how far each side moved.
"""
import argparse, json
import numpy as np
import cv2
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("body")
ap.add_argument("--approx", required=True)
ap.add_argument("--native", required=True)
ap.add_argument("--px-per-mm", type=float, default=12.0)
ap.add_argument("--search", type=float, default=0.06, help="search band per side, fraction of the rect size")
ap.add_argument("--inset", type=int, default=0, help="shrink the hole by N px after snapping")
ap.add_argument("--fit-native", action="store_true", help="shrink the hole to the exact native aspect inside the glass")
ap.add_argument("--snap", choices=["near", "strongest", "none"], default="near",
                help="near: the strong edge closest to the guess (default); strongest: the strongest edge in the band; none: keep the guess")
ap.add_argument("--fill-border", action="store_true", help="paint the display area left around the exact-aspect hole near-black")
ap.add_argument("--out-skin", required=True); ap.add_argument("--out-overlay", required=True)
a = ap.parse_args()

im = np.asarray(Image.open(a.body).convert("RGBA"))
g = cv2.cvtColor(im[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
g = cv2.GaussianBlur(g, (0, 0), 1.0)
gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)); gy = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
x, y, w, h = map(int, a.approx.split(","))
nw, nh = map(int, a.native.lower().split("x"))


def pick(pos, prof, est, size):
    """the strongest edge (strongest) or the strong edge nearest the guess (near: strength weighted by
    a Gaussian of the distance, sigma 2.5% of the screen size, among edges at least 35% of the max)."""
    if a.snap == "none":
        return est
    if a.snap == "strongest":
        return int(pos[int(np.argmax(prof))])
    w = np.exp(-((pos - est) / (0.025 * size)) ** 2) * (prof >= 0.35 * prof.max())
    return int(pos[int(np.argmax(prof * w))])


def snap_vertical(x_est, y0, y1, band):
    """column for a vertical side: mean |d/dx| over the middle 70% of the side."""
    ya, yb = int(y0 + 0.15 * (y1 - y0)), int(y1 - 0.15 * (y1 - y0))
    xs = np.arange(max(1, x_est - band), min(g.shape[1] - 1, x_est + band + 1))
    prof = np.array([gx[ya:yb, c].mean() for c in xs])
    return pick(xs, prof, x_est, w), float(prof.max()), float(np.median(prof))


def snap_horizontal(y_est, x0, x1, band):
    xa, xb = int(x0 + 0.15 * (x1 - x0)), int(x1 - 0.15 * (x1 - x0))
    ys = np.arange(max(1, y_est - band), min(g.shape[0] - 1, y_est + band + 1))
    prof = np.array([gy[r, xa:xb].mean() for r in ys])
    return pick(ys, prof, y_est, h), float(prof.max()), float(np.median(prof))


bx, by = max(2, int(a.search * w)), max(2, int(a.search * h))
L, sl, ml = snap_vertical(x, y, y + h, bx)
R, sr, mr = snap_vertical(x + w, y, y + h, bx)
T, st, mt = snap_horizontal(y, L, R, by)
B, sb, mb = snap_horizontal(y + h, L, R, by)
# the gradient peak sits on the boundary; the hole starts one pixel inside it
off = 0 if a.snap == "none" else 1
L, T, R, B = L + off + a.inset, T + off + a.inset, R - a.inset, B - a.inset
glass = [L, T, R - L, B - T]
if a.fit_native:
    # largest rectangle with the exact native aspect inside the snapped glass, centred:
    # the leftover glass stays as a thin black border, the bezel is never cut
    gw, gh = R - L, B - T
    if gw / gh > nw / nh:
        fw, fh = round(gh * nw / nh), gh
    else:
        fw, fh = gw, round(gw * nh / nw)
    L, T = L + (gw - fw) // 2, T + (gh - fh) // 2
    R, B = L + fw, T + fh
rw, rh = R - L, B - T

skin = im.copy()
if a.fill_border:   # what is left of the rendered display around the exact hole becomes the LCD's black border
    gl, gt, gw_, gh_ = glass; skin[gt:gt + gh_, gl:gl + gw_, :3] = (14, 14, 16)
skin[T:B, L:R, 3] = 0; skin[T:B, L:R, :3] = 0
Image.fromarray(skin, "RGBA").save(a.out_skin)
ov = Image.fromarray(im, "RGBA").convert("RGB"); d = ImageDraw.Draw(ov)
d.rectangle([x, y, x + w - 1, y + h - 1], outline=(255, 200, 0))      # marker's guess
d.rectangle([L, T, R - 1, B - 1], outline=(255, 0, 255))              # snapped hole
ov.save(a.out_overlay)

ppm = a.px_per_mm
print(json.dumps({
    "approx": [x, y, w, h], "glass_px": glass, "screen_px": [L, T, rw, rh],
    "screen_mm": [round(L / ppm, 2), round(T / ppm, 2), round(rw / ppm, 2), round(rh / ppm, 2)],
    "aspect_w_h": round(rw / rh, 4), "native_aspect_w_h": round(nw / nh, 4),
    "aspect_error_pct": round(100 * ((rw / rh) / (nw / nh) - 1), 2),
    "moved_px": {"left": L - 1 - a.inset - x, "top": T - 1 - a.inset - y, "right": R + a.inset - (x + w), "bottom": B + a.inset - (y + h)},
    "edge_strength_vs_median": {k: round(s / max(m, 1e-3), 1) for k, s, m in (("left", sl, ml), ("right", sr, mr), ("top", st, mt), ("bottom", sb, mb))},
}))
