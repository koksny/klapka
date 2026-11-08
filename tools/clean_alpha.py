"""Turn a raw CGI cutout (RGBA) into a clean master body PNG at the archive's physical scale.

- alpha noise < 8 -> 0, one body (largest component), holes filled, interior forced opaque
  (the AA rim the model drew is kept in a thin band at the outline)
- edge colours decontaminated (rim RGB taken from the nearest opaque pixel: no halo from the old background)
- RGB under alpha 0 set to 0 (deterministic files)
- optional deskew from the measured side-edge angle
- trimmed, scaled so the body height = height_mm * px_per_mm, padded by 1 mm of transparency
- prints a report: alpha stats, aspect vs spec, edge tilt, left/right symmetry

python -I tools/clean_alpha.py RAW.png OUT.png --height-mm 99 --width-mm 46 [--px-per-mm 12] [--deskew]
"""
import argparse, json
import numpy as np
import cv2
from PIL import Image
from scipy import ndimage as ndi

ap = argparse.ArgumentParser()
ap.add_argument("raw"); ap.add_argument("out")
ap.add_argument("--height-mm", type=float, required=True)
ap.add_argument("--width-mm", type=float, required=True)
ap.add_argument("--px-per-mm", type=float, default=12.0)
ap.add_argument("--rim", type=int, default=2, help="px band at the outline where model alpha is kept")
ap.add_argument("--deskew", action="store_true")
a = ap.parse_args()

src = Image.open(a.raw)
rep = {"raw": a.raw, "raw_mode": src.mode}
im = np.asarray(src.convert("RGBA")).astype(np.float32)
A = im[..., 3].copy()
rep["raw_alpha_min"] = int(A.min()); rep["raw_alpha_partial_frac"] = round(float(((A > 0) & (A < 255)).mean()), 4)
if A.min() >= 255:
    raise SystemExit(json.dumps({**rep, "error": "no transparency in raw output"}))


def edge_tilt(mask):
    rows = np.where(mask.any(1))[0]
    r0, r1 = rows.min(), rows.max(); span = r1 - r0
    ys = np.arange(int(r0 + 0.2 * span), int(r0 + 0.8 * span))
    L = np.array([np.argmax(mask[y]) for y in ys]); R = np.array([mask.shape[1] - 1 - np.argmax(mask[y][::-1]) for y in ys])
    kl, bl = np.polyfit(ys, L, 1); kr, br = np.polyfit(ys, R, 1)
    return (float(np.degrees(np.arctan(kl))), float(np.degrees(np.arctan(kr))),
            float((L - (kl * ys + bl)).std()), float((R - (kr * ys + br)).std()))


A[A < 8] = 0
lab, n = ndi.label(A >= 128)
sizes = ndi.sum(np.ones_like(lab), lab, range(1, n + 1))
body = ndi.binary_fill_holes(lab == int(np.argmax(sizes)) + 1)
rep["components_ge128"] = int(n)
A[~ndi.binary_dilation(body, iterations=a.rim + 1)] = 0              # stray islands / far haze
# pixels the model left (semi-)transparent inside the body carry the matte colour under them
# (often magenta/purple): give them the colour of the nearest truly opaque pixel before they go solid
was_opaque = A >= 250
_, (jy, jx) = ndi.distance_transform_edt(~was_opaque, return_indices=True)
fill = ndi.binary_erosion(body, iterations=a.rim) & ~was_opaque
im[..., :3][fill] = im[..., :3][jy[fill], jx[fill]]
rep["interior_refilled_px"] = int(fill.sum())
A[ndi.binary_erosion(body, iterations=a.rim)] = 255                   # solid interior

if a.deskew:
    tl, tr, _, _ = edge_tilt(A >= 128)
    ang = (tl + tr) / 2
    rep["deskew_deg"] = round(ang, 3)
    if abs(ang) > 0.05:
        h, w = A.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), -ang, 1.0)
        pm = im[..., :3] * (A[..., None] / 255.0)
        pm = cv2.warpAffine(pm, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=0)
        A = np.clip(cv2.warpAffine(A, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=0), 0, 255)
        im = np.dstack([np.where(A[..., None] > 0, pm / np.maximum(A[..., None], 1e-3) * 255.0, 0), A])
        A[A < 8] = 0

# decontaminate rim colours: take RGB from the nearest fully opaque pixel
opaque = A >= 250
_, (iy, ix) = ndi.distance_transform_edt(~opaque, return_indices=True)
rgb = im[..., :3]
rim = (A > 0) & ~opaque
rgb[rim] = rgb[iy[rim], ix[rim]]
rgb[A == 0] = 0

# trim, scale to physical size, pad 1 mm
ys, xs = np.where(A > 0)
y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
rgb, A = rgb[y0:y1, x0:x1], A[y0:y1, x0:x1]
bh, bw = A.shape
rep["body_px_raw"] = [int(bw), int(bh)]
rep["aspect_w_h"] = round(bw / bh, 4); rep["spec_aspect_w_h"] = round(a.width_mm / a.height_mm, 4)
tl, tr, jl, jr = edge_tilt(A >= 128)
rep["side_tilt_deg"] = [round(tl, 3), round(tr, 3)]; rep["side_jitter_px"] = [round(jl, 2), round(jr, 2)]
s = a.height_mm * a.px_per_mm / bh
nw, nh = int(round(bw * s)), int(round(a.height_mm * a.px_per_mm))
pm = rgb * (A[..., None] / 255.0)
interp = cv2.INTER_LANCZOS4 if s > 1 else cv2.INTER_AREA
pm = cv2.resize(pm, (nw, nh), interpolation=interp)
A2 = np.clip(cv2.resize(A, (nw, nh), interpolation=interp), 0, 255)
A2[A2 < 4] = 0
rgb2 = np.where(A2[..., None] > 0, np.clip(pm / np.maximum(A2[..., None], 1e-3) * 255.0, 0, 255), 0)
pad = int(round(a.px_per_mm))
out = np.zeros((nh + 2 * pad, nw + 2 * pad, 4), np.uint8)
out[pad:pad + nh, pad:pad + nw, :3] = np.round(rgb2).astype(np.uint8)
out[pad:pad + nh, pad:pad + nw, 3] = np.round(A2).astype(np.uint8)
Image.fromarray(out, "RGBA").save(a.out)

m = out[..., 3] >= 128
cols = np.where(m.any(0))[0]; cx = (cols.min() + cols.max()) / 2
mir = m[:, ::-1]; shift = int(round(2 * cx - (m.shape[1] - 1)))
mir = np.roll(mir, shift, axis=1)
rep["lr_symmetry_iou"] = round(float((m & mir).sum() / (m | mir).sum()), 4)
rep["out"] = a.out; rep["out_size"] = [out.shape[1], out.shape[0]]
rep["scale"] = round(s, 4); rep["px_per_mm"] = a.px_per_mm
rep["alpha_partial_px"] = int(((out[..., 3] > 0) & (out[..., 3] < 255)).sum())
print(json.dumps(rep))
