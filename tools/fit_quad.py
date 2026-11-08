"""Find the phone's four corners automatically from a cutout's alpha: fit a straight line to the middle
part of each side of the silhouette and intersect them. Prints corners as "x,y x,y x,y x,y" (TL TR BR BL)
for rectify.py. Meant for roughly frontal photos (mild tilt / keystone), not for steep angles.

python -I tools/fit_quad.py CUTOUT.png
"""
import sys, json
import numpy as np
from PIL import Image

A = np.asarray(Image.open(sys.argv[1]).convert("RGBA"))[..., 3] >= 128
rows = np.where(A.any(1))[0]; cols = np.where(A.any(0))[0]
r0, r1, c0, c1 = rows.min(), rows.max(), cols.min(), cols.max()


def fit(points):  # least squares x = k*y + b  (or y = k*x + b)
    p = np.array(points, float); k, b = np.polyfit(p[:, 0], p[:, 1], 1); return k, b


ys = np.arange(int(r0 + 0.2 * (r1 - r0)), int(r0 + 0.8 * (r1 - r0)))
L = fit([(y, np.argmax(A[y])) for y in ys])                              # x = kL*y + bL
R = fit([(y, A.shape[1] - 1 - np.argmax(A[y][::-1])) for y in ys])
xs = np.arange(int(c0 + 0.3 * (c1 - c0)), int(c0 + 0.7 * (c1 - c0)))
T = fit([(x, np.argmax(A[:, x])) for x in xs])                           # y = kT*x + bT
B = fit([(x, A.shape[0] - 1 - np.argmax(A[:, x][::-1])) for x in xs])


def cross(v, h):  # vertical x = kv*y + bv, horizontal y = kh*x + bh
    kv, bv = v; kh, bh = h
    y = (kh * bv + bh) / (1 - kh * kv); return kv * y + bv, y


corners = [cross(L, T), cross(R, T), cross(R, B), cross(L, B)]
print(" ".join(f"{x:.1f},{y:.1f}" for x, y in corners))
print(json.dumps({"tilt_deg": {"left": round(float(np.degrees(np.arctan(L[0]))), 3), "right": round(float(np.degrees(np.arctan(R[0]))), 3),
                               "top": round(float(np.degrees(np.arctan(T[0]))), 3), "bottom": round(float(np.degrees(np.arctan(B[0]))), 3)}}),
      file=sys.stderr)
