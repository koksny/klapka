"""Draw a phone's layout template (first CGI image) from phone.json: body outline at the real size,
screen at its exact native aspect, keypad block. Same style as Koks's hand-made template: white
background, grey body (127), black screen (0), light grey keypad (195), black outlines.
The canvas is the CGI size; the phone is drawn at px_per_mm (default 12, the master scale), centred.

python -I tools/make_template.py phones/k800i/phone.json OUT.png [--size 704x1408] [--px-per-mm 12]
Prints the template geometry in px (body, screen, keypad) for checking the render against it.
"""
import argparse, json
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("phone"); ap.add_argument("out")
ap.add_argument("--size", default="704x1408")
ap.add_argument("--px-per-mm", type=float, default=12.0)
ap.add_argument("--outline-mm", type=float, default=0.4)
ap.add_argument("--labels", action="store_true", help="draw the key labels and printed texts from phone.json")
a = ap.parse_args()
P = json.load(open(a.phone, encoding="utf-8"))
TW, TH = map(int, a.size.split("x")); s = a.px_per_mm
bw, bh = P["size_mm"]["width"] * s, P["size_mm"]["height"] * s
assert bw <= TW and bh <= TH, "phone does not fit the canvas at this scale"
ox, oy = round((TW - bw) / 2), round((TH - bh) / 2)
ol = max(2, round(a.outline_mm * s))
img = Image.new("RGB", (TW, TH), (255, 255, 255)); d = ImageDraw.Draw(img)


def rect(r):  # mm dict -> px box (integer edges)
    return [ox + round(r["x"] * s), oy + round(r["y"] * s), ox + round((r["x"] + r["w"]) * s) - 1, oy + round((r["y"] + r["h"]) * s) - 1]


body = [ox, oy, ox + round(bw) - 1, oy + round(bh) - 1]
d.rounded_rectangle(body, radius=round(P.get("corner_radius_mm", 0) * s), fill=(127, 127, 127), outline=(0, 0, 0), width=ol)
L = P["layout_mm"]
for seam in L.get("seams", []):  # slider / flip: where the two parts meet
    y = oy + round(seam["y"] * s)
    d.line([(ox, y), (ox + round(bw) - 1, y)], fill=(0, 0, 0), width=ol)
if "keypad" in L:
    d.rectangle(rect(L["keypad"]), fill=(195, 195, 195), outline=(0, 0, 0), width=ol)
scr = rect(L["screen"])
# keep the exact native aspect in whole pixels: width from the data, height from the aspect, centred on the data
nw0, nh0 = P["display"]["native_px"]; sw0 = scr[2] - scr[0] + 1; sh0 = round(sw0 * nh0 / nw0)
cy0 = (scr[1] + scr[3] + 1) / 2; scr = [scr[0], round(cy0 - sh0 / 2), scr[2], round(cy0 - sh0 / 2) + sh0 - 1]
d.rectangle(scr, fill=(0, 0, 0))

if a.labels:
    from PIL import ImageFont
    FONT = "C:/Windows/Fonts/bahnschrift.ttf"
    def font(px): return ImageFont.truetype(FONT, max(8, round(px)))
    # keypad: one key per label, digit large, letters small to its right, dark on light grey
    if "keys" in P and "keypad" in L:
        k = L["keypad"]; rows = P["keys"]; nr, nc = len(rows), max(len(r) for r in rows)
        gap = 0.5 * s
        kw, kh = (k["w"] * s - gap * (nc + 1)) / nc, (k["h"] * s - gap * (nr + 1)) / nr
        kx0, ky0 = ox + k["x"] * s, oy + k["y"] * s
        for ri, row in enumerate(rows):
            for ci, label in enumerate(row):
                x0 = kx0 + gap + ci * (kw + gap); y0 = ky0 + gap + ri * (kh + gap)
                d.rounded_rectangle([x0, y0, x0 + kw, y0 + kh], radius=round(0.6 * s), fill=(225, 225, 225), outline=(60, 60, 60), width=max(1, ol // 2))
                digit, _, letters = label.partition(" ")
                fd, fl = font(kh * 0.62), font(kh * 0.36)
                cy = y0 + kh / 2
                wd = d.textlength(digit, font=fd); wl = d.textlength(letters, font=fl) if letters else 0
                gapx = kh * 0.12 if letters else 0
                tx = x0 + (kw - (wd + gapx + wl)) / 2
                d.text((tx, cy), digit, font=fd, fill=(0, 0, 0), anchor="lm")
                if letters:
                    d.text((tx + wd + gapx, cy), letters, font=fl, fill=(0, 0, 0), anchor="lm")
    # printed texts (logo, sub-brand) at their measured centre lines
    for t in P.get("text_layout_mm", []):
        d.text((ox + bw / 2, oy + t["cy"] * s), t["text"], font=font(t["h"] * s * 1.35), fill=(235, 235, 235), anchor="mm")

img.save(a.out)
nw, nh = P["display"]["native_px"]
sw, sh = scr[2] - scr[0] + 1, scr[3] - scr[1] + 1
print(json.dumps({"out": a.out, "size": [TW, TH], "px_per_mm": s, "body_px": body, "screen_px": scr,
                  "screen_aspect": round(sw / sh, 4), "native_aspect": round(nw / nh, 4),
                  "keypad_px": rect(L["keypad"]) if "keypad" in L else None}))
