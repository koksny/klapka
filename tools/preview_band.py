"""Preview a skin on a Mi Band 7/8/9 screen (192x490, AMOLED black): the clock is drawn into the
screen hole first, the skin goes on top. Saves the native-size PNG and a 2x nearest-neighbour copy.

python -I tools/preview_band.py SKIN.png --screen x,y,w,h --out OUT.png [--size 192x490] [--margin 4]
"""
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("skin"); ap.add_argument("--screen", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--size", default="192x490"); ap.add_argument("--margin", type=int, default=4)
ap.add_argument("--time", default="12:34"); ap.add_argument("--date", default="Pn 08.11")
a = ap.parse_args()
TW, TH = map(int, a.size.split("x"))
skin = Image.open(a.skin).convert("RGBA")
sx, sy, sw, sh = map(int, a.screen.split(","))
s = min((TW - 2 * a.margin) / skin.width, (TH - 2 * a.margin) / skin.height)
pw, ph = round(skin.width * s), round(skin.height * s)
ox, oy = (TW - pw) // 2, (TH - ph) // 2
# screen rect on the band, snapped to whole pixels
L, T = ox + round(sx * s), oy + round(sy * s); R, B = ox + round((sx + sw) * s), oy + round((sy + sh) * s)

band = Image.new("RGBA", (TW, TH), (0, 0, 0, 255))
d = ImageDraw.Draw(band)
d.rectangle([L, T, R - 1, B - 1], fill=(28, 44, 70, 255))
def font(px):
    for f in ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        try: return ImageFont.truetype(f, px)
        except OSError: pass
    return ImageFont.load_default()
fw = R - L
d.text(((L + R) / 2, T + (B - T) * 0.42), a.time, font=font(int(fw * 0.30)), fill=(240, 240, 240, 255), anchor="mm")
d.text(((L + R) / 2, T + (B - T) * 0.66), a.date, font=font(int(fw * 0.12)), fill=(170, 200, 240, 255), anchor="mm")
small = skin.resize((pw, ph), Image.LANCZOS)
band.alpha_composite(small, (ox, oy))
band.convert("RGB").save(a.out)
band.convert("RGB").resize((TW * 2, TH * 2), Image.NEAREST).save(a.out.rsplit(".", 1)[0] + "_2x.png")
print({"out": a.out, "phone_px": [pw, ph], "screen_on_band": [L, T, R - L, B - T]})
