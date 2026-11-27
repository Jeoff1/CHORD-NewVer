# Public page images: sources and licences

Images used by the public landing page (`apps/church/templates/church/landing.html`) and the
sign-up page (`apps/accounts/templates/accounts/signup.html`); the directory and church profiles
reuse the logos.
Rules ([[Design-System]], "Photography"): freely licensed or owned, sources recorded here, no
recognisable faces, no symbols that belong to one particular church, no logos or text.

## Replacing a photo

Save the new image under the **same file names** (a WebP and a JPEG fallback) and update its
entry below. The page needs no code change. Photos are decorative (empty alt text) and are
cropped by CSS (`object-fit: cover`), so any landscape image works; keep the main subject in
the right half of the hero photo. Suggested: 2400 px wide for the hero, 1800 px for the
rehearsal photo, about 200 KB as WebP (quality 80 to 85). The sign-up photo is the exception:
a portrait image (about 1600 by 2580, plus an 800 px wide WebP for phones), its subject a little
left of centre; the phone banner shows a strip just below the middle.

## Files

| File | Source | Creator | Licence | Edits |
| ---- | ------ | ------- | ------- | ----- |
| `hero-worship.webp`, `hero-worship.jpg` (960 by 640) | "Concert Stage", StockSnap: https://stocksnap.io/photo/concert-stage-P7JJ4LKNK8 | Marc-Antoine Dépelteau | CC0 1.0 (public domain): https://creativecommons.org/publicdomain/zero/1.0/ | Mirrored left to right; warmed toward amber; slight contrast |
| `rehearsal-ambient.webp`, `rehearsal-ambient.jpg` (1024 by 683) | "Free playing guitar image", rawpixel: https://www.rawpixel.com/image/5913957/image-public-domain-hand-wooden | Not named | CC0 1.0 (public domain): https://creativecommons.org/publicdomain/zero/1.0/ | The guitar maker's name on the body blurred out; warmed slightly |
| `signup-worship.webp`, `signup-worship.jpg` (1600 by 2580), `signup-worship-800.webp` (800 by 1290) | "Bearded guitar concert (Unsplash)", Wikimedia Commons: https://commons.wikimedia.org/wiki/File:Bearded_guitar_concert_(Unsplash).jpg; first published on Unsplash on 15 Mar 2017 (https://unsplash.com/photos/I7iOoLnpXfs), when Unsplash photos were CC0 | Austin Neill | CC0 1.0 (public domain): https://creativecommons.org/publicdomain/zero/1.0/ | From the 5472 by 3648 original: cropped to a portrait frame (a bottle on the stage table left out); the face softened into the stage haze so it is not recognisable; resized for the web (WebP quality 80, JPEG 78) |
| `chord-logo.webp`, `chord-logo.png` (760 by 304) | The CHORD logo, the owner's final artwork (27 Nov 2026) | CHORD project | The project's own | None to the design: empty transparent margin trimmed, resized for the web |
| `chord-logo-gold.webp`, `chord-logo-gold.png` (760 by 304) | The same logo, for green grounds (the owner's choice, 27 Nov 2026) | CHORD project | The project's own | Its two colours exchanged pixel by pixel (deep green and gold, the approved `#173630` and `#E5C690`); same shapes and transparency |

Licences checked on 27 Nov 2026 through each image's Openverse record (api.openverse.org),
which names the licence, creator and original page. The sign-up photo's licence was checked on
27 Nov 2026 on its Wikimedia Commons page (licence CC0, author and original Unsplash page named). CC0 needs no credit; the creators are
named here anyway.

The free copies are 960 and 1024 px wide. Higher-resolution originals (4896 and 5472 px)
can be downloaded from the source pages above and saved under the same names.
