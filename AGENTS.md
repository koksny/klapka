# AGENTS.md: adding or fixing a phone with an AI agent

This file is for AI coding agents (any vendor). It explains how to add a phone to KLAPKA or fix one,
from finding photos to the pull request. Humans: [CONTRIBUTING.md](CONTRIBUTING.md).

KLAPKA is an archive of retro phone skins: each phone as a straight-on PNG at 12 px/mm with a
transparent screen at the exact native aspect, plus its data in `phone.json`. Every phone is made with
the same process, the **standard**: [docs/PIPELINE.md](docs/PIPELINE.md). `tools/klapka.py` runs it
step by step.

## Ground rules

1. **Follow the standard.** Do not change it in a pull request that adds or fixes phones; propose
   changes in an issue first.
2. **Sliders, flips and swivels are shown open** (keypad slid out, clamshell unfolded, swivel turned
   out). Exception: a keypad
   flip that closes over a touchscreen (Sony Ericsson P800, P900, P910i, P990i) is shown closed;
   see [docs/PIPELINE.md](docs/PIPELINE.md#rules).
3. **Photos:** prefer photos of original, unmodified phones (no operator stickers, no aftermarket
   covers), see [docs/REFERENCES.md](docs/REFERENCES.md). Photos are input only and are never
   committed (keep them in `refs/`), so any source works, whatever its licence: press shots, shops,
   reviews. Record each photo's URL (and author, when known).
4. **Never trust printed text from the image model.** Read every label on the final image letter by
   letter. Run `klapka.py mark <id> --text-ok` only after you have done that.
5. **Use only the prompts in `tools/prompts.json`**, through `tools/klapka.py`. One image request at a
   time.
6. **Commit only** the files listed in step 10. Never commit `refs/`, `phones/**/work/` or
   `klapka.local.json`.
7. **You need to see images.** Measuring, choosing seeds and reading labels are visual checks. If you
   cannot view images, stop and say so.

## Setup

- Python 3.10+ and `pip install -r requirements.txt`.
- An image server: [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) `sd-server`
  running **Qwen-Image 2.1** (the Turbo version with 8 steps is what the standard uses), with the
  A1111-style API (`POST /sdapi/v1/txt2img` with `extra_images`). Tell the tools where it is:
  `KLAPKA_SD_URL=http://127.0.0.1:PORT`, or `{"sd_url": "http://127.0.0.1:PORT"}` in
  `klapka.local.json` (not committed). [KLIF](https://github.com/koksny/klif) users can give
  `{"klif_cli": "path/to/klif-cli"}` instead.
- Run everything from the repo root.

## Workflow A: add a phone

Example id: `sony-ericsson/k750i` (`<brand>/<model>`, lowercase, dashes).

**1. Check it is new.** Look for the model in `catalog.json`. If it is there, use workflow B.

**2. Find sources.**
- Specs: body width × height (and the open size for sliders and flips), display diagonal and
  resolution. Use two sources when you can; note them in `sources.specs`.
- A **geometry photo**: the most frontal photo you can find, to measure where the screen, keypad and
  seams sit. Phones that share a chassis (K750i and W800i) can share the body and screen
  measurements, but measure the keypad on the model itself: it can sit differently.
- An **appearance photo**: a photo of an original unit. It does not need to be perfectly frontal,
  but the closer to straight-on the better: the render keeps a little of the photo's angle. Readable
  labels mean fewer text fixes. Any source works: Wikimedia Commons, press shots, shop and review
  photos.
- Save downloads under `refs/<brand>/<model>/`.

**3. Create and fill `phone.json`.**
```
python tools/klapka.py new sony-ericsson/k750i --brand "Sony Ericsson" --model K750i
```
Fill it in; [docs/FORMAT.md](docs/FORMAT.md) explains every field and
[schema/phone.schema.json](schema/phone.schema.json) validates it. Once `size_mm` is filled, measure
the layout on the geometry photo:
```
python tools/klapka.py measure sony-ericsson/k750i refs/sony-ericsson/k750i/front.jpg
```
It finds the body, stretches it to the real size and draws a millimetre grid
(`work/measure_grid.png`: a line every mm, cyan every 5 mm, magenta every 10 mm), so positions read
straight off in mm. Check `work/measure_bbox.png`: if the box caught a hand or a shadow, give it
yourself with `--bbox x0,y0,x1,y1` (photo pixels). A photo rotated by more than a few degrees
measures badly; find a straighter one (phones that share a chassis, like the K750i and W800i, can
share measurements; say so in `size_note`).
- When a spec value cannot be right (a display diagonal that does not fit the measured glass), use
  what fits and explain it in `size_note`.
- `layout_mm.screen.y` is the top edge of the display glass in mm from the top of the body. Leave
  `x`, `w`, `h` null: they are computed from the diagonal at the exact native aspect, centred.
- `layout_mm.keypad` is the block of number keys; `layout_mm.seams` marks where the parts of a
  slider or flip meet.
- `texts` lists printed words on the front (brand, sub-brands); `keys` lists the key labels row by
  row; `key_icons` describes icons next to labels in words.

**4. Template.**
```
python tools/klapka.py template sony-ericsson/k750i
```
Look at `phones/sony-ericsson/k750i/work/template.png`: grey body, black screen, light grey keypad,
at the real proportions. If something is clearly off, fix `phone.json` and run it again.

**5. Photo.**
```
python tools/klapka.py photo sony-ericsson/k750i refs/sony-ericsson/k750i/photo.jpg --source "https://commons.wikimedia.org/wiki/File:..." --license "CC BY-SA 4.0" --author "Name"   # licence and author only if known
```

**6. Pass 1: four renders, ranked by geometry.**
```
python tools/klapka.py pass1 sony-ericsson/k750i
```
Seeds are ranked by geometry relative to the phone itself (scale does not matter): a seed is `ok`
when its background is white, its body aspect is within 3% of the template and the screen is centred
where the template puts it (within 1% of the body width); among those, the best screen match and
left/right symmetry win. Look at `work/pass1_sheet.png` and check that the winner looks straight-on:
both side bezels equally thick, no side panel showing, the bottom edge level. If no seed is `ok`, or
the winner looks turned, render more (`--seeds 1,2,3,4,5,6,7,8`) or use a more frontal photo: the
render keeps the photo's viewing angle a little.

**7. Pass 2: background removal.**
```
python tools/klapka.py pass2 sony-ericsson/k750i
```

**8. Read and fix every printed text.**
```
python tools/klapka.py grid sony-ericsson/k750i
```
Read every word and key label on `work/final_grid.png` (the grid labels are pixel coordinates of
`work/final.png`). For each area with a mistake:
```
python tools/klapka.py textfix sony-ericsson/k750i --row 3
python tools/klapka.py textfix sony-ericsson/k750i --text "Sony Ericsson" --box 150,180,520,230
```
Before `--row`, run `python tools/klapka.py rows <id>` and look at `work/rows_check.png`: the
numbered boxes must sit on the rows of number keys (1 = the row with 1 2 3). If they are shifted
(a logo or badge under the keypad can pull them down), pass that row's box yourself:
`--row 3 --box x0,y0,x1,y1` (coordinates from `work/final_grid.png`).

**Fix as little as possible.** Every redraw can drift the small icons next to the labels, so fix only
the rows of keys that are wrong (`--row N`, 1 = top row, labels from `phone.json` `keys`) and leave
correct rows alone. `--row` finds the rows on the render itself; `--keypad` takes the template's
keypad block and redraws everything at once, so use it only when most rows are wrong (then it is the
best tool: it got every label right at the first seed on three phones where word fixes kept returning
the same garbled letters), and then put the rows that were already right back from the clean cutout:
```
python tools/klapka.py restore sony-ericsson/k750i --rows 1 4
```
For a word, give a tight box around it. `key_icons` in `phone.json` must describe this model's own
icons (they differ between models). Check `work/fixN_check.png` (before above, after below).

- **A label that keeps coming back wrong** (the edit tends to keep the glyph shape it sees, so two or
  three tries give the same wrong letter): switch to another seed that passed step 6,
  `pass2 <id> --from-seed N`, and read again.
- **One key wrong:** fix just that key with the row prompt and a description, never with `--text` alone
  (that prompt writes a description out literally):
  `textfix <id> --row 4 --box x0,y0,x1,y1 --text "a single key: a large '*' on the left, and on the right the small letters 'a/A' with a small key-lock symbol"`.
  Give the key's box (the row from `rows_check.png`, one column of the keypad).
- **Only the letters are wrong** (digit and key fine): the cleanest fix is the word prompt on a tight
  box around just those letters, e.g. `textfix <id> --text "PQRS" --box …`. Redrawing a whole key can
  change its colour and size so it no longer matches its neighbours.
- **A fix went wrong:** `pass2 <id> --reuse` starts the text fixes over from the clean cutout (no new
  render), or try `--seed 2`. To undo one small area, `restore <id> --box x0,y0,x1,y1 --feather 2`.
- **Keep word boxes clear of their neighbours:** a box that cuts through a glyph erases the part
  inside it (a `*` became `→)`, a `5` lost its right half); `restore` that glyph from the cutout.
- **A single character** (`*`, `#`) through the word prompt comes back with the quote marks drawn as
  commas; use the row prompt: `textfix <id> --row 4 --box … --text "*"`.
- Do not erase letters and ask the model to write them on an empty key: it gets the letters right
  but too large, and it redraws the digit.

**9. Finish and verify.**
```
python tools/klapka.py finish sony-ericsson/k750i
```
It must end with `PASS` (lines marked `info` are recorded but not pass/fail; thresholds in
[docs/PIPELINE.md](docs/PIPELINE.md#acceptance)).
Then look at `work/screen_check.png` (the body before cutting): the **green box is the display
window** and must follow the inside edge of the bezel on all four sides; the magenta hole sits in its
middle, and the whole window is painted as dark glass. The automatic window finder misses often (it
can grab a bezel ring or the screen content). When it does, read the window off `body.png` and give it
by hand: `finish <id> --window x0,y0,x1,y1` (body.png pixels; it is remembered). Each side then snaps
to the strongest edge within 7 px, which can jump from the outer to the inner edge of a thin dark LCD
border on one side only and shift the hole by half a millimetre. To avoid that, read the four edges
off a luminance profile across each side (where the bezel ends and the glass or the dark LCD border
begins) and add `--no-refine` to use them exactly. A bright frame line (bezel highlight) belongs
outside the window on all four sides or on none. Where the render's screen content reaches the window
edge, give the window 1–2 px beyond it: the window has rounded corners and would leave a light speck.

When the brand or a logo is printed on the glass around the display (one glass panel over the
face, e.g. W880i, W890i, W910i), the window is the LCD rectangle inside the panel, never the whole
panel: a window over the print paints it black.

`finish` also measures the **visible border**: on the finished skin, the dark band from each hole edge
out to the bezel. Opposite sides may differ by at most 0.3 mm; when a dark LCD border was left outside
the window on one side, the hole is re-centred in the whole dark area. On a dark front (the band runs
more than 2 mm past the window, e.g. a black phone) the band is the body itself, so only the window
counts there (`dark_front` in the checks). A wrong window paints the bezel black, so never skip this
look. Only when the green box is right:
```
python tools/klapka.py mark sony-ericsson/k750i --screen-ok
```
Then read every text on `skin.png` once more and, only if all of it is right:
```
python tools/klapka.py mark sony-ericsson/k750i --text-ok
python tools/klapka.py pages
```

**10. Commit and open a pull request.** Commit only:
- `phones/<brand>/<model>/`: `README.md`, `phone.json`, `build.json`, `skin.png`, `body.png`,
  `skin-black.png`, `mi-band-192x490.png`, `preview.png`, `thumb.png`
- everything `pages` regenerated: `README.md`, `phones/README.md`, `phones/<brand>/README.md`,
  `catalog/`, `catalog.json` (not `assets/header.png`: the header is a fixed line-up the maintainer picks)

Fill in the pull request template. A maintainer looks at the result before it is merged.

## Workflow B: fix a phone

1. Read the issue or the problem, and the phone's `build.json` (how it was made).
2. Wrong label → workflow A step 8 on that phone (run `pass2` first if `work/` is gone; you then need
   `pass1` too, since `work/` is not committed).
3. Wrong size or screen position → correct `phone.json` with a source, then steps 4 to 9.
4. Finish with steps 9 and 10, and say in the pull request what was wrong and how you checked it.

## Workflow C: a "Request a phone" issue

1. Check `catalog.json`; if the phone exists, link it in the issue.
2. Otherwise run workflow A. Use photos the requester linked when they show an original unit.
3. Link the pull request in the issue.

## When something goes wrong

| Problem | What to do |
|---|---|
| `No image server` | set `KLAPKA_SD_URL` or `klapka.local.json` (Setup) |
| best seed too narrow or too short | more seeds (`--seeds 5,6,7,8`); check `size_mm` and the template |
| the render copies the photo's screen content | fine: the screen is cut out in `finish` |
| a text fix comes out wrong | tighter `--box`, another `--seed`; never accept a wrong label |
| `finish` fails on the screen aspect | check `layout_mm.screen.y` and `display` in `phone.json` |
| model ignores the photo and draws a flat grey phone | the template is fine; try other seeds or a clearer photo |
| the phone looks turned or lopsided (one side panel showing, screen off-centre) | the photo was taken at an angle: the render keeps a little of it. Use a more frontal photo |
| the body comes out several % too wide although the photo looks frontal | the photo was taken from above or below (keystone: one end wider than the other). Measure the body width at the top and the bottom of the photo; if they differ, run `tools/rectify.py` with the four corners first |
| keypad rows are tilted while the body is straight | the photo was at an angle; use an orthographic press render or a straight-on photo and render again |
| the key rows in `rows_check.png` sit on the wrong keys | the keypad block in `phone.json` is off; measure it on this model's photo, not a sister model's |
| the green window in `work/screen_check.png` misses the bezel's inside edge | `finish <id> --window x0,y0,x1,y1 --no-refine` with the edges read off `body.png` |
| the hole looks off-centre although `finish` passes | a thin frame line or dark border is inside the window on one side and outside on the other; give the window exactly (`--no-refine`) |
| a photo shows an operator logo or sticker (e.g. "vodafone") | use another photo: it ends up on the skin |
| a spec value cannot be right (a diagonal that does not fit the measured glass) | use what fits the measurement and explain it in `size_note` |
| downloads from Wikimedia fail with an HTML error page | rate limit: send a descriptive User-Agent and retry with a pause |
