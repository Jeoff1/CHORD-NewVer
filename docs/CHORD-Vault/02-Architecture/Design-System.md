# Design System

The owner's design system, given on 2026-11-25 (Phase 9A, A7, part 2;
[[Design-Decisions]], "Adviser comments, 24 Nov", A7). Every screen reuses
these pieces; don't add colours, fonts or icons outside them.

## Where it lives

| Piece | File |
| ----- | ---- |
| Tokens, Bootstrap overrides, fonts, the player card | `static/css/chord.css`, loaded in `templates/base.html` right after Bootstrap |
| Fonts | `static/vendor/fonts/`: Raleway (one variable file, 600 to 800) and Fira Sans Condensed (400, 500, 600, 700), Latin and Latin Extended, with `OFL-Raleway.txt` and `OFL-FiraSansCondensed.txt` (SIL Open Font License) |
| Icons | `templates/includes/icons/<name>.html`: search, gear, eye, eye-off, person, play, pause, plus chevron-left, back-10 and forward-10. Solid, `fill="currentColor"`, `aria-hidden="true"`; optional `size` (px, 20 by default): `{% include "includes/icons/play.html" with size=24 %}` |
| Back link | `templates/includes/back_link.html` with `url`, `label` and an optional `detail` (shown after a comma): a pill at least 44px tall with a chevron |
| Profile letter | `base.html`: `.chord-avatar`, the first letter of the full name (else the username), gold on green, `aria-hidden`; the name shows beside it |
| Light or dark mode | `base.html`: a few lines of script in `<head>` set `data-bs-theme` before the stylesheets load, so nothing flashes: the person's own choice (`User.theme`: Settings › Personal › Appearance, also in the user menu), else the device's (`prefers-color-scheme`). Signed out, the device's |

Bootstrap stays the base ([[0002-server-rendered-ui]]): `chord.css` only
sets its CSS variables and a few classes. `--bs-body-bg` is the **surface**
(cards, inputs, tables, dropdowns read it); the page behind them is
`--chord-page`, on `body`.

## Page patterns (A7 part 3)

| Pattern | Where | Use |
| ------- | ----- | --- |
| Page header | `{% load ui %}{% page_header title subtitle=… %}…{% endpage_header %}` (`apps/core/templatetags/ui.py`, `includes/page_header.html`) | The heading left, the actions right. One primary button (`btn-primary`) per page |
| More | `{% more_menu %}<li>…</li>{% endmore_menu %}` | Every other page action, each behind its own permission; an empty menu doesn't render |
| Section tabs | `{% section_tabs links as tabs %}{% include "includes/section_tabs.html" with tabs=tabs label=… %}` | A Module's sections; the current one (the longest link the page's path starts with) gets the gold underline and `aria-current` |
| Status pill | `{% include "includes/status_pill.html" with status=… %}` | draft, confirmed, none, cancelled, occasion, pending, accepted, declined; optional `pill_text` |
| Cards | `.card` with `.chord-card-head` (a Raleway `.card-title`, and a count or link on the right) | Content blocks |
| Two columns | `.chord-columns` holding `.chord-main` and `.chord-side` | Main content and a side column; they stack on a phone |
| Settings hub | Each app registers `SettingsPage`s in `apps/core/settings_menu.py`; `base.html` shows the hub on their pages. Every category is always shown (no dropdowns); the side menu scrolls on its own when it is taller than the window, stays in view beside the page on a wide screen, and opens scrolled to the current page | One place for every setting |
| Dashboard | Each Module registers sources in `apps/church/dashboard.py` | "Needs your attention", "Coming up" and side cards |
| Icons | `templates/includes/icons/`: also chevron-right, chevron-up, chevron-down, lock and dots; for the landing page music-note, document, people, calendar, megaphone and check-circle | Icon-only buttons carry an `aria-label` and are at least 44px |
| Landing page | `church/landing.html`, `.chord-landing*` in `chord.css` | The public front page. Green hero and footer, gold call to action, pill buttons; the example lineup card is light in both modes. Wording from Labels, features only for switched-on Modules |

## Tokens

**Light mode (default)**

| Token | Value | Use |
|---|---|---|
| Page background | `#E6E2E1` | `body` |
| Surface | `#FFFFFF` | cards, navbar, tables, inputs |
| Text | `#173630` | body text and headings |
| Secondary text | `#4A5E59` | muted text (`--bs-secondary-color`) |
| Border | `#D3CDC9` | cards, dividers |
| Strong border | `#9FA7A2` | outline buttons, inputs |
| Primary | `#173630`, text on it `#E5C690` | `.btn-primary`, active states |
| Accent (gold) | `#E5C690` | highlights; never as text on white |
| Accent tint | `#F3E6C9` | current page in menus, selected rows, outline-button hover |
| Link | `#173630`, hover `#0B1F1B`, underlined | links |
| Chord letters | `#7A5A1E` | chord names in the sheet viewer (`--chord-chord-letter`) |
| Tertiary surface | `#F4F1F0` | `bg-body-tertiary` boxes (chosen here) |

**Dark mode**

| Token | Value |
|---|---|
| Page background | `#060F00` |
| Surface | `#0F241F` (cards), `#173630` (raised: navbar, dropdowns, modals, `bg-body-tertiary`) |
| Text | `#E6E2E1` |
| Headings and accent | `#E5C690` |
| Secondary text | `#B9C4BF` |
| Border | `#2E4A44` |
| Strong border | `#6E8A83` (chosen here; the owner gave none for dark) |
| Primary | background `#E5C690`, text `#060F00` |
| Chord letters | `#E5C690` |

Status colours stay Bootstrap's, at shades that pass: `.text-success` and
`.text-danger` use `#146C43` and `#B02A37` in light mode, `#75B798` and
`#EA868F` in dark; `.text-bg-primary` has dark text in dark mode, where
primary is gold.

**Type:** Raleway (600 to 800) for headings, the navbar brand and card
titles; Fira Sans Condensed for everything else (`--bs-body-font-family`).
The chord sheet's chords stay monospace, so they line up over the lyrics.

## The Spotify player card

`apps/songs/templates/songs/includes/player.html` and
`apps/songs/static/songs/player.js`; styles under `.chord-player` in
`chord.css`. A rounded card on green `#173630` in both modes, headed
"Listen" (Raleway, gold) with a small uppercase "Spotify". Three states:

1. **Full playback in the browser** (`playback.use_sdk`): a 64px cover (from
   the SDK in the browser only, never sent to CHORD or stored), the title
   and artist from CHORD's Song, a progress bar (gold on `#2E4A44`,
   `role="progressbar"`) with the elapsed and total time (the stored length
   until the SDK reports one), and back 10 seconds, a 56px gold play/pause
   button and forward 10 seconds. Progress updates about once a second
   while playing, and stops when paused or when the page is hidden. On any
   SDK failure the controls hide and Spotify's embedded player shows inside
   the card.
2. **Embedded player** (not connected): Spotify's iframe inside the card,
   "Open in Spotify" and, when connections are set up, "Connect your
   Spotify account".
3. **No playback** (the song has no Spotify track): a muted play icon, "No
   playback for this song" and why. No link to fix it: CHORD has no page
   that links an existing song to a track.

Touch targets are at least 44px; with `prefers-reduced-motion` the
progress bar doesn't animate.

## Contrast

Every text pair is at least 4.5:1 (checked 2026-11-25):

| Mode | Text on background | Ratio |
|---|---|---|
| Light | Text `#173630` on surface `#FFFFFF` | 13.07 |
| Light | Text on page `#E6E2E1` | 10.16 |
| Light | Text on accent tint `#F3E6C9` | 10.56 |
| Light | Text on tertiary `#F4F1F0` | 11.63 |
| Light | Secondary `#4A5E59` on surface | 6.92 |
| Light | Secondary on page | 5.38 |
| Light | Secondary on accent tint | 5.59 |
| Light | Secondary on tertiary | 6.15 |
| Light | Primary button `#E5C690` on `#173630` | 7.97 |
| Light | Primary button hover `#E5C690` on `#0B1F1B` | 10.45 |
| Light | Chord letters `#7A5A1E` on surface | 6.35 |
| Light | `.text-success` `#146C43` / `.text-danger` `#B02A37` on surface | 6.45 / 6.50 |
| Dark | Text `#E6E2E1` on card `#0F241F` | 12.64 |
| Dark | Text on page `#060F00` | 15.18 |
| Dark | Text on raised `#173630` | 10.16 |
| Dark | Gold `#E5C690` on card / page / raised | 9.91 / 11.91 / 7.97 |
| Dark | Secondary `#B9C4BF` on card / raised / page | 9.06 / 7.29 / 10.88 |
| Dark | Primary button `#060F00` on `#E5C690` | 11.91 |
| Dark | Text on selected `#2E4A44` | 7.49 |
| Dark | `.text-success` `#75B798` / `.text-danger` `#EA868F` on card | 6.95 / 6.43 |
| Card | Gold "Listen", links and play icon background on `#173630` | 7.97 |
| Card | Title `#FFFFFF` on `#173630` | 13.07 |
| Card | Artist, times, labels `#C9C3BF` on `#173630` | 7.49 |
| Card | Text `#E6E2E1` on `#173630` | 10.16 |
| Card | Play icon `#173630` on gold | 7.97 |
| Badges | White on Bootstrap success / danger / secondary | 4.53 / 4.53 / 4.69 |
| Badges | Black on Bootstrap warning / info | 12.88 / 10.72 |
| Alerts | Bootstrap's alert text on its own background, light and dark | 7.15 to 10.82 |

Shapes, not text (3:1 needed): the card's progress fill on its track,
5.88; the muted play icon `#9FB3AD` on `#2E4A44`, 4.37; the dark-mode strong
border `#6E8A83` on cards, 4.35. **The light-mode strong border `#9FA7A2`
reaches only 2.46:1 on white**, below 3:1 for input and button outlines;
`#6E8A83` (3.73:1) would pass. It is used as given until the owner decides.
