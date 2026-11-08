## Phones

<!-- e.g. sony-ericsson/k750i (new), sony-ericsson/w995 (fix: # key icons) -->

## Sources

<!-- spec sheets and photos with licence and author; the phone's build.json and phone.json list them too -->

## Checklist

- [ ] Made with the standard (`docs/PIPELINE.md`) through `tools/klapka.py`
- [ ] `finish` ends with `PASS`
- [ ] `work/screen_check.png` checked: the hole covers the lit display only, centred, then `mark --screen-ok`
- [ ] Every printed label and word read letter by letter on `skin.png`, then `mark --text-ok`
- [ ] `pages` run; only phone files and the regenerated pages are committed
- [ ] No reference photos, no `work/` files, no `klapka.local.json`
