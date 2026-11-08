"""Contact sheet: python -I tools/contact_sheet.py OUT.png H img1 img2 ...  (EXIF-transposed, labeled)"""
import sys
from PIL import Image, ImageOps, ImageDraw
out, H, paths = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
tiles = []
for p in paths:
    im = ImageOps.exif_transpose(Image.open(p)).convert("RGBA")
    w0, h0 = im.size
    im = im.resize((max(1, round(w0 * H / h0)), H), Image.LANCZOS)
    bg = Image.new("RGBA", (im.width, H + 22), (255, 0, 255, 255) if "rgba" in sys.argv[0] else (40, 40, 40, 255))
    # checker under transparency
    ck = Image.new("RGBA", im.size, (200, 200, 200, 255)); d = ImageDraw.Draw(ck)
    for y in range(0, im.height, 16):
        for x in range(0, im.width, 16):
            if (x // 16 + y // 16) % 2: d.rectangle([x, y, x + 15, y + 15], fill=(150, 150, 150, 255))
    ck.alpha_composite(im); bg.paste(ck, (0, 22))
    ImageDraw.Draw(bg).text((4, 4), f"{p.split('/')[-1].split(chr(92))[-1]}  {w0}x{h0}", fill=(255, 255, 255, 255))
    tiles.append(bg)
W = sum(t.width for t in tiles) + 8 * (len(tiles) + 1)
sheet = Image.new("RGBA", (W, H + 22 + 16), (20, 20, 20, 255)); x = 8
for t in tiles: sheet.paste(t, (x, 8)); x += t.width + 8
sheet.convert("RGB").save(out); print(out, sheet.size)
