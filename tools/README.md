# KLAPKA tools

Python 3.10+ with `pip install -r requirements.txt`. Run from the repo root.
An image server is needed for the render steps (see `AGENTS.md`, Setup).

**Use `tools/klapka.py`**: it runs the standard (`docs/PIPELINE.md`) step by step and keeps the
records in `build.json`. The other scripts are what it calls; they also work on their own.

| Script | Used in | What it does |
|---|---|---|
| `klapka.py` | all steps | `new`, `measure`, `template`, `photo`, `pass1`, `pass2`, `grid`, `rows`, `textfix`, `restore`, `finish`, `mark`, `pages`, `header` |
| `make_template.py` | template | layout drawn from `phone.json`: body, seams, screen at the exact native aspect, keypad block |
| `cgi_edit.py` | pass1, pass2, textfix | one Qwen-Image 2.1 edit; fills prompt placeholders from `phone.json`; writes a JSON sidecar |
| `backend.py` | – | finds the image server (`KLAPKA_SD_URL`, `klapka.local.json` or KLIF) |
| `score_render.py` | pass1 | ranks renders: white background, body aspect within 3%, then the best screen match |
| `fix_text.py` | textfix | cut, enlarge to an exact multiple of 32, paste back colour-matched with a feathered edge; alpha untouched |
| `clean_alpha.py` | finish | alpha cleanup, edge colour clean-up, 12 px/mm master with 1 mm padding; measures tilt, jitter, symmetry |
| `mark_screen.py` | finish | display window (automatic, or `--window` by hand, `--no-refine` to keep it exact) painted as glass, exact-aspect hole centred in it, visible-border check and balancing |
| `make_header.py` | header | the README header animation: letters of KLAPKA on lit LCDs, phones stepping past one place per second (animated PNG) |
| `contact_sheet.py` | – | images side by side on a checkerboard, for looking |

Standard prompts (`tools/prompts.json`): `koks_template` (pass 1), `cutout` (pass 2),
`fix_key_row`, `fix_keypad_tpl` and `fix_text` (text pass).

Kept for reference, not part of the standard: `preview_band.py` (old preview), `prep_ref.py`,
`fit_quad.py`, `rectify.py` (photo-only approaches rejected in `docs/PIPELINE.md`),
`tools/prompts_archive.json`.
