"""Screen stage: find the display on BODY.png from an approximate rectangle, cut the hole at the exact
native aspect, and measure where the hole sits.

python tools/mark_screen.py BODY.png --approx x,y,w,h --native 176x220 --fit-native --out-skin SKIN.png
       --out-overlay OVERLAY.png [--snap combo|near|strongest|none] [--search 0.12] [--fill-border]

near (default): each side snaps to the strong edge nearest the guess. combo: for each side, up to 5 candidate edges (local maxima of the edge profile) in a band
around the guess; the four-edge combination wins that is strong, centred on the body's vertical axis
and closest to the native aspect. none: the given rectangle is the display (manual).

Placement checks printed under "checks" (finish turns them into pass/fail):
- centre_x_pct: hole centre vs the body's vertical axis, % of the body width
- margin_diff_mm: the hole must sit centred in the display window: per axis, the difference between
  the distances from the hole edges to the nearest strong edge outside them
- spill: a strong edge parallel to a hole side just inside the hole means the hole runs past the
  display into its frame (ratio of that edge to the frame edge outside; > 0.6 = spill)
"""
import argparse, itertools, json
import numpy as np
import cv2
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("body")
ap.add_argument("--approx", required=True)
ap.add_argument("--native", required=True)
ap.add_argument("--px-per-mm", type=float, default=12.0)
ap.add_argument("--search", type=float, default=0.12, help="search band per side, fraction of the rect size")
ap.add_argument("--inset", type=int, default=0, help="shrink the hole by N px after snapping")
ap.add_argument("--fit-native", action="store_true", help="shrink the hole to the exact native aspect inside the glass")
ap.add_argument("--snap", choices=["combo", "near", "strongest", "none"], default="near")
ap.add_argument("--fill-border", action="store_true", help="paint the display area left around the exact-aspect hole near-black")
ap.add_argument("--out-skin", required=True); ap.add_argument("--out-overlay", required=True)
a = ap.parse_args()

im = np.asarray(Image.open(a.body).convert("RGBA"))
g = cv2.cvtColor(im[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32)
g = cv2.GaussianBlur(g, (0, 0), 1.0)
gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)); gy = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
x, y, w, h = map(int, a.approx.split(","))
nw, nh = map(int, a.native.lower().split("x"))
ppm = a.px_per_mm
alpha = im[..., 3] >= 128
rows = np.where(alpha[y:y + h].any(1))[0] + y
cols = [np.where(alpha[r])[0] for r in rows[::2]]
spans = np.array([(c.min(), c.max()) for c in cols if len(c)], float)
wd = spans[:, 1] - spans[:, 0] + 1; core = spans[np.abs(wd - np.median(wd)) <= 0.01 * np.median(wd)]
core = core if len(core) >= 5 else spans
body_cx = float(np.median((core[:, 0] + core[:, 1]) / 2)); body_w = float(np.median(core[:, 1] - core[:, 0] + 1))


def vprof(xs, ya, yb):
    ya, yb = int(ya + 0.15 * (yb - ya)), int(yb - 0.15 * (yb - ya))
    return np.array([gx[ya:yb, c].mean() if 0 < c < g.shape[1] - 1 else 0.0 for c in xs])


def hprof(ys, xa, xb):
    xa, xb = int(xa + 0.15 * (xb - xa)), int(xb - 0.15 * (xb - xa))
    return np.array([gy[r, xa:xb].mean() if 0 < r < g.shape[0] - 1 else 0.0 for r in ys])


def candidates(pos, prof, k=5):
    """local maxima of the profile at least 30% of its max, strongest first."""
    p = np.convolve(prof, np.ones(3) / 3, mode="same")
    peaks = [i for i in range(1, len(p) - 1) if p[i] >= p[i - 1] and p[i] >= p[i + 1] and p[i] >= 0.3 * p.max()]
    peaks = sorted(peaks, key=lambda i: -p[i])[:k]
    return [(int(pos[i]), float(p[i])) for i in peaks] or [(int(pos[int(np.argmax(p))]), float(p.max()))]


bx, by = max(3, int(a.search * w)), max(3, int(a.search * h))
xsL = np.arange(x - bx, x + bx + 1); xsR = np.arange(x + w - bx, x + w + bx + 1)
ysT = np.arange(y - by, y + by + 1); ysB = np.arange(y + h - by, y + h + by + 1)

if a.snap == "none":
    L, T, R, B = x, y, x + w, y + h
elif a.snap == "combo":
    cL = candidates(xsL, vprof(xsL, y, y + h)); cR = candidates(xsR, vprof(xsR, y, y + h))
    cT = candidates(ysT, hprof(ysT, x, x + w)); cB = candidates(ysB, hprof(ysB, x, x + w))
    smax = max(s for c in (cL, cR, cT, cB) for _, s in c)
    best = None
    for (l, sl), (r, sr), (t, st), (b, sb) in itertools.product(cL, cR, cT, cB):
        if r - l < 0.5 * w or b - t < 0.5 * h: continue
        strength = (sl + sr + st + sb) / (4 * smax)
        centre = abs((l + r) / 2 - body_cx) / body_w
        aspect = abs(np.log(((r - l) / (b - t)) / (nw / nh)))
        size = abs(np.log((r - l) / w)) + abs(np.log((b - t) / h))
        score = strength - 8 * centre - 2.5 * aspect - 0.6 * size
        if best is None or score > best[0]: best = (score, l, r, t, b)
    _, L, R, T, B = best
    L, T = L + 1, T + 1            # the gradient peak sits on the boundary; the hole starts one pixel inside it
else:
    def pick(pos, prof, est, size):
        if a.snap == "strongest": return int(pos[int(np.argmax(prof))])
        wt = np.exp(-((pos - est) / (0.025 * size)) ** 2) * (prof >= 0.35 * prof.max())
        return int(pos[int(np.argmax(prof * wt))])
    L = pick(xsL, vprof(xsL, y, y + h), x, w) + 1; R = pick(xsR, vprof(xsR, y, y + h), x + w, w)
    T = pick(ysT, hprof(ysT, L, R), y, h) + 1; B = pick(ysB, hprof(ysB, L, R), y + h, h)

L, T, R, B = L + a.inset, T + a.inset, R - a.inset, B - a.inset
glass = [int(L), int(T), int(R - L), int(B - T)]
if a.fit_native:
    # largest rectangle with the exact native aspect inside the glass, centred: the leftover glass stays
    # as a thin black border, the bezel is never cut
    gw, gh = R - L, B - T
    if gw / gh > nw / nh: fw, fh = round(gh * nw / nh), gh
    else: fw, fh = gw, round(gw * nh / nw)
    L, T = L + (gw - fw) // 2, T + (gh - fh) // 2
    R, B = L + fw, T + fh
L, T, R, B = int(L), int(T), int(R), int(B); rw, rh = R - L, B - T

# ---- placement checks, measured on the uncut body
reach = int(4 * ppm); inner = int(3 * ppm)


def side(dirn):
    """distance from the hole edge to the strongest edge outside it (within 4 mm), and the strongest
    parallel edge just inside the hole (0.4-3 mm) relative to it."""
    if dirn in ("left", "right"):
        sgn = -1 if dirn == "left" else 1; e = L if dirn == "left" else R - 1
        out = [e + sgn * d for d in range(1, reach)]; ins = [e - sgn * d for d in range(int(0.4 * ppm), inner)]
        po, pi = vprof(out, T, B), vprof(ins, T, B)
    else:
        sgn = -1 if dirn == "top" else 1; e = T if dirn == "top" else B - 1
        out = [e + sgn * d for d in range(1, reach)]; ins = [e - sgn * d for d in range(int(0.4 * ppm), inner)]
        po, pi = hprof(out, L, R), hprof(ins, L, R)
    k = int(np.argmax(po)); return (k + 1) / ppm, float(pi.max() / max(po.max(), 1e-3))


m = {s: side(s) for s in ("left", "right", "top", "bottom")}
checks = {"centre_x_pct": round(100 * abs((L + R) / 2 - body_cx) / body_w, 2),
          "margin_diff_mm": round(max(abs(m["left"][0] - m["right"][0]), abs(m["top"][0] - m["bottom"][0])), 2),
          "margins_mm": {s: round(v[0], 2) for s, v in m.items()},
          "spill": round(max(v[1] for v in m.values()), 2), "spill_by_side": {s: round(v[1], 2) for s, v in m.items()}}

skin = im.copy()
if a.fill_border:   # what is left of the rendered display around the exact hole becomes the LCD's black border
    gl, gt, gw_, gh_ = glass; skin[gt:gt + gh_, gl:gl + gw_, :3] = (14, 14, 16)
skin[T:B, L:R, 3] = 0; skin[T:B, L:R, :3] = 0
Image.fromarray(skin, "RGBA").save(a.out_skin)
ov = Image.fromarray(im, "RGBA").convert("RGB"); d = ImageDraw.Draw(ov)
d.rectangle([x, y, x + w - 1, y + h - 1], outline=(255, 200, 0))      # the guess
d.rectangle(glass[:2] + [glass[0] + glass[2] - 1, glass[1] + glass[3] - 1], outline=(0, 200, 255))   # display found
d.rectangle([L, T, R - 1, B - 1], outline=(255, 0, 255))              # hole
d.line([(body_cx, T - 20), (body_cx, B + 20)], fill=(0, 255, 0))      # body axis
ov.save(a.out_overlay)

print(json.dumps({
    "approx": [x, y, w, h], "glass_px": glass, "screen_px": [L, T, rw, rh],
    "screen_mm": [round(L / ppm, 2), round(T / ppm, 2), round(rw / ppm, 2), round(rh / ppm, 2)],
    "aspect_w_h": round(rw / rh, 4), "native_aspect_w_h": round(nw / nh, 4),
    "aspect_error_pct": round(100 * ((rw / rh) / (nw / nh) - 1), 2), "snap": a.snap, "checks": checks}))
