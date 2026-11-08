"""Undo perspective: warp the phone's front face, given its four corners in the photo, onto an upright
rectangle with the phone's real aspect (width_mm : height_mm). Corners are the front face's virtual sharp
corners in phone terms (TL TR BR BL = top-left, top-right, bottom-right, bottom-left as the phone stands),
marked by a vision model or a person. The output is padded and sized for the CGI edit.

python -I tools/rectify.py PHOTO OUT.png --corners "x,y x,y x,y x,y" --mm 46x99 [--coord-scale 1.0]
       [--size 704x1408] [--fill 0.88]
"""
import argparse, json
import numpy as np
import cv2
from PIL import Image, ImageOps

ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("out")
ap.add_argument("--corners", required=True)
ap.add_argument("--coord-scale", type=float, default=1.0, help="corners were marked on a copy scaled by this factor")
ap.add_argument("--mm", required=True)
ap.add_argument("--size", default="704x1408")
ap.add_argument("--fill", type=float, default=0.88, help="phone height as a fraction of the canvas height")
ap.add_argument("--bg", default="255,255,255")
a = ap.parse_args()

im = np.asarray(ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB"))
src = np.array([[float(v) for v in p.split(",")] for p in a.corners.split()], np.float32) / a.coord_scale
wmm, hmm = map(float, a.mm.lower().split("x"))
TW, TH = map(int, a.size.lower().split("x"))
ph = a.fill * TH; pw = ph * wmm / hmm
if pw > a.fill * TW:
    pw = a.fill * TW; ph = pw * hmm / wmm
x0, y0 = (TW - pw) / 2, (TH - ph) / 2
dst = np.array([[x0, y0], [x0 + pw, y0], [x0 + pw, y0 + ph], [x0, y0 + ph]], np.float32)
M = cv2.getPerspectiveTransform(src, dst)
bg = tuple(int(v) for v in a.bg.split(","))
out = cv2.warpPerspective(im, M, (TW, TH), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=bg)
Image.fromarray(out).save(a.out)
# how much the far end was magnified (resolution the warp had to invent)
sides = [float(np.linalg.norm(src[i] - src[(i + 1) % 4])) for i in range(4)]
pw, ph = float(pw), float(ph)
print(json.dumps({"out": a.out, "src_corners": src.round(1).tolist(), "src_side_px_T_R_B_L": [round(s, 1) for s in sides],
                  "dst_face_px": [round(pw, 1), round(ph, 1)],
                  "magnification_top_bottom_left_right": [round(pw / sides[0], 2), round(pw / sides[2], 2),
                                                          round(ph / sides[3], 2), round(ph / sides[1], 2)]}))
