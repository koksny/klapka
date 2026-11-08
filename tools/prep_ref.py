"""Prepare a reference photo for the CGI edit: find the phone, crop with a margin, pad to the
target aspect with the photo's own background colour, resize to the target size, drop EXIF.

python -I tools/prep_ref.py SRC OUT.png --size 640x1280 [--margin 0.06]
"""
import argparse, json
import numpy as np
import cv2
from PIL import Image, ImageOps
from scipy import ndimage as ndi

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--size", default="640x1280")
ap.add_argument("--margin", type=float, default=0.06)
ap.add_argument("--bbox", help="x0,y0,x1,y1 of the phone, skips detection (busy or watermarked backgrounds)")
ap.add_argument("--bg", help="r,g,b padding colour, overrides the border median")
a = ap.parse_args()
TW, TH = map(int, a.size.lower().split("x"))

im = ImageOps.exif_transpose(Image.open(a.src)).convert("RGB")
rgb = np.asarray(im).astype(np.float32)
H, W, _ = rgb.shape

# background model = median colour of a thin border; subject = pixels far from it (Otsu)
b = max(4, min(H, W) // 50)
border = np.concatenate([rgb[:b].reshape(-1, 3), rgb[-b:].reshape(-1, 3),
                         rgb[:, :b].reshape(-1, 3), rgb[:, -b:].reshape(-1, 3)])
bg = np.median(border, axis=0)
if a.bg:
    bg = np.array([float(v) for v in a.bg.split(",")])
if a.bbox:
    x0, y0, x1, y1 = map(int, a.bbox.split(","))
else:
    # subject = GrabCut from a rect inset 1.5% (silver phones on white defeat a plain colour threshold);
    # run on a downscaled copy; the crop margin below covers the few pixels the inset may clip
    k = min(1.0, 800 / max(H, W))
    small = cv2.resize(rgb.astype(np.uint8), (int(W * k), int(H * k)), interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    inset = int(round(0.015 * max(sh, sw)))
    gc = np.zeros((sh, sw), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(small, cv2.COLOR_RGB2BGR), gc, (inset, inset, sw - 2 * inset, sh - 2 * inset),
                bgd, fgd, 6, cv2.GC_INIT_WITH_RECT)
    fg_small = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8) * 255
    fg_small = cv2.morphologyEx(fg_small, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    fg = cv2.resize(fg_small, (W, H), interpolation=cv2.INTER_NEAREST)
    labels, n = ndi.label(fg > 0)
    if n == 0:
        raise SystemExit("no subject found")
    sizes = ndi.sum(np.ones_like(labels), labels, range(1, n + 1))
    mask = ndi.binary_fill_holes(labels == (int(np.argmax(sizes)) + 1))
    ys, xs = np.where(mask)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()

# crop with margin, then pad to the target aspect with the background colour
m = int(round(a.margin * max(x1 - x0, y1 - y0)))
cx0, cy0 = max(0, x0 - m), max(0, y0 - m)
cx1, cy1 = min(W, x1 + m + 1), min(H, y1 + m + 1)
crop = rgb[cy0:cy1, cx0:cx1]
ch, cw, _ = crop.shape
s = min(TW / cw, TH / ch)
nw, nh = int(round(cw * s)), int(round(ch * s))
resized = cv2.resize(crop.astype(np.uint8), (nw, nh), interpolation=cv2.INTER_LANCZOS4 if s > 1 else cv2.INTER_AREA)
canvas = np.empty((TH, TW, 3), np.uint8); canvas[:] = bg.astype(np.uint8)
ox, oy = (TW - nw) // 2, (TH - nh) // 2
canvas[oy:oy + nh, ox:ox + nw] = resized
Image.fromarray(canvas).save(a.out)  # no EXIF carried over

info = {"src": a.src, "src_size": [W, H], "subject_bbox": [int(x0), int(y0), int(x1), int(y1)],
        "subject_aspect_w_h": round((x1 - x0 + 1) / (y1 - y0 + 1), 4), "bg_rgb": bg.round().astype(int).tolist(),
        "scale": round(s, 4), "out": a.out, "out_size": [TW, TH], "placed": [ox, oy, nw, nh]}
print(json.dumps(info))
