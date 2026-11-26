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
| Icons | `templates/includes/icons/`: also chevron-right, chevron-up, chevron-down, lock and dots; for the landing page music-note, document, people, calendar, megaphone and check-circle; for the Directory x; for the church profile map-pin, phone, mail and globe | Icon-only buttons carry an `aria-label` and are at least 44px. On the landing page an icon takes its size from the text (`.chord-landing .chord-icon`) |
| Landing page | `church/landing.html`, its own `static/css/landing.css` (classes `lp-*`) and `church/static/church/landing.js` | The public front page, redesigned 26-27 Nov 2026: see "The landing page" below |
| Sign-up page | `accounts/signup.html`, its own `static/css/auth.css` (classes `au-*`) and `accounts/static/accounts/signup.js` | Create an account, redesigned 27 Nov 2026: see "The sign-up page" below |

## The landing page (redesign, 26-27 Nov 2026)

Approved by the UI/UX owner on 2026-11-27, subject to the lead developer's
approval; built on branch `joy-ui-ux-v2` ([[Design-Decisions]], A7,
"Landing page redesign"). Only `church/landing.html` loads `landing.css`
and `landing.js`, so nothing here reaches a signed-in page.

- **Sections:** a solid green nav that stays at the top (logo and links
  left; Sign in, outlined, and Sign up, gold, right; a Menu on phones);
  the hero, its photograph on the right fading into the green, the example
  lineup card hanging over its lower edge; How it works (the Phase 9C
  steps on one line); Features (an open 3 by 2 grid); Rehearsal (the
  chord sheet with the Listen card overlapping it); Who it's for (green,
  the hero photo faint behind); United in Worship (the church carousel);
  the gold call to action (Sign up); the footer.
- **Logo:** transparent, never on a plate
  (`church/includes/landing_logo.html`). On light grounds (the gold call to
  action) the owner's final artwork, unchanged
  (`static/images/landing/chord-logo.webp`, `.png` fallback). On green
  grounds (nav, intro, footer) its colour-swapped copy, `chord-logo-gold.*`
  (`variant="gold"`): gold letters and circle, deep-green triangle and
  church, the same shapes, made by exchanging the two colours pixel by
  pixel (the owner's choice, 2026-11-27).
- **Photography** (new kind of asset): freely licensed or owned, each
  source, creator, licence and edit recorded in
  `static/images/landing/SOURCES.md`; no recognisable faces and no symbol
  that belongs to one particular church (decision 0001); decorative, so
  `alt=""`. Fixed file names, so a photo is replaced without a code change.
- **Landing-only effects:** photo fades (green overlays), warm glows, soft
  shadows, gradient washes between sections, smooth scrolling, gentle hover
  lifts. All motion stops with `prefers-reduced-motion`.
- **Loading intro:** the logo, a seven-bar gold equalizer, "Bringing
  worship together" and a thin loading line on the green. Only on the first
  visit in a browser session (`sessionStorage`), never without JavaScript.
  It stays at least **0.8 s** (the owner's approved exception to "no
  deliberate delay", 2026-11-27; none with reduced motion), leaves on
  `load`, goes after 4 s at most (script) or 6 s (CSS). No sound.
- **United in Worship:** up to 12 churches that are public and finished
  setup, newest first (`views.showcase_churches`), in a native-scrolling
  carousel: three in view on desktop, two on tablet, one on a phone, with
  snapping and arrow buttons the script shows only when there is more to
  scroll. Name, address and logo only; each card opens the church's public
  page, and "Explore all churches" the directory.
- **Eyebrows** on light grounds use the chord-letter gold `#7A5A1E`; gold
  `#E5C690` on green and in dark mode. The footer is `#0B1F1B` (the link
  hover colour).
- **Wording** is the platform's neutral default Labels ([[0014-church-platform]]).

## The church directory (redesign, 27 Nov 2026)

Designed as an interactive mockup and approved by the UI/UX owner on
2026-11-27; built on branch `joy-ui-ux-v2`. `church/directory.html` loads
`landing.css` (tokens, nav, logo, buttons) and its own
`static/css/directory.css` (classes `dir-*`) and
`church/static/church/directory.js`; no other page loads them.

- **Nav:** the landing page's green nav with the gold logo, and **Back to
  Home** (chevron-left), a real link to `/` (the landing page for a
  visitor, the dashboard for a signed-in person); "Home" on narrow phones.
  The same look for visitors and signed-in people, who keep their account
  and their own light or dark choice.
- **Header:** "Discover Churches" and the search, side by side on wide
  screens, stacked below 900 px.
- **Search:** a wide rounded bar (search icon, field, an X to clear, the
  gold Search button), a gold outline on hover and while typing. It stays
  in place: no overlay, dimming or movement. Suggestions open directly
  beneath it, under the sticky nav: up to six, the typed text underlined in
  gold, then "See all results". Arrow keys, Enter and Escape work; a click
  elsewhere closes them.
- **Results:** "N churches", or "Back to all churches", "Search results for
  “…”" and "N churches found"; sort by Newest (default), Name A to Z or Z to
  A. Cards in rows of 4, 3, 2 and 1 (1200, 900 and 560 px), the same size,
  never stretched: the logo in a white circle on a warm gradient, or the
  fallback (the people icon in gold on green, as on the landing page); the
  name, the address and View church. Hover lifts the card and zooms the
  image. 24 to a page.
- **Loading:** a small gold spinner in the suggestions and beside the count
  while waiting; placeholder cards only when an update takes longer than
  0.2 s, so a quick answer never flickers. No added delay.
- **Icon added:** `x` (the search's clear button), solid like the rest.

## The church profile (redesign, 27 Nov 2026)

A public website for each listed church: the same page for visitors,
signed-in people and its own members, with no sign-in needed to view it.
Designed as an interactive mockup and approved by the UI/UX owner on
2026-11-27; built on branch `joy-ui-ux-v2`. `church/homepage.html` loads
`landing.css` and its own `static/css/profile.css` (classes `pf-*`) and
`church/static/church/profile.js`; no other page loads them.

- **Nav:** the gold logo (to `/`) and **Back to Churches** (the
  Directory); "Churches" on narrow phones.
- **Cover:** a rounded banner with the default green-and-gold gradient,
  no stock photos; a church's own banner image would go on `.pf-banner`
  later with no layout change. The church's logo (or the CHORD fallback,
  the people icon on green) in a circle overlapping its lower left.
- **Sidebar, the only place for the church's details:** name, About
  (clamped to five lines with Read more), then Contact: address (opens a
  map search), phone (`tel:`), email (`mailto:`) and website, each with
  its icon and only when filled in; then Upcoming services when the church
  switches them on. Sticky beside the main area on wide screens.
- **Main area, tabs** (ARIA tabs, arrow keys, Home and End; without
  JavaScript every section shows): **Announcements** (date badge, title,
  date, three lines with Read more, latest five, newest first; one panel
  with dividers; a note when there are none) and **Available services**
  (equal cards: calendar icon, name, description, usual length, the gold
  Request this service). A tab appears only while its Module is on.
- **Footer:** "Powered by CHORD".
- **Responsive:** sidebar 340 px, then 290 px below 960 px; one column
  below 760 px (cover, logo, sidebar, tabs, sections); tab icons drop
  below 480 px so the labels stay on one line.
- **Icons added:** `map-pin`, `phone`, `mail` and `globe` (the contact
  rows), solid like the rest.

## The sign-up page (redesign, 27 Nov 2026)

Create an account (`/accounts/signup/`) as a split screen. Designed as an
interactive mockup (v2 after review: a freely licensed photo, a compact
centred form, a short checklist) and approved by the UI/UX owner on
2026-11-27; built on branch `joy-ui-ux-v2`. `accounts/signup.html`
(standalone, with `accounts/includes/signup_field.html` for each field)
loads its own `static/css/auth.css` (classes `au-*`, every rule under
`body.au`) and `accounts/static/accounts/signup.js`; no other page loads
them. Same `SignUpView`, `SignUpForm`, CSRF protection and server-side
validation; no Google, Facebook or Apple sign-in.

- **Card:** one rounded container (28 px, a soft shadow; a border in dark
  mode) centred on the page background, at most 1200 px wide.
- **Photo panel (left, 48%):** the photograph
  (`images/landing/signup-worship.*`, see `SOURCES.md`) with a deep-green
  overlay, darker at the top for the gold logo (upper left, to `/`) and
  darkest at the bottom for **Bringing Worship Together** (Raleway 800,
  white) and the tagline. Decorative: `alt=""`. An 800 px WebP for phones,
  1600 px for wide screens, a JPEG fallback.
- **Form panel (right):** **Back to Home** (the new `arrow-left` icon) at
  its top right; then a centred column, 420 px at most: the **Sign Up /
  Sign In** toggle (a pill; the current one green with gold text, gold in
  dark mode; real links to the two routes), "Create an account" and the
  view's intro, the fields, the full-width gold **Create Account** button
  and "Already have an account? Sign in".
- **Fields:** labels above; 48 px inputs, 12 px corners, outlines
  `#6E8A83` (3.73:1 on white, the owner's choice for this page), a gold
  focus ring; icons inside Username (person), Email (mail) and both
  passwords (lock); First and Last name side by side above 480 px. Help
  text under each field; the server's errors under it in the danger
  colour (`id_<field>_error`, which Django's `aria-describedby` names),
  the form's own errors above the fields.
- **Password checklist:** Django's help list replaced by four short items
  in two rows under the field, keeping its id: 8 or more characters, Not
  only numbers, Unlike your name or email (the script ticks these as the
  person types) and Not a common password (dashed: only the server knows
  the list). They mirror `AUTH_PASSWORD_VALIDATORS`; the server still
  checks every rule. Under Confirm password, "Passwords match" or "don't
  match yet" while typing.
- **Show password:** an eye button in each password field (44 px,
  `aria-pressed`, "Show password" / "Hide password"), hidden until the
  script runs.
- **Wording** (approved): the username hint "Up to 150 letters, digits and
  @ . + - _", "Confirm password" and "Enter the same password again."
  (`SignUpForm`; the rules are Django's).
- **Light or dark:** the device's (only signed-out people see the page);
  the tokens of this note, with gold headings and links in dark mode.
- **Responsive:** below 992 px the card is 786 px at most and the photo
  42%; below 720 px the card stacks: Back to Home above it, a 184 px photo
  banner (logo and heading, no tagline), then the form; names one per row
  below 480 px. The page scrolls normally; nothing is clipped.
- **Motion:** input focus and button hover only (a 1 px lift); none with
  `prefers-reduced-motion`.
- **Icon added:** `arrow-left` (Back to Home here), solid like the rest.
  The directory and profile keep their chevron Back links.

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
