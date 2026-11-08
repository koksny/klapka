# File format

Every phone lives in `phones/<brand>/<model>/` and has the same files.

## Images

| File | Size | Contents |
|---|---|---|
| `skin.png` | phone + 1 mm on each side, at **12 px/mm** | RGBA. Fully transparent around the phone and inside the screen hole; the phone is opaque with anti-aliased edges. Colour values under fully transparent pixels are 0. |
| `body.png` | same as `skin.png` | the same image with the screen glass left in |
| `mi-band-192x490.png` | 192 × 490 | the skin fitted into a Mi Band 7 / 8 / 9 screen with a 4 px margin, transparent around it and in the screen |
| `preview.png` | 384 × 980 | the Mi Band export with a sample clock, on black, enlarged 2× (for the page) |
| `thumb.png` | 240 px tall | the skin with dark glass in the screen (for galleries) |

Because every `skin.png` uses the same 12 px/mm scale, phones can be placed side by side at their real
relative sizes without resizing.

Coordinates are in pixels, origin top-left, `[x, y, width, height]`.

## `phone.json`

Validated by [schema/phone.schema.json](../schema/phone.schema.json).

| Field | Meaning |
|---|---|
| `id` | `<brand>/<model>`, the folder name |
| `brand`, `model`, `year` | as sold |
| `form` | `candybar`, `slider`, `flip`, `swivel` or `other` |
| `view` | `front` (candybar), `open` (sliders and flips) or `closed` (keypad flips over a touchscreen, e.g. the Sony Ericsson P series) |
| `size_mm` | width, height, depth of the shown state (open size for sliders and flips) |
| `size_closed_mm` | for sliders and flips: the closed size from the spec sheet |
| `size_note` | how a size was measured when it is not in a spec sheet |
| `corner_radius_mm` | body corner radius |
| `display` | `native_px` [w, h], `diagonal_in`, `type` |
| `layout_mm.screen` | display glass in mm from the body's top-left corner; `w`/`h` follow from the diagonal at the exact native aspect, `x` is centred unless set |
| `layout_mm.keypad` | the block of number keys, in mm |
| `layout_mm.seams` | for sliders and flips: `[{"y": mm}]` where the parts meet |
| `texts` | printed words on the front, e.g. `["Sony Ericsson", "Cyber-shot"]` |
| `keys` | key labels row by row, e.g. `[["1", "2 ABC", "3 DEF"], ...]` |
| `key_icons` | icons next to labels, in words |
| `keypad_labels` | the letters line used in the render prompt |
| `screen` | written by the tools: the screen hole in `skin.png` (`skin_px`), in mm, and `native_px` |
| `exports` | written by the tools: per export file, its size and the screen rectangle in it |
| `sources` | `specs` (URLs) and `geometry_photo` (url, license, author) |

## `build.json`

Written by `tools/klapka.py`: how the phone was made (template size and scale, the appearance photo
with its licence, every pass-1 seed with its score, pass 2, each text fix with its box) and the
acceptance results. Together with `phone.json` it is enough to make the phone again.
