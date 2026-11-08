"""One Qwen-Image 2.1 edit on the image server (see backend.py): the first reference image sets the
canvas size, further references (--ref2) are extra inputs. Saves the PNG plus a JSON sidecar with
everything needed to repeat it (prompt, seed, size, sampler, model, reference hashes, time).
One request at a time.

python tools/cgi_edit.py --ref REF.png [--ref2 IMG] --prompt-file tools/prompts.json --prompt-id ID
                         [--phone phone.json] [--text "Sony Ericsson"] --seed N --out OUT.png

Placeholders in a prompt: {texts} {keys} {key_rows} {key_icons} come from --phone, {text} from --text.
"""
import argparse, base64, hashlib, json, sys, time, urllib.request
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import server  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--ref", required=True)
ap.add_argument("--ref2", action="append", default=[], help="extra reference images")
ap.add_argument("--prompt-file", required=True)
ap.add_argument("--prompt-id", required=True)
ap.add_argument("--phone", help="phone.json: fills {texts} {keys} {key_rows} {key_icons}")
ap.add_argument("--text", help="fills {text}")
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--steps", type=int, default=8)
ap.add_argument("--allow-large", action="store_true", help="allow > 1,048,576 px (sd.cpp then slows down later images)")
ap.add_argument("--out", required=True)
a = ap.parse_args()

prompt = json.load(open(a.prompt_file, encoding="utf-8"))[a.prompt_id]
if a.phone:
    ph = json.load(open(a.phone, encoding="utf-8"))
    rows = "; ".join(f"row {i}: " + ", ".join(f"'{k}'" for k in r) for i, r in enumerate(ph.get("keys", []), 1))
    fill = {"texts": ". ".join(ph.get("texts", [ph["brand"]])), "keys": ph.get("keypad_labels", ""),
            "key_rows": rows, "key_icons": ph.get("key_icons", "")}
    for k, v in fill.items():
        prompt = prompt.replace("{" + k + "}", v)
if a.text is not None:
    prompt = prompt.replace("{text}", a.text)

ref_bytes = open(a.ref, "rb").read()
w, h = Image.open(a.ref).size
assert w % 32 == 0 and h % 32 == 0, "canvas must be multiples of 32 (the server rounds other sizes)"
assert a.allow_large or w * h <= 1_048_576, "canvas must be at most 1,048,576 px"
extra = [ref_bytes] + [open(p, "rb").read() for p in a.ref2]
base, info = server()
body = {"prompt": prompt, "width": w, "height": h, "seed": a.seed, "steps": a.steps, "cfg_scale": 1.0,
        "sampler_name": "euler", "extra_images": [base64.b64encode(b).decode() for b in extra]}
req = urllib.request.Request(base + "/sdapi/v1/txt2img", data=json.dumps(body).encode("utf-8"),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=900) as r:
    res = json.loads(r.read())
dt = time.time() - t0
open(a.out, "wb").write(base64.b64decode(res["images"][0]))
meta = {"out": a.out, "prompt_id": a.prompt_id, "prompt": prompt, "seed": a.seed, "steps": a.steps, "width": w, "height": h,
        "cfg_scale": 1.0, "sampler_name": "euler", **info, "refs": [a.ref] + a.ref2,
        "ref_sha256": [hashlib.sha256(b).hexdigest() for b in extra], "seconds": round(dt, 1)}
json.dump(meta, open(a.out.rsplit(".", 1)[0] + ".json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
im = Image.open(a.out)
print(json.dumps({"out": a.out, "mode": im.mode, "size": im.size, "seconds": round(dt, 1)}))
