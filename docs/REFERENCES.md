# Choosing photos

A phone needs two kinds of photo; one photo can serve both.

- **Appearance photo** (the second image of pass 1): any reasonable photo of the phone. It does not
  have to be frontal; the template sets the geometry.
- **Geometry photo**: the most frontal photo available, used only to measure where the screen,
  keypad and seams sit (and the open length of sliders and flips).

Photos are input only: the image model redraws the phone from them, and the photos themselves stay
out of the published repo (`refs/` is not published). **Any photo that shows the phone well can be
used, whatever its licence** (Koks, 2026-11-08): press shots, shop photos, reviews, video frames.
**Look first at the Mobile Phone Museum** (mobilephonemuseum.com, Koks 2026-11-11: it has nearly every
model, photographed well). Each catalogued unit has its own page, `/phone-detail/<slug>` (slugs vary:
`sony-ericsson-k750i`, `c510`; the catalogue search runs in the browser), with straight-on studio
shots on a transparent background: front, open, back, sides. The images are
`static-mpm-optimized.s3.eu-west-2.amazonaws.com/<uuid>_large.png` (400 x 600); swap `_large` for
`_xlarge` for 800 x 1200 (`_thumbnail` is small). Open flips lie on their backs, so the lid is
raised toward the camera: wider at the top than at the hinge and about 6% short (Z600: display
1.16 tall per wide on the museum shot, 1.23 on a photo held square). Measure the open length on the
base, which lies flat, and correct the lid. Museum units can carry an inventory sticker (Z600:
"PTX-528" on the speaker pad) or an operator logo (Z1010: orange): paint them out. The site says
"all content is © Mobile Phone Museum Limited ... All rights reserved" (licences via
licensing@mobilephonemuseum.com). Under the rule above that is no bar to using a shot as input; credit
it in `build.json` like any other photo.
Other good places to look: Wikimedia Commons, GSMArena picture pages, LPC Wiki (lpcwiki.miraheze.org), shop listings (Ceneo and the like).
Straight-on press renders, best for both roles: gsm.magazyn.pl (`/pic/b/<brand>-<model>.jpg` and the
gallery `/pic_gallery/b/<brand>-<model>_NNN.jpg`), newmobile.com phone pages (Sony Ericsson press
sets: `front_straight`, `front_slided_open`), esato.com (`/gfx/phones/sonyericsson<model>.jpg`, about
200 x 450, sharper than gsm.magazyn.pl but cropped tight, sometimes through the phone's edge), mobilephonefeatures.com
(`view_b` images, also CDMA models), Xataka Movil galleries (`xatakamovil.com/galeria/sony-ericsson-<model>`:
official press sets such as `front_open`, up to 768 px tall), shop and archive listings (esfr.pl, imimg.com). GSMArena now answers
automated clients with a paywall; specs also come from teltarif.de, devicebeast.com and phonescoop.com.
GSMArena's mobile pages (`m.gsmarena.com/<phone>-pictures-<id>.php`) still list the image URLs, and
its image server answers; the file names do not always follow the model (`se-xperia-pureness-1.jpg`).
When an esato render is cropped tight, add a white margin before `photo`.
Watch for reflections under press renders: they are not part of the phone. When no press render of
the open phone exists, a review photo of an original unit works (mobile-review.com reviews show most
phones open); paint out the site's watermark first.
Record where it came from in `build.json` (`photo`) anyway, so the phone can be made again.

Pick the appearance photo in this order:

1. **Factory configuration.** The phone as it left the box: original badges and caps (K700i:
   "QuickShare"), no operator stickers or logos, no aftermarket covers, no plugs, caps or straps
   sticking out, no protective film. A sharper photo of a modified unit loses to a softer photo of an
   original one. A model sold only through one operator with that operator's print on it (Sony
   Ericsson F500i, vodafone) keeps the print: that is its factory configuration.
2. **Sliders, flips and swivels photographed open** (keypad flips over a touchscreen: closed), the way the skin
   shows them.
3. **Whole front visible**, labels and logos large and readable (the text pass fixes what is not,
   but readable text means fewer fixes).
4. **Resolution and sharpness.**
