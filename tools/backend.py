"""Where the image server is. Any stable-diffusion.cpp server running Qwen-Image 2.1 that speaks the
A1111-style API (POST /sdapi/v1/txt2img with "extra_images") works. Looked up in this order:

1. env KLAPKA_SD_URL, e.g. http://127.0.0.1:1235
2. klapka.local.json in the repo root (not committed): {"sd_url": "..."} or {"klif_cli": "path/to/klif-cli"}
3. KLIF (https://github.com/koksny/klif): klif-cli on PATH or env KLIF_CLI; its System CGI must be online
"""
import json, os, shutil, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _local():
    p = ROOT / "klapka.local.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def server():
    """Returns (base_url, info dict). Raises SystemExit with a clear message when nothing is found."""
    url = os.environ.get("KLAPKA_SD_URL") or _local().get("sd_url")
    if url:
        return url.rstrip("/"), {"backend": "sd_url"}
    cli = os.environ.get("KLIF_CLI") or _local().get("klif_cli") or shutil.which("klif-cli")
    if not cli:
        raise SystemExit("No image server: set KLAPKA_SD_URL to a stable-diffusion.cpp server running Qwen-Image 2.1, "
                         "or put {\"sd_url\": \"http://host:port\"} in klapka.local.json (see AGENTS.md).")
    for _ in range(30):  # "busy" lingers for a moment after the previous request
        st = json.loads(subprocess.run([cli, "--json", "status", "cgi"], capture_output=True, text=True, check=True).stdout)
        if st.get("status") != "busy":
            break
        time.sleep(2)
    if st.get("status") != "online":
        raise SystemExit(f"KLIF System CGI is not online ({st.get('status')}); start it with: klif-cli launch cgi --yes --wait")
    if st.get("apiKey"):
        raise SystemExit("KLIF System CGI wants an API key; this tool does not handle keys.")
    if st.get("preset") != "qwen-image-21":   # the standard renders on Qwen-Image 2.1 Turbo; CGI is shared and may run another model
        raise SystemExit(f"KLIF System CGI runs preset {st.get('preset')!r} ({st.get('model')}); the standard needs qwen-image-21: "
                         "klif-cli presets use cgi qwen-image-21, then klif-cli restart cgi --yes --wait")
    return st["baseUrl"].rstrip("/"), {"backend": "klif", "preset": st.get("preset"), "model": st.get("model")}
