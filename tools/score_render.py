"""Rank pass-1 renders (white background) against their template, to pick the seed that kept the real
proportions. Scale does not matter (the master is rescaled to millimetres later), so everything is
compared relative to the phone's own bounding box:

- body aspect error against the template (the acceptance limit is 3%)
- the screen: the template's screen, placed relative to the render's body box, is snapped to the
  strongest nearby edges; its IoU with the template screen in body-relative coordinates
- the background must be white (a coloured background breaks the cutout)
- symmetry: the screen centre must sit where the template puts it (within 1% of the body width), and a
  mirror test of the body's edges (left against right) catches renders turned in 3D, where one side
  panel shows and the other does not

Order: renders that pass (white background, aspect within 3%, screen centred within 1%) first, best
screen match and mirror symmetry first; then the rest. python tools/score_render.py TEMPLATE.json RENDER.png [RENDER.png ...]
"""
import sys, json
import numpy as np
import cv2
from PIL import Image

MAX_ASPECT_ERR = 3.0  # % (Koks, 2026-11-08)
MAX_CENTRE_ERR = 1.0  # % of the body width
T = json.load(open(sys.argv[1], encoding="utf-8"))
# a template with parts (antenna, flap) prints the silhouette as body_px and the body alone as body_rect_px;
# the render's body_box() finds the body, so relative positions must use the body rectangle
tb, ts = T.get("body_rect_px") or T["body_px"], T["screen_px"]   # [x0, y0, x1, y1] inclusive
t_aspect = (tb[2] - tb[0] + 1) / (tb[3] - tb[1] + 1)


def rel(r, b):
    w, h = b[2] - b[0] + 1, b[3] - b[1] + 1
    return [(r[0] - b[0]) / w, (r[1] - b[1]) / h, (r[2] - b[0] + 1) / w, (r[3] - b[1] + 1) / h]


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy; return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def body_box(rgb):
    nonwhite = (rgb.min(-1) < 225) | ((rgb.max(-1) - rgb.min(-1)) > 25)
    rows = np.where(nonwhite.sum(1) > 0.25 * nonwhite.sum(1).max())[0]
    mid = (rows.min() + rows.max()) // 2; band = nonwhite[mid - 150: mid + 150]
    cols = np.where(band.mean(0) > 0.5)[0]
    return [int(cols.min()), int(rows.min()), int(cols.max()), int(rows.max())]


def background_white(rgb):
    e = np.concatenate([rgb[:8].reshape(-1, 3), rgb[-8:].reshape(-1, 3), rgb[:, :8].reshape(-1, 3), rgb[:, -8:].reshape(-1, 3)])
    return bool(e.mean() > 215 and (e.max(1) - e.min(1)).mean() < 20)


def snap_screen(rgb, approx, frac=0.08):
    g = cv2.GaussianBlur(cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), 1.0)
    gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)); gy = np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
    x0, y0, x1, y1 = [int(round(v)) for v in approx]; w, h = x1 - x0, y1 - y0; bx, by = max(2, int(frac * w)), max(2, int(frac * h))
    def v(xe):
        ys = slice(int(y0 + .15 * h), int(y1 - .15 * h)); xs = np.arange(max(1, xe - bx), min(g.shape[1] - 1, xe + bx + 1))
        return int(xs[np.argmax([gx[ys, c].mean() for c in xs])])
    def hz(ye, L, R):
        xs = slice(int(L + .15 * (R - L)), int(R - .15 * (R - L))); ys = np.arange(max(1, ye - by), min(g.shape[0] - 1, ye + by + 1))
        return int(ys[np.argmax([gy[r, xs].mean() for r in ys])])
    L, R = v(x0), v(x1); return [L, hz(y0, L, R), R, hz(y1, L, R)]


def mirror_corr(rgb, b):
    g = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)[b[1]:b[3] + 1, b[0]:b[2] + 1]
    g = cv2.GaussianBlur(g, (0, 0), 2.0)
    e = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3))
    m = e[:, ::-1]; e, m = e - e.mean(), m - m.mean()
    return float((e * m).sum() / np.sqrt((e * e).sum() * (m * m).sum()))


rows = []
t_rel = rel(ts, tb)
t_centre = ((ts[0] + ts[2]) / 2 - (tb[0] + tb[2]) / 2) / (tb[2] - tb[0] + 1)
for f in sys.argv[2:]:
    rgb = np.asarray(Image.open(f).convert("RGB")).astype(np.float32)
    b = body_box(rgb); bw, bh = b[2] - b[0] + 1, b[3] - b[1] + 1
    approx = [b[0] + t_rel[0] * bw, b[1] + t_rel[1] * bh, b[0] + t_rel[2] * bw, b[1] + t_rel[3] * bh]
    s = snap_screen(rgb, approx)
    aspect = bw / bh; err = 100 * (aspect / t_aspect - 1)
    si = iou(rel(s, b), t_rel); white = background_white(rgb)
    centre_err = 100 * (((s[0] + s[2]) / 2 - (b[0] + b[2]) / 2) / bw - t_centre)
    mc = mirror_corr(rgb, b)
    ok = white and abs(err) <= MAX_ASPECT_ERR and abs(centre_err) <= MAX_CENTRE_ERR
    rows.append({"render": f, "ok": ok, "background_white": white, "aspect_error_pct": round(err, 2), "screen_rel_iou": round(si, 4),
                 "screen_centre_error_pct": round(centre_err, 2), "mirror": round(mc, 4),
                 "body_aspect": round(aspect, 4), "template_body_aspect": round(t_aspect, 4), "body": b, "screen": s,
                 "score": round(si + 0.5 * mc - 0.05 * abs(err) - 0.1 * abs(centre_err) - (0 if white else 10), 4)})
rows.sort(key=lambda r: (not r["ok"], -r["score"] if r["ok"] else abs(r["aspect_error_pct"]) + (0 if r["background_white"] else 100)))
for r in rows:
    print(json.dumps(r))
