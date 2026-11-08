<div align="center">

<img src="assets/lineup.png" alt="The phones in KLAPKA, side by side at their real sizes" width="100%">

# KLAPKA

**Koksny Legacy Archive of Phones, Keypads & Assets**

The phones we grew up with, as clean skins with a see-through screen.<br>
Free, measured to scale, ready for your watch face, wallpaper or emulator.

<!-- COUNT:START -->
**7 phones** so far
<!-- COUNT:END --> · [Browse](#phones) · [Download](#get-a-skin-no-git-needed) · [Request a phone](https://github.com/koksny/klapka/issues/new?template=request-a-phone.yml) · [For AI agents](AGENTS.md)

</div>

---

## Phones

Click a phone to see it big and download it.

<!-- GALLERY:START -->
<table>
<tr><td align="center" width="25%"><a href="phones/sony-ericsson/k700i/"><img src="phones/sony-ericsson/k700i/thumb.png" height="160" alt="Sony Ericsson K700i"></a><br><b>K700i</b><br><sub>2004</sub></td><td align="center" width="25%"><a href="phones/sony-ericsson/k750i/"><img src="phones/sony-ericsson/k750i/thumb.png" height="160" alt="Sony Ericsson K750i"></a><br><b>K750i</b><br><sub>2005</sub></td><td align="center" width="25%"><a href="phones/sony-ericsson/k800i/"><img src="phones/sony-ericsson/k800i/thumb.png" height="160" alt="Sony Ericsson K800i"></a><br><b>K800i</b><br><sub>2006</sub></td><td align="center" width="25%"><a href="phones/sony-ericsson/t610/"><img src="phones/sony-ericsson/t610/thumb.png" height="160" alt="Sony Ericsson T610"></a><br><b>T610</b><br><sub>2003</sub></td></tr>
<tr><td align="center" width="25%"><a href="phones/sony-ericsson/w800i/"><img src="phones/sony-ericsson/w800i/thumb.png" height="160" alt="Sony Ericsson W800i"></a><br><b>W800i</b><br><sub>2005</sub></td><td align="center" width="25%"><a href="phones/sony-ericsson/w810i/"><img src="phones/sony-ericsson/w810i/thumb.png" height="160" alt="Sony Ericsson W810i"></a><br><b>W810i</b><br><sub>2006</sub></td><td align="center" width="25%"><a href="phones/sony-ericsson/w995/"><img src="phones/sony-ericsson/w995/thumb.png" height="160" alt="Sony Ericsson W995"></a><br><b>W995</b><br><sub>2009</sub></td></tr>
</table>
<!-- GALLERY:END -->

All phones by brand: [phones/](phones/)

## Get a skin (no Git needed)

1. Click a phone above.
2. On its page, click **Download** next to the file you want. That's it.

Want everything at once? Click the green **Code** button at the top of this page, then **Download ZIP**.

## What you get

Every phone comes in the same format, so they work together:

| File | What it is |
|---|---|
| `skin.png` | the phone, straight-on, at **12 pixels per millimetre**, transparent around it and in the screen |
| `body.png` | the same, with the screen glass left in |
| `mi-band-192x490.png` | ready-made background for a **Mi Band 7 / 8 / 9** watch face |
| `phone.json` | real size, display, and the exact screen position in every file |

The screen hole always has the phone's real screen proportions (for example 240 × 320 → 3:4),
so anything you put behind it fits the way it did on the original phone. Phones with a slider or a
flip are always shown **open**. Details: [docs/FORMAT.md](docs/FORMAT.md).

## Mi Band in two steps

1. Download `mi-band-192x490.png` from the phone's page.
2. In your watch face editor, set it as the background and put the clock inside the screen area.
   The phone's page gives the exact numbers (x, y, width, height).

## Missing your phone? Spotted a mistake?

- **[Request a phone](https://github.com/koksny/klapka/issues/new?template=request-a-phone.yml)**: tell us the model (and colour, if it matters).
  A link to a photo of an original, unmodified one helps a lot.
- **[Report a mistake](https://github.com/koksny/klapka/issues/new?template=fix-a-phone.yml)**: wrong label, wrong size, odd detail.

You need a free GitHub account to open an issue.

## Make one yourself

Every phone here was made with the same documented process, and the tools are in this repo.
If you use an AI coding agent, point it at **[AGENTS.md](AGENTS.md)**: it explains the whole process
step by step, so the agent can add a phone or fix one and open a pull request.
Without an agent, start with [CONTRIBUTING.md](CONTRIBUTING.md).

## How the skins are made

1. **Measure:** real size from spec sheets, the screen drawn at its exact native proportions.
2. **Render:** an image model redraws the phone from an ordinary photo into that exact layout,
   straight-on and clean.
3. **Check every label:** printed text is read letter by letter; anything wrong is redrawn on its own.
4. **Cut and verify:** the background and the screen are cut out, and the result is measured
   against the spec before it goes in.

The full standard, with the numbers every phone must meet: [docs/PIPELINE.md](docs/PIPELINE.md).

## License and credits

Released under the [MIT License](LICENSE). Each phone's page lists the photos and spec sheets it was
made from.

<sub>Phone names, logos and designs are trademarks of their owners. KLAPKA is a fan project and is not
affiliated with or endorsed by any phone maker.</sub>
