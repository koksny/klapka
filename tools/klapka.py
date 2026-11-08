"""KLAPKA runner: the production standard (docs/PIPELINE.md) as commands. Run from the repo root.

  python tools/klapka.py new      sony-ericsson/k750i --brand "Sony Ericsson" --model K750i
  python tools/klapka.py measure  sony-ericsson/k750i PHOTO [--bbox x0,y0,x1,y1]   # mm grid for step 0
  python tools/klapka.py template sony-ericsson/k750i              # after filling phone.json
  python tools/klapka.py photo    sony-ericsson/k750i PHOTO --source URL --license "CC BY-SA 4.0" [--author NAME]
  python tools/klapka.py pass1    sony-ericsson/k750i [--seeds 1,2,3,4]
  python tools/klapka.py pass2    sony-ericsson/k750i [--seed 1] [--reuse]
  python tools/klapka.py grid     sony-ericsson/k750i              # coordinate grid on work/final.png
  python tools/klapka.py rows     sony-ericsson/k750i              # check the detected key rows first
  python tools/klapka.py textfix  sony-ericsson/k750i --row 3            # one row of keys (preferred)
  python tools/klapka.py textfix  sony-ericsson/k750i --keypad [--box x0,y0,x1,y1]
  python tools/klapka.py textfix  sony-ericsson/k750i --text "Sony Ericsson" --box x0,y0,x1,y1
  python tools/klapka.py restore  sony-ericsson/k750i --rows 1 4    # put correct rows back from p2.png after a keypad redraw
  python tools/klapka.py finish   sony-ericsson/k750i              # master, screen hole, exports, acceptance
  python tools/klapka.py mark     sony-ericsson/k750i --text-ok     # after reading every printed text
  python tools/klapka.py pages                                      # phone pages, catalog, catalog.json
  python tools/klapka.py header                                     # README header from assets/header.json (maintainer)

State lives in phones/<brand>/<model>/: phone.json (data), build.json (provenance, scores,
acceptance), work/ (renders, crops, sheets; not committed). Steps can be re-run; pass1 skips
seeds that already exist.
"""
import argparse, json, math, re, shutil, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
PHONES = ROOT / "phones"
PROMPTS = TOOLS / "prompts.json"
MASTER_PX_PER_MM = 12
MAX_PX = 1_048_576
SCREEN_GLASS = (11, 13, 16)
STANDARD_KEYS = [["1", "2 ABC", "3 DEF"], ["4 GHI", "5 JKL", "6 MNO"], ["7 PQRS", "8 TUV", "9 WXYZ"], ["* a/A", "0 +", "#"]]
THRESHOLDS = {"aspect_error_pct": 3.0, "lean_deg": 0.3, "screen_aspect_error_pct": 0.2}
# measured and recorded, not pass/fail (Koks, 2026-11-08): rounded or tapering sides and one-sided buttons are design
INFO_ONLY = ("taper_deg", "tilt_deg", "jitter_px", "symmetry_iou", "deskew_deg")


# ---------------------------------------------------------------- helpers
def pdir(pid): return PHONES / pid
def wdir(pid): d = pdir(pid) / "work"; d.mkdir(parents=True, exist_ok=True); return d
def load(p, default=None): return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else default
def save(p, obj): Path(p).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
def phone(pid): return load(pdir(pid) / "phone.json")
def build(pid): return load(pdir(pid) / "build.json", {"standard": "v1"})
def save_build(pid, b): save(pdir(pid) / "build.json", b)


def run(script, *args):
    r = subprocess.run([sys.executable, "-I", str(TOOLS / script), *map(str, args)], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{script} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout


def last_json(out):
    for line in reversed(out.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {}


def resolve_screen(P):
    """Screen size from the diagonal at the exact native aspect; x defaults to centred."""
    s = P["layout_mm"]["screen"]; nw, nh = P["display"]["native_px"]; d = P["display"]["diagonal_in"] * 25.4
    if not s.get("w") or not s.get("h"):
        k = d / math.hypot(nw, nh); s["w"], s["h"] = round(nw * k, 2), round(nh * k, 2)
    if s.get("x") is None:
        s["x"] = round((P["size_mm"]["width"] - s["w"]) / 2, 2)
    return P


def canvas_for(w_mm, h_mm):
    a = w_mm / h_mm
    for H in range(2048, 255, -32):
        W = math.ceil(a * 0.92 * H / 0.90 / 32) * 32
        if W * H <= MAX_PX:
            return W, H, round(0.92 * H / h_mm, 3)
    raise SystemExit("no canvas fits")


def alpha_bbox(png):
    A = np.asarray(Image.open(png).convert("RGBA"))[..., 3] >= 128
    ys, xs = np.where(A); return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def font(px):
    for f in ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        try: return ImageFont.truetype(f, int(px))
        except OSError: pass
    return ImageFont.load_default()


def with_glass(skin):
    """skin with a dark glass behind the hole (for thumbnails)."""
    im = Image.open(skin).convert("RGBA"); A = np.asarray(im)[..., 3]
    from scipy import ndimage as ndi
    inside = ndi.binary_fill_holes(A >= 128) & (A < 128)
    g = Image.new("RGBA", im.size, (0, 0, 0, 0)); g.paste(Image.new("RGBA", im.size, (*SCREEN_GLASS, 255)), mask=Image.fromarray((inside * 255).astype(np.uint8)))
    g.alpha_composite(im); return g


# ---------------------------------------------------------------- commands
def cmd_new(a):
    d = pdir(a.id)
    if (d / "phone.json").exists(): raise SystemExit(f"{d}/phone.json exists")
    d.mkdir(parents=True, exist_ok=True)
    save(d / "phone.json", {
        "id": a.id, "brand": a.brand, "model": a.model, "year": None, "form": "candybar", "view": "front",
        "size_mm": {"width": None, "height": None, "depth": None}, "size_note": "",
        "corner_radius_mm": 2.0,
        "display": {"native_px": [None, None], "diagonal_in": None, "type": ""},
        "layout_mm": {"screen": {"x": None, "y": None, "w": None, "h": None, "note": "w/h from the diagonal, x centred unless set; y = top edge, measured"},
                      "keypad": {"x": None, "y": None, "w": None, "h": None}, "seams": []},
        "texts": [a.brand], "keys": STANDARD_KEYS, "key_icons": "", "keypad_labels": "2 ABC, 3 DEF, 4 GHI, 5 JKL, 6 MNO, 7 PQRS, 8 TUV, 9 WXYZ",
        "sources": {"specs": [], "geometry_photo": {"url": "", "license": "", "author": ""}}})
    print(f"created {d / 'phone.json'}: fill it in (docs/PIPELINE.md step 0), then run: template {a.id}")


def body_bbox_grabcut(rgb):
    import cv2
    from scipy import ndimage as ndi
    H, W = rgb.shape[:2]; k = min(1.0, 800 / max(H, W))
    small = cv2.resize(rgb, (int(W * k), int(H * k)), interpolation=cv2.INTER_AREA); sh, sw = small.shape[:2]
    inset = int(round(0.015 * max(sh, sw))); gc = np.zeros((sh, sw), np.uint8)
    cv2.grabCut(cv2.cvtColor(small, cv2.COLOR_RGB2BGR), gc, (inset, inset, sw - 2 * inset, sh - 2 * inset),
                np.zeros((1, 65)), np.zeros((1, 65)), 6, cv2.GC_INIT_WITH_RECT)
    fg = ((gc == 1) | (gc == 3)); lab, n = ndi.label(fg)
    if not n: raise SystemExit("no phone found; give --bbox")
    big = lab == 1 + int(np.argmax(ndi.sum(np.ones_like(lab), lab, range(1, n + 1))))
    ys, xs = np.where(big); return [int(xs.min() / k), int(ys.min() / k), int(xs.max() / k), int(ys.max() / k)]


def cmd_measure(a):
    """Body cut from a frontal photo, stretched to the real size, with a millimetre grid: read the
    screen top edge, keypad block and seams straight off it."""
    P = phone(a.id); wm, hm = P["size_mm"]["width"], P["size_mm"]["height"]
    if not (wm and hm): raise SystemExit("fill size_mm in phone.json first")
    im = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGBA")
    flat = Image.new("RGBA", im.size, (255, 255, 255, 255)); flat.alpha_composite(im); im = flat.convert("RGB"); rgb = np.asarray(im)
    box = [int(v) for v in a.bbox.split(",")] if a.bbox else body_bbox_grabcut(rgb)
    pre = im.copy(); ImageDraw.Draw(pre).rectangle(box, outline=(255, 0, 255), width=max(3, im.width // 300)); pre.thumbnail((1000, 1000))
    pre.save(wdir(a.id) / "measure_bbox.png")
    S = 12; crop = im.crop((box[0], box[1], box[2] + 1, box[3] + 1)).resize((round(wm * S), round(hm * S)), Image.LANCZOS)
    pad = 60; G = Image.new("RGB", (crop.width + pad, crop.height + pad), (20, 20, 20)); G.paste(crop, (pad, pad)); d = ImageDraw.Draw(G)
    for mm in range(0, int(max(wm, hm)) + 1):
        c = (255, 0, 255) if mm % 10 == 0 else ((0, 220, 255) if mm % 5 == 0 else (90, 90, 90))
        if mm <= wm:
            x = pad + mm * S; d.line([(x, pad), (x, G.height)], fill=c, width=1)
            if mm % 5 == 0: d.text((x - 6, 18), str(mm), fill=(255, 255, 0), font=font(16))
        if mm <= hm:
            y = pad + mm * S; d.line([(pad, y), (G.width, y)], fill=c, width=1)
            if mm % 5 == 0: d.text((4, y - 9), str(mm), fill=(255, 255, 0), font=font(16))
    G.save(wdir(a.id) / "measure_grid.png")
    print(f"bbox {box} -> {wdir(a.id) / 'measure_grid.png'} (lines every mm, cyan 5 mm, magenta 10 mm); "
          f"check {wdir(a.id) / 'measure_bbox.png'}; wrong body box? pass --bbox x0,y0,x1,y1")


def cmd_template(a):
    P = resolve_screen(phone(a.id)); save(pdir(a.id) / "phone.json", P)
    W, H, s = (int(a.size.split("x")[0]), int(a.size.split("x")[1]), a.px_per_mm) if a.size else canvas_for(P["size_mm"]["width"], P["size_mm"]["height"])
    out = wdir(a.id) / "template.png"
    T = last_json(run("make_template.py", pdir(a.id) / "phone.json", out, "--size", f"{W}x{H}", "--px-per-mm", s))
    save(wdir(a.id) / "template.json", T)
    b = build(a.id); b["template"] = {"size": [W, H], "px_per_mm": s, "body_px": T["body_px"], "screen_px": T["screen_px"]}; save_build(a.id, b)
    print(json.dumps(T))


def cmd_photo(a):
    im = ImageOps.exif_transpose(Image.open(a.path)).convert("RGBA")
    flat = Image.new("RGBA", im.size, (255, 255, 255, 255)); flat.alpha_composite(im)   # transparent photos -> white
    im = flat.convert("RGB"); im.thumbnail((1024, 1024), Image.LANCZOS)
    im.save(wdir(a.id) / "photo.png")
    b = build(a.id); b["photo"] = {"url": a.source, "license": a.license, "author": a.author or "", "size_used": list(im.size)}; save_build(a.id, b)
    print(f"photo.png {im.size}")


def cmd_pass1(a):
    w = wdir(a.id); seeds = [int(s) for s in a.seeds.split(",")]
    for s in seeds:
        out = w / f"p1_s{s}.png"
        if out.exists(): print(f"seed {s}: exists"); continue
        print(run("cgi_edit.py", "--ref", w / "template.png", "--ref2", w / "photo.png", "--phone", pdir(a.id) / "phone.json",
                  "--prompt-file", PROMPTS, "--prompt-id", "koks_template", "--seed", s, "--out", out).strip())
    lines = run("score_render.py", w / "template.json", *[w / f"p1_s{s}.png" for s in seeds]).strip().splitlines()
    scores = [json.loads(l) for l in lines]
    for sc in scores: sc["seed"] = int(re.search(r"p1_s(\d+)", sc.pop("render")).group(1))
    T = load(w / "template.json"); sheet = []
    for sc in scores:  # overlay sheet for a visual check
        im = Image.open(w / f"p1_s{sc['seed']}.png").convert("RGB"); d = ImageDraw.Draw(im)
        d.rectangle(T["body_px"], outline=(255, 0, 255), width=2); d.rectangle(T["screen_px"], outline=(0, 200, 255), width=2)
        d.text((8, 8), f"seed {sc['seed']}  {'OK' if sc['ok'] else 'no'}  aspect {sc['aspect_error_pct']:+.1f}%  centre {sc['screen_centre_error_pct']:+.1f}%  mirror {sc['mirror']}", fill=(255, 0, 0), font=font(22)); sheet.append(im)
    S = Image.new("RGB", (sum(i.width for i in sheet) + 8 * len(sheet), sheet[0].height), (30, 30, 30)); x = 0
    for i in sheet: S.paste(i, (x, 0)); x += i.width + 8
    S.thumbnail((2400, 1200)); S.save(w / "pass1_sheet.png")
    b = build(a.id); b["pass1"] = {"prompt_id": "koks_template", "scores": scores, "best_seed": scores[0]["seed"]}
    b["model"] = {k: v for k, v in load(w / f"p1_s{scores[0]['seed']}.json").items() if k in ("backend", "preset", "model", "steps", "cfg_scale", "sampler_name")}
    save_build(a.id, b)
    for sc in scores: print(f"seed {sc['seed']}: {'ok ' if sc['ok'] else 'NO '} aspect {sc['aspect_error_pct']:+.2f}%  screen centre {sc['screen_centre_error_pct']:+.2f}%  mirror {sc['mirror']}  screen IoU {sc['screen_rel_iou']}  white bg {sc['background_white']}")
    if not scores[0]["ok"]:
        print("no seed passes (white background, aspect within 3%, screen centred within 1%): run more seeds, e.g. --seeds 5,6,7,8 (then pass all seeds you want ranked)")
    print(f"best: seed {scores[0]['seed']}  -> look at {w / 'pass1_sheet.png'}")


def cmd_pass2(a):
    w = wdir(a.id); b = build(a.id); src = w / f"p1_s{a.from_seed or b['pass1']['best_seed']}.png"
    if a.reuse and (w / "p2.png").exists():
        print("reusing p2.png (text fixes cleared)")
    else:
        print(run("cgi_edit.py", "--ref", src, "--prompt-file", PROMPTS, "--prompt-id", "cutout", "--seed", a.seed, "--out", w / "p2.png").strip())
    shutil.copyfile(w / "p2.png", w / "final.png")
    b["pass2"] = {"from": src.name, "prompt_id": "cutout", "seed": a.seed}; b["text_fixes"] = []
    b.setdefault("pass1", {})["used_seed"] = int(re.search(r"p1_s(\d+)", src.name).group(1)); save_build(a.id, b)
    print(f"final.png = p2.png; read every printed text on it (klapka.py grid {a.id} helps), fix with textfix")


def cmd_grid(a):
    w = wdir(a.id); im = Image.open(w / "final.png").convert("RGBA")
    bg = Image.new("RGBA", im.size, (128, 128, 128, 255)); bg.alpha_composite(im); im = bg.convert("RGB")
    k = 2; im = im.resize((im.width * k, im.height * k), Image.LANCZOS); d = ImageDraw.Draw(im)
    for x in range(0, im.width // k, 20):
        d.line([(x * k, 0), (x * k, im.height)], fill=(255, 0, 255) if x % 100 == 0 else (150, 90, 150), width=1)
        if x % 100 == 0: d.text((x * k + 3, 3), str(x), fill=(255, 255, 0), font=font(18))
    for y in range(0, im.height // k, 20):
        d.line([(0, y * k), (im.width, y * k)], fill=(0, 255, 255) if y % 100 == 0 else (90, 150, 150), width=1)
        if y % 100 == 0: d.text((3, y * k + 3), str(y), fill=(255, 255, 0), font=font(18))
    im.save(w / "final_grid.png"); print(f"{w / 'final_grid.png'} (2x; labels are final.png pixel coordinates)")


def detect_key_rows(png, keypad_px, nrows):
    """Rows of keys found on the render itself: label text gives strong horizontal-gradient energy, the
    gaps between rows little. Picks the run of nrows evenly spaced peaks that best overlaps the
    template keypad. Returns [(y0, y1), ...] top to bottom and the x range."""
    import cv2
    from scipy.signal import find_peaks
    im = Image.open(png).convert("RGBA"); a = np.asarray(im).astype(np.float32)
    rgb = a[..., :3] * (a[..., 3:] / 255.0) + 110 * (1 - a[..., 3:] / 255.0)
    g = cv2.GaussianBlur(cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), 1.0)
    gx = np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3))
    x0, y0, x1, y1 = keypad_px; kh = y1 - y0 + 1; rh = kh / nrows
    ya, yb = max(0, int(y0 - 0.35 * kh)), min(g.shape[0], int(y1 + 0.35 * kh))
    xa, xb = int(x0 + 0.04 * (x1 - x0)), int(x1 - 0.04 * (x1 - x0))
    prof = gx[ya:yb, xa:xb].mean(1)
    k = max(3, int(0.18 * rh)) | 1; prof = np.convolve(prof, np.ones(k) / k, mode="same")
    pk, _ = find_peaks(prof, distance=max(2, int(0.55 * rh)), prominence=0.08 * prof.max())
    pk = list(pk + ya)
    best = None
    for i in range(0, len(pk) - nrows + 1):
        run = np.array(pk[i:i + nrows]); sp = np.diff(run)
        if len(sp) and (sp.min() < 0.6 * rh or sp.max() > 1.6 * rh): continue
        reg = (sp.std() / sp.mean()) if len(sp) > 1 else 0.0
        top, bot = run[0] - sp.mean() / 2, run[-1] + sp.mean() / 2
        ov = max(0, min(bot, y1) - max(top, y0)) / (max(bot, y1) - min(top, y0))
        score = ov - reg
        if best is None or score > best[0]: best = (score, run, sp.mean())
    if best is None: raise SystemExit("could not find the key rows; give --box from the grid")
    _, run, sp = best
    return [(int(round(c - sp / 2)), int(round(c + sp / 2))) for c in run], (x0, x1)


def cmd_rows(a):
    """Draw the detected key rows on work/final.png for a visual check."""
    w = wdir(a.id); P = phone(a.id); T = load(w / "template.json")
    rows, (x0, x1) = detect_key_rows(w / "final.png", T["keypad_px"], len(P["keys"]))
    im = Image.open(w / "final.png").convert("RGBA"); bg = Image.new("RGBA", im.size, (110, 110, 110, 255)); bg.alpha_composite(im)
    d = ImageDraw.Draw(bg)
    for i, (ra, rb) in enumerate(rows, 1):
        d.rectangle([x0 - 4, ra, x1 + 4, rb], outline=(255, 0, 255), width=2); d.text((x1 + 8, (ra + rb) // 2), str(i), fill=(255, 0, 255), font=font(22), anchor="lm")
    m = 40; bg.crop((x0 - m, rows[0][0] - m, x1 + 3 * m, rows[-1][1] + m)).save(w / "rows_check.png")
    print(json.dumps({"rows": rows}), f"-> {w / 'rows_check.png'}")


def cmd_textfix(a):
    w = wdir(a.id); b = build(a.id); n = len(b.get("text_fixes", [])) + 1
    P = phone(a.id); row_text = None
    if a.box: box = a.box
    elif a.row:
        T = load(w / "template.json"); s = b["template"]["px_per_mm"]; m = round(s)
        rows, (x0, x1) = detect_key_rows(w / "final.png", T["keypad_px"], len(P["keys"]))
        ra, rb = rows[a.row - 1]
        box = f"{x0 - m},{ra},{x1 + m},{rb}"
    elif a.keypad:
        T = load(w / "template.json"); s = b["template"]["px_per_mm"]; m = round(2 * s); x0, y0, x1, y1 = T["keypad_px"]
        box = f"{x0 - m},{y0 - m},{x1 + m},{y1 + m}"
    else: raise SystemExit("--box is required for --text")
    if a.row:
        keys = P["keys"][a.row - 1]; row_text = ", ".join(f"'{k}'" for k in keys) + "."
        if P.get("key_icons") and any(k.split()[0] in ("1", "*", "#") for k in keys):
            row_text += " " + P["key_icons"]
    crop = w / f"fix{n}_crop.png"; ed = w / f"fix{n}_ed.png"
    meta = last_json(run("fix_text.py", "crop", "--src", w / "final.png", "--box", box, "--auto-fit", "--width", 1024 if a.keypad and not a.row else 2048, "--out", crop))
    if a.row:
        run("cgi_edit.py", "--ref", crop, "--prompt-file", PROMPTS, "--prompt-id", "fix_key_row", "--text", row_text, "--seed", a.seed, "--out", ed)
    elif a.keypad:
        run("cgi_edit.py", "--ref", crop, "--phone", pdir(a.id) / "phone.json", "--prompt-file", PROMPTS, "--prompt-id", "fix_keypad_tpl", "--seed", a.seed, "--out", ed)
    else:
        run("cgi_edit.py", "--ref", crop, "--prompt-file", PROMPTS, "--prompt-id", "fix_text", "--text", a.text, "--seed", a.seed, "--out", ed)
    before = Image.open(w / "final.png").convert("RGBA")
    run("fix_text.py", "paste", "--src", w / "final.png", "--box-from", crop.with_suffix(".json"), "--edited", ed, "--out", w / "final.png")
    after = Image.open(w / "final.png").convert("RGBA"); bx = meta["box"]
    pair = [i.crop(bx) for i in (before, after)]; z = max(1, round(900 / pair[0].width))
    pair = [p.resize((p.width * z, p.height * z), Image.LANCZOS) for p in pair]
    S = Image.new("RGB", (pair[0].width, pair[0].height * 2 + 8), (0, 0, 0)); S.paste(pair[0], (0, 0)); S.paste(pair[1], (0, pair[0].height + 8))
    S.save(w / f"fix{n}_check.png")
    area, pid_ = (f"key row {a.row}", "fix_key_row") if a.row else (("keypad", "fix_keypad_tpl") if a.keypad else ("text", "fix_text"))
    b.setdefault("text_fixes", []).append({"n": n, "area": area, "text": row_text or a.text, "box": bx, "prompt_id": pid_, "seed": a.seed})
    save_build(a.id, b); print(f"pasted; before/after: {w / f'fix{n}_check.png'}")


def cmd_restore(a):
    """Put rows of keys (or a box) back from the clean cutout (p2.png): for rows a keypad redraw got
    wrong but that were right before. Same render, same pixels; feathered edge, alpha untouched."""
    w = wdir(a.id); P = phone(a.id); T = load(w / "template.json"); b = build(a.id)
    if a.box: boxes = [[int(v) for v in a.box.split(",")]]
    else:
        rows, (x0, x1) = detect_key_rows(w / "p2.png", T["keypad_px"], len(P["keys"])); m = round(b["template"]["px_per_mm"])
        boxes = [[x0 - m, rows[r - 1][0], x1 + m, rows[r - 1][1]] for r in a.rows]
    from PIL import ImageFilter
    src, cur = Image.open(w / "p2.png").convert("RGBA"), Image.open(w / "final.png").convert("RGBA")
    for bx in boxes:
        patch = src.crop(bx); mask = Image.new("L", patch.size, 0); f = a.feather
        mask.paste(255, (f, f, patch.width - f, patch.height - f)); mask = mask.filter(ImageFilter.GaussianBlur(f / 2))
        cur.paste(Image.composite(patch, cur.crop(bx), mask), (bx[0], bx[1]))
    cur.save(w / "final.png")
    b.setdefault("text_fixes", []).append({"n": len(b.get("text_fixes", [])) + 1, "area": "restored from p2", "rows": a.rows, "boxes": boxes})
    save_build(a.id, b); print(json.dumps({"restored": boxes}))


def cmd_finish(a):
    d, w = pdir(a.id), wdir(a.id); P = phone(a.id); b = build(a.id); T = load(w / "template.json")
    wm, hm = P["size_mm"]["width"], P["size_mm"]["height"]
    rep = last_json(run("clean_alpha.py", w / "final.png", d / "body.png", "--height-mm", hm, "--width-mm", wm, "--px-per-mm", MASTER_PX_PER_MM, "--deskew"))
    x0, y0, x1, y1 = alpha_bbox(w / "final.png"); k = hm * MASTER_PX_PER_MM / (y1 - y0 + 1); pad = MASTER_PX_PER_MM
    if not a.screen and b.get("screen_source", {}).get("manual"):   # keep a rectangle given earlier
        a.screen = ",".join(map(str, b["screen_source"]["final_px"]))
    if a.screen:   # the display as seen on work/final.png (x0,y0,x1,y1), e.g. read off final_grid.png
        sx0, sy0, sx1, sy1 = [int(v) for v in a.screen.split(",")]; snap = "none"
    else:          # the template's screen, placed relative to the render's own body box
        bx = T["body_px"]; tw, th = bx[2] - bx[0] + 1, bx[3] - bx[1] + 1; rw, rh = x1 - x0 + 1, y1 - y0 + 1
        sx0, sy0, sx1, sy1 = [x0 + (T["screen_px"][0] - bx[0]) * rw / tw, y0 + (T["screen_px"][1] - bx[1]) * rh / th,
                              x0 + (T["screen_px"][2] - bx[0]) * rw / tw, y0 + (T["screen_px"][3] - bx[1]) * rh / th]
        snap = "near"
    approx = f"{round((sx0 - x0) * k + pad)},{round((sy0 - y0) * k + pad)},{round((sx1 - sx0 + 1) * k)},{round((sy1 - sy0 + 1) * k)}"
    nw, nh = P["display"]["native_px"]
    scr = last_json(run("mark_screen.py", d / "body.png", "--approx", approx, "--native", f"{nw}x{nh}", "--search", 0.06, "--fit-native",
                        "--snap", snap, "--fill-border", "--px-per-mm", MASTER_PX_PER_MM, "--out-skin", d / "skin.png", "--out-overlay", w / "screen_overlay.png"))
    b["screen_source"] = {"final_px": [round(v) for v in (sx0, sy0, sx1, sy1)], "snap": snap, "manual": bool(a.screen)}
    sx, sy, sw, sh = scr["screen_px"]
    # Mi Band 7/8/9 export: 192x490, phone fitted with a 4 px margin, transparent around it and in the hole
    skin = Image.open(d / "skin.png").convert("RGBA"); BW, BH, M = 192, 490, 4
    f = min((BW - 2 * M) / skin.width, (BH - 2 * M) / skin.height); pw, ph = round(skin.width * f), round(skin.height * f)
    ox, oy = (BW - pw) // 2, (BH - ph) // 2
    band = Image.new("RGBA", (BW, BH), (0, 0, 0, 0)); band.alpha_composite(skin.resize((pw, ph), Image.LANCZOS), (ox, oy))
    bL, bT = ox + math.ceil(sx * f), oy + math.ceil(sy * f); bR, bB = ox + math.floor((sx + sw) * f), oy + math.floor((sy + sh) * f)
    band.save(d / "mi-band-192x490.png")
    prev = Image.new("RGBA", (BW, BH), (0, 0, 0, 255)); dr = ImageDraw.Draw(prev)
    dr.rectangle([bL, bT, bR - 1, bB - 1], fill=(26, 40, 66, 255)); fw = bR - bL
    dr.text(((bL + bR) / 2, bT + (bB - bT) * 0.42), "12:34", font=font(fw * 0.30), fill=(240, 240, 240, 255), anchor="mm")
    dr.text(((bL + bR) / 2, bT + (bB - bT) * 0.66), "Mon 08.11", font=font(fw * 0.11), fill=(170, 200, 240, 255), anchor="mm")
    prev.alpha_composite(band); prev.convert("RGB").resize((BW * 2, BH * 2), Image.NEAREST).save(d / "preview.png")
    g = with_glass(d / "skin.png"); g.thumbnail((10000, 240), Image.LANCZOS); g.save(d / "thumb.png")
    for old in ("band_preview.png", "band_preview_2x.png"):
        if (d / old).exists(): (d / old).unlink()
    P["screen"] = {"skin_px": [sx, sy, sw, sh], "mm": scr["screen_mm"], "native_px": [nw, nh],
                   "note": "screen hole in skin.png (12 px/mm, 1 mm padding); exact native aspect"}
    P["exports"] = {"mi-band-192x490.png": {"size": [BW, BH], "screen_px": [bL, bT, bR - bL, bB - bT]}}
    save(d / "phone.json", P)
    acc = {"aspect": round(rep["aspect_w_h"], 4), "spec_aspect": round(wm / hm, 4),
           "aspect_error_pct": round(100 * (rep["aspect_w_h"] / (wm / hm) - 1), 2),
           "lean_deg": round(abs(sum(rep["side_tilt_deg"]) / 2), 3), "taper_deg": round(abs(rep["side_tilt_deg"][1] - rep["side_tilt_deg"][0]) / 2, 3),
           "deskew_deg": rep.get("deskew_deg", 0.0),
           "tilt_deg": max(abs(t) for t in rep["side_tilt_deg"]), "jitter_px": max(rep["side_jitter_px"]),
           "symmetry_iou": rep["lr_symmetry_iou"], "screen_aspect_error_pct": abs(scr["aspect_error_pct"])}
    ok = {"aspect_error_pct": abs(acc["aspect_error_pct"]) <= THRESHOLDS["aspect_error_pct"], "lean_deg": acc["lean_deg"] <= THRESHOLDS["lean_deg"],
          "screen_aspect_error_pct": acc["screen_aspect_error_pct"] <= THRESHOLDS["screen_aspect_error_pct"]}
    manual = b.get("acceptance", {}).get("manual", {"text_ok": False, "approved": False})
    b["acceptance"] = {"measured": acc, "pass": ok, "manual": manual}; save_build(a.id, b)
    # check sheet: skin + the text-fix areas, for the visual read
    S = with_glass(d / "skin.png"); S.thumbnail((10000, 900)); S.save(w / "check_sheet.png")
    for kx, v in acc.items(): print(f"{kx:26s} {v!s:>8}  {'info' if kx in INFO_ONLY or kx not in ok else ('ok' if ok[kx] else 'FAIL')}")
    print("PASS" if all(ok.values()) else "FAIL: see the lines above")
    print(f"text_ok={manual['text_ok']} approved={manual['approved']}  -> read every text on {d / 'skin.png'}, then: mark {a.id} --text-ok")


def cmd_mark(a):
    b = build(a.id); m = b.setdefault("acceptance", {}).setdefault("manual", {"text_ok": False, "approved": False})
    if a.text_ok: m["text_ok"] = True
    if a.approved: m["approved"] = True
    save_build(a.id, b); print(m)


# ---------------------------------------------------------------- pages
def phones_done():
    out = []
    for pj in sorted(PHONES.glob("*/*/phone.json")):
        d = pj.parent
        if (d / "skin.png").exists() and (d / "build.json").exists() and "acceptance" in load(d / "build.json", {}):
            out.append(d)
    return sorted(out, key=lambda d: (load(d / "phone.json").get("year") or 0, load(d / "phone.json")["model"]))


def host(u):
    return re.sub(r'^https?://(www\.|m\.)?', '', u).split('/')[0]


def credit(src):
    if not src or not src.get("url"): return ""
    who = f" by {src['author']}" if src.get("author") else ""
    lic = f", {src['license']}" if src.get("license") else ""
    return f"[photo]({src['url']}){who}{lic}"


def phone_page(d):
    P, B = load(d / "phone.json"), load(d / "build.json")
    name = f"{P['brand']} {P['model']}"; s = P["size_mm"]; dsp = P["display"]; sc = P["screen"]; ex = P["exports"]["mi-band-192x490.png"]["screen_px"]
    form = P["form"] + {"open": ", shown open", "closed": ", shown closed"}.get(P.get("view"), "")
    size = f"{s['width']} × {s['height']} mm" + {"open": " (open)", "closed": " (closed)"}.get(P.get("view"), "")
    if P.get("size_closed_mm"): size += f", {P['size_closed_mm']['width']} × {P['size_closed_mm']['height']} mm closed"
    srcs = P.get("sources", {}); specs = ", ".join(f"[{host(u)}]({u})" for u in srcs.get("specs", []))
    acc = B["acceptance"]["measured"]
    return f"""<!-- generated by tools/klapka.py pages: edit phone.json / build.json instead -->
# {name}

<p align="center">
  <img src="skin.png" height="520" alt="{name} skin">
  &nbsp;&nbsp;
  <img src="preview.png" height="520" alt="{name} on a Mi Band">
</p>

| | |
|---|---|
| Year | {P.get('year') or '–'} |
| Type | {form} |
| Size | {size} |
| Display | {dsp['diagonal_in']}″, {dsp['native_px'][0]} × {dsp['native_px'][1]} |
| Screen hole in `skin.png` | x {sc['skin_px'][0]}, y {sc['skin_px'][1]}, {sc['skin_px'][2]} × {sc['skin_px'][3]} px |

## Download

Click **Download**; the file saves straight away.

| File | What it is | |
|---|---|---|
| `skin.png` | the phone at 12 px/mm, transparent background, transparent screen | [Download](skin.png?raw=true) |
| `body.png` | the same without the screen hole | [Download](body.png?raw=true) |
| `mi-band-192x490.png` | ready for a Mi Band 7 / 8 / 9 watch face (192 × 490) | [Download](mi-band-192x490.png?raw=true) |
| `phone.json` | sizes and the screen position, for your own tools | [Download](phone.json?raw=true) |

**Mi Band 7 / 8 / 9:** use `mi-band-192x490.png` as the background and put the clock inside
the screen: x {ex[0]}, y {ex[1]}, {ex[2]} × {ex[3]} px.

## How it was made

Standard v1 ([docs/PIPELINE.md](../../../docs/PIPELINE.md)): measured to scale, re-rendered straight
and clean from a photo, every printed label checked.
Body aspect {acc['aspect']} (spec {acc['spec_aspect']}), screen at the exact {dsp['native_px'][0]}:{dsp['native_px'][1]} aspect.

**Credits:** appearance from a {credit(B.get('photo'))}; geometry measured on a {credit(srcs.get('geometry_photo'))}; specs: {specs or '–'}.

<sub>Trademarks belong to their owners. KLAPKA is a fan project and is not affiliated with any phone maker.</sub>
"""


def relpath(target, here):
    import os
    t = target.relative_to(ROOT).as_posix() if isinstance(target, Path) else target
    return os.path.relpath(t or ".", here or ".").replace("\\", "/")


def gallery(dirs, here, cols=4):
    """thumbnail table; links are relative to the folder `here` (repo-relative, "" = root)."""
    cells = []
    for d in dirs:
        P = load(d / "phone.json"); link = relpath(d, here)
        cells.append(f'<a href="{link}/"><img src="{link}/thumb.png" height="160" alt="{P["brand"]} {P["model"]}"></a>'
                     f'<br><b>{P["model"]}</b><br><sub>{P["brand"]} · {P.get("year") or ""}</sub>')
    rows = ["<table>"]
    for i in range(0, len(cells), cols):
        rows.append("<tr>" + "".join(f'<td align="center" width="{100 // cols}%">{c}</td>' for c in cells[i:i + cols]) + "</tr>")
    rows.append("</table>")
    return "\n".join(rows)


def replace_block(text, name, content):
    a, b = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    return re.sub(re.escape(a) + r".*?" + re.escape(b), lambda m: f"{a}\n{content}\n{b}", text, flags=re.S)


FORM_NAMES = {"candybar": "Candybar", "slider": "Slider", "flip": "Flip / clamshell", "swivel": "Swivel", "other": "Other"}
GEN = "<!-- generated by tools/klapka.py pages: do not edit by hand -->\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def browse_nav(here):
    c = relpath("catalog", here)
    return (f'<a href="{c}/years.md">By year</a> · <a href="{c}/brands.md">By brand</a> · '
            f'<a href="{c}/types.md">By type</a> · <a href="{c}/all.md">All phones</a>')


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def cmd_header(a):
    """README header animation from the hand-picked list in assets/header.json."""
    cfg = load(ROOT / "assets" / "header.json")
    dirs = [PHONES / p for p in cfg["phones"]]
    missing = [str(d) for d in dirs if not (d / "skin.png").exists()]
    if missing: raise SystemExit(f"not finished yet: {missing}")
    print(run("make_header.py", ROOT / "assets" / "header.png", *dirs, "--style", cfg.get("style", "amber")).strip())


def cmd_pages(a):
    import datetime
    dirs = phones_done(); catalog = []; today = datetime.date.today().isoformat()
    for d in dirs:
        B = load(d / "build.json")
        if "added" not in B:
            B["added"] = today; save(d / "build.json", B)
    by_year, by_brand, by_form = {}, {}, {}
    for d in dirs:
        P = load(d / "phone.json")
        by_year.setdefault(P.get("year") or 0, []).append(d)
        by_brand.setdefault(d.parent, []).append(d)
        by_form.setdefault(P["form"], []).append(d)

    # phone pages, with a navigation line above the title
    for d in dirs:
        P = load(d / "phone.json"); here = d.relative_to(ROOT).as_posix(); c = relpath("catalog", here)
        nav = (f'<p><a href="{relpath("", here)}/">KLAPKA</a> · <a href="{c}/years/{P.get("year")}.md">{P.get("year")}</a> · '
               f'<a href="../">{P["brand"]}</a> · <a href="{c}/types/{P["form"]}.md">{FORM_NAMES.get(P["form"], P["form"])}</a></p>\n')
        write(d / "README.md", phone_page(d).replace("\n# ", "\n" + nav + "\n# ", 1))
        catalog.append({"id": P["id"], "brand": P["brand"], "model": P["model"], "year": P.get("year"), "form": P["form"],
                        "view": P.get("view"), "added": load(d / "build.json")["added"], "size_mm": P["size_mm"],
                        "display": P["display"], "screen": P["screen"],
                        "files": {f: f"{here}/{f}" for f in ("skin.png", "body.png", "mi-band-192x490.png", "preview.png", "phone.json")}})
    save(ROOT / "catalog.json", {"standard": "v1", "count": len(catalog), "phones": catalog})

    cat = ROOT / "catalog"
    # by year: an index and one page per year with previous / next links
    years = sorted(by_year)
    lines = [f"| [{y}](years/{y}.md) | {len(by_year[y])} | " + ", ".join(load(d / "phone.json")["model"] for d in by_year[y][:8])
             + (" …" if len(by_year[y]) > 8 else "") + " |" for y in years]
    write(cat / "years.md", GEN + "# Phones by year\n\n" + browse_nav("catalog") + "\n\n| Year | Phones | |\n|---|---|---|\n" + "\n".join(lines) + "\n")
    for i, y in enumerate(years):
        prev = f"[← {years[i - 1]}]({years[i - 1]}.md)" if i else ""
        nxt = f"[{years[i + 1]} →]({years[i + 1]}.md)" if i + 1 < len(years) else ""
        write(cat / "years" / f"{y}.md", GEN + f"# {y}\n\n{browse_nav('catalog/years')}\n\n{prev}{' · ' if prev and nxt else ''}{nxt}\n\n"
              f"{plural(len(by_year[y]), 'phone')}.\n\n{gallery(by_year[y], 'catalog/years')}\n")
    # by brand: an index; each brand folder has its own gallery page
    lines = []
    for bd, ds in sorted(by_brand.items()):
        ys = [load(d / "phone.json").get("year") or 0 for d in ds]
        lines.append(f"| [{load(ds[0] / 'phone.json')['brand']}]({relpath(bd, 'catalog')}/) | {len(ds)} | {min(ys)}–{max(ys)} |")
    write(cat / "brands.md", GEN + "# Phones by brand\n\n" + browse_nav("catalog") + "\n\n| Brand | Phones | Years |\n|---|---|---|\n" + "\n".join(lines) + "\n")
    for bd, ds in by_brand.items():
        P = load(ds[0] / "phone.json"); here = bd.relative_to(ROOT).as_posix()
        write(bd / "README.md", GEN + f"# {P['brand']}\n\n{browse_nav(here)}\n\n{plural(len(ds), 'phone')}, oldest first. Click one to see and download it.\n\n{gallery(ds, here)}\n")
    write(PHONES / "README.md", GEN + "# Phones\n\n" + browse_nav("phones") + "\n\n" + "\n".join(
        f"- [{load(ds[0] / 'phone.json')['brand']}]({bd.name}/) ({len(ds)})" for bd, ds in sorted(by_brand.items())) + "\n")
    # by type
    write(cat / "types.md", GEN + "# Phones by type\n\n" + browse_nav("catalog") + "\n\nSliders and flips are shown open; keypad flips over a touchscreen (Sony Ericsson P series) closed.\n\n| Type | Phones |\n|---|---|\n"
          + "\n".join(f"| [{FORM_NAMES.get(fm, fm)}](types/{fm}.md) | {len(ds)} |" for fm, ds in sorted(by_form.items())) + "\n")
    for fm, ds in by_form.items():
        write(cat / "types" / f"{fm}.md", GEN + f"# {FORM_NAMES.get(fm, fm)}\n\n{browse_nav('catalog/types')}\n\n{plural(len(ds), 'phone')}, oldest first.\n\n{gallery(ds, 'catalog/types')}\n")
    # all phones: a plain table, light enough for hundreds of rows
    rows = []
    for d in dirs:
        P = load(d / "phone.json"); dsp = P["display"]
        rows.append(f"| [{P['model']}]({relpath(d, 'catalog')}/) | {P['brand']} | {P.get('year') or ''} | {FORM_NAMES.get(P['form'], P['form'])} | "
                    f"{P['size_mm']['width']} × {P['size_mm']['height']} mm | {dsp['diagonal_in']}″ {dsp['native_px'][0]}×{dsp['native_px'][1]} |")
    write(cat / "all.md", GEN + f"# All phones ({len(dirs)})\n\n{browse_nav('catalog')}\n\nOldest first. Machine-readable: [catalog.json](../catalog.json).\n\n"
          "| Model | Brand | Year | Type | Size | Display |\n|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n")

    # front page: the header animation, counts, browse links and the newest additions only
    recent = sorted(dirs, key=lambda d: (load(d / "build.json")["added"], load(d / "phone.json").get("year") or 0), reverse=True)[:8]
    readme = ROOT / "README.md"
    if readme.exists():
        t = readme.read_text(encoding="utf-8"); ny = [y for y in years if y]
        t = replace_block(t, "RECENT", gallery(recent, ""))
        t = replace_block(t, "COUNT", f"**{plural(len(dirs), 'phone')}** from {plural(len(by_brand), 'brand')}, {min(ny)}–{max(ny)}")
        t = replace_block(t, "BROWSE", "\n".join([
            "- **[By year](catalog/years.md)**: " + " · ".join(f"[{y}](catalog/years/{y}.md)" for y in ny),
            "- **[By brand](catalog/brands.md)**: " + " · ".join(f"[{load(ds[0] / 'phone.json')['brand']}]({relpath(bd, '')}/)" for bd, ds in sorted(by_brand.items())),
            "- **[By type](catalog/types.md)**: " + " · ".join(f"[{FORM_NAMES.get(fm, fm)}](catalog/types/{fm}.md)" for fm in sorted(by_form)),
            "- **[All phones](catalog/all.md)** in one table, or [catalog.json](catalog.json) for your own tools"]))
        readme.write_text(t, encoding="utf-8")
    print(f"{len(dirs)} phone pages, {len(by_brand)} brands, {len(years)} years, {len(by_form)} types, catalog/, catalog.json")


# ---------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("new"); p.add_argument("id"); p.add_argument("--brand", required=True); p.add_argument("--model", required=True)
    p = sp.add_parser("measure"); p.add_argument("id"); p.add_argument("photo"); p.add_argument("--bbox")
    p = sp.add_parser("template"); p.add_argument("id"); p.add_argument("--size"); p.add_argument("--px-per-mm", type=float)
    p = sp.add_parser("photo"); p.add_argument("id"); p.add_argument("path"); p.add_argument("--source", required=True); p.add_argument("--license", required=True); p.add_argument("--author")
    p = sp.add_parser("pass1"); p.add_argument("id"); p.add_argument("--seeds", default="1,2,3,4")
    p = sp.add_parser("pass2"); p.add_argument("id"); p.add_argument("--seed", type=int, default=1); p.add_argument("--from-seed", type=int); p.add_argument("--reuse", action="store_true", help="restart text fixes from the existing p2.png")
    p = sp.add_parser("grid"); p.add_argument("id")
    p = sp.add_parser("textfix"); p.add_argument("id"); p.add_argument("--keypad", action="store_true"); p.add_argument("--row", type=int, help="one row of keys (1 = top), labels from phone.json"); p.add_argument("--text"); p.add_argument("--box"); p.add_argument("--seed", type=int, default=1)
    p = sp.add_parser("rows"); p.add_argument("id")
    p = sp.add_parser("restore"); p.add_argument("id"); p.add_argument("--rows", type=int, nargs="*", default=[]); p.add_argument("--box"); p.add_argument("--feather", type=int, default=6, help="soft edge in px (use 1-2 for thin strips)")
    p = sp.add_parser("finish"); p.add_argument("id"); p.add_argument("--screen", help="display rectangle on work/final.png: x0,y0,x1,y1 (when the automatic one misses)")
    p = sp.add_parser("mark"); p.add_argument("id"); p.add_argument("--text-ok", action="store_true"); p.add_argument("--approved", action="store_true")
    sp.add_parser("pages")
    sp.add_parser("header")
    a = ap.parse_args()
    {"new": cmd_new, "measure": cmd_measure, "template": cmd_template, "photo": cmd_photo, "pass1": cmd_pass1, "pass2": cmd_pass2, "grid": cmd_grid,
     "textfix": cmd_textfix, "rows": cmd_rows, "restore": cmd_restore, "finish": cmd_finish, "mark": cmd_mark, "pages": cmd_pages, "header": cmd_header}[a.cmd](a)


if __name__ == "__main__":
    main()
