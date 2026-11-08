"""Header animation: six phones side by side, each screen showing one letter of K L A P K A on a lit
LCD strip that stays put. Every second the phones slide one place to the left (eased, 0.4 s); the strip
shows only through the screen holes, so each letter is seen through every phone's cut-out screen in turn. Loops seamlessly after one
pass through the phones. Animated PNG (full alpha, looks right on light and dark pages).

python tools/make_header.py OUT.png PHONE_DIR [PHONE_DIR ...] [--style green|blue|amber] [--px-per-mm 3]
"""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

GLYPHS = {
    "K": ["X...X", "X..X.", "X.X..", "XX...", "X.X..", "X..X.", "X...X"],
    "L": ["X....", "X....", "X....", "X....", "X....", "X....", "XXXXX"],
    "A": [".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"],
    "P": ["XXXX.", "X...X", "X...X", "XXXX.", "X....", "X....", "X...."],
}
STYLES = {  # LCD background top, bottom, lit pixel, unlit pixel ghost
    "green": ((176, 196, 120), (140, 165, 92), (28, 40, 22), (0, 0, 0, 22)),
    "blue": ((150, 205, 255), (82, 150, 235), (10, 28, 70), (0, 0, 40, 24)),
    "amber": ((255, 196, 96), (230, 150, 50), (60, 30, 6), (40, 20, 0, 26)),
}

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("phones", nargs="+")
ap.add_argument("--style", default="amber", choices=STYLES)
ap.add_argument("--px-per-mm", type=float, default=2.5)
ap.add_argument("--word", default="KLAPKA")
ap.add_argument("--ms", type=int, default=1000, help="one step (hold + slide)")
ap.add_argument("--slide-ms", type=int, default=400)
ap.add_argument("--fps", type=int, default=15)
a = ap.parse_args()
S = a.px_per_mm / 12.0                  # skin.png is 12 px/mm
top_c, bot_c, lit_c, ghost_c = STYLES[a.style]

phones = []
for p in a.phones:
    d = Path(p); P = json.load(open(d / "phone.json", encoding="utf-8"))
    im = Image.open(d / "skin.png").convert("RGBA"); im = im.resize((round(im.width * S), round(im.height * S)), Image.LANCZOS)
    x, y, w, h = [v * S for v in P["screen"]["skin_px"]]
    phones.append({"im": im, "hole": (x, y, w, h), "cx": x + w / 2, "cy": y + h / 2})
if len(phones) < len(a.word):   # repeat the line-up so there is always a phone per letter
    phones = (phones * ((len(a.word) // len(phones)) + 1))
n, slots = len(phones), len(a.word)

slot_w = max(p["im"].width for p in phones) + round(7 * a.px_per_mm)
up = max(p["cy"] for p in phones); down = max(p["im"].height - p["cy"] for p in phones)
margin = round(2 * a.px_per_mm)
W, H = slots * slot_w + 2 * margin, round(up + down) + 2 * margin
Yc = margin + up

# one pixel-font letter size that fits the smallest screen
min_w = min(p["hole"][2] for p in phones); min_h = min(p["hole"][3] for p in phones)
dot = int(min(0.62 * min_h / 7, 0.75 * min_w / 5))
gap = max(1, dot // 6)


def lcd(w, h):
    """lit LCD panel with a vertical gradient."""
    t = np.linspace(0, 1, h)[:, None, None]
    g = (np.array(top_c) * (1 - t) + np.array(bot_c) * t) * np.ones((1, w, 1))
    return Image.fromarray(np.dstack([g, np.full((h, w), 255)]).astype(np.uint8), "RGBA")


def letter(ch):
    rows = GLYPHS[ch]; L = Image.new("RGBA", (5 * dot, 7 * dot), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            box = [c * dot, r * dot, (c + 1) * dot - gap - 1, (r + 1) * dot - gap - 1]
            d.rectangle(box, fill=(*lit_c, 255) if v == "X" else ghost_c)
    return L


letters = [letter(ch) for ch in a.word]

# the backdrop: one lit LCD strip across the whole width with the letters at the slot centres. It stays
# put; the phones slide over it and it shows only through their screen holes.
y_top = min(Yc - p["cy"] + p["hole"][1] for p in phones) - 3
y_bot = max(Yc - p["cy"] + p["hole"][1] + p["hole"][3] for p in phones) + 3
backdrop = Image.new("RGBA", (W, H), (0, 0, 0, 0))
backdrop.alpha_composite(lcd(W, round(y_bot - y_top)), (0, round(y_top)))
for i, L in enumerate(letters):
    sx = margin + i * slot_w + slot_w / 2
    backdrop.alpha_composite(L, (round(sx - L.width / 2), round(Yc - L.height / 2)))

# soft fade at both ends, inside the margin and half a gap, so phones leave and enter smoothly
fade = np.ones(W, np.float32); fw = margin + (slot_w - max(p["im"].width for p in phones)) // 2
fade[:fw] = np.linspace(0, 1, fw); fade[W - fw:] = np.linspace(1, 0, fw)


def ease(u):  # ease-in-out cubic
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def frame(step, u):
    """phones of `step` shifted left by u (0..1) of a slot."""
    F = Image.new("RGBA", (W, H), (0, 0, 0, 0)); mask = Image.new("L", (W, H), 0); md = ImageDraw.Draw(mask)
    placed = []
    for i in range(slots + 1):
        p = phones[(step + i) % n]; sx = margin + (i - u) * slot_w + slot_w / 2
        ox, oy = round(sx - p["cx"]), round(Yc - p["cy"]); x, y, w, h = p["hole"]
        md.rectangle([ox + x - 1, oy + y - 1, ox + x + w, oy + y + h], fill=255)
        placed.append((p, ox, oy))
    shown = backdrop.copy(); shown.putalpha(Image.fromarray((np.asarray(backdrop)[..., 3] * (np.asarray(mask) / 255.0)).astype(np.uint8)))
    F.alpha_composite(shown)
    for p, ox, oy in placed:
        F.alpha_composite(p["im"], (ox, oy))
    A = np.asarray(F).copy(); A[..., 3] = (A[..., 3] * fade[None, :]).astype(np.uint8)
    return Image.fromarray(A, "RGBA")


frames, durations = [], []
k = max(2, round(a.slide_ms / 1000 * a.fps))
for step in range(n):
    frames.append(frame(step, 0.0)); durations.append(a.ms - a.slide_ms)
    for j in range(1, k):
        frames.append(frame(step, ease(j / k))); durations.append(round(a.slide_ms / k))
# one shared 256-colour palette with alpha for all frames (APNG frames share PLTE/tRNS): ~5x smaller
strip = Image.new("RGBA", (W, H * len(frames)))
for i, fr in enumerate(frames): strip.paste(fr, (0, i * H))
q = strip.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
frames = [q.crop((0, i * H, W, (i + 1) * H)) for i in range(len(frames))]
frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=0, blend=0, optimize=True)
print(json.dumps({"out": a.out, "size": [W, H], "frames": len(frames), "dot": dot, "bytes": Path(a.out).stat().st_size}))
