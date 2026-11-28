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
| Section tabs | `{% section_tabs links as tabs %}{% include "includes/section_tabs.html" with tabs=tabs label=… %}` | Tabs within a page only (since 28 Nov 2026 no Module has a tab bar of its sections: the sidebar holds them); the current tab (the longest link the page's path starts with) gets the gold underline and `aria-current` |
| Status pill | `{% include "includes/status_pill.html" with status=… %}` | draft, confirmed, none, cancelled, occasion, pending, accepted, declined; optional `pill_text` |
| Cards | `.card` with `.chord-card-head` (a Raleway `.card-title`, and a count or link on the right) | Content blocks |
| Two columns | `.chord-columns` holding `.chord-main` and `.chord-side` | Main content and a side column; they stack on a phone |
| Settings hub | Each app registers `SettingsPage`s in `apps/core/settings_menu.py`; `base.html` shows the hub on their pages. Every category is always shown (no dropdowns); the side menu scrolls on its own when it is taller than the window, stays in view beside the page on a wide screen, and opens scrolled to the current page | One place for every setting |
| Dashboard | Each Module registers sources in `apps/church/dashboard.py` | "Needs your attention", "Coming up" and side cards |
| Icons | `templates/includes/icons/`: also chevron-right, chevron-up, chevron-down, lock and dots; for the landing page music-note, document, people, calendar, megaphone and check-circle; for the Directory x; for the church profile map-pin, phone, mail and globe | Icon-only buttons carry an `aria-label` and are at least 44px. On the landing page an icon takes its size from the text (`.chord-landing .chord-icon`) |
| Landing page | `church/landing.html`, its own `static/css/landing.css` (classes `lp-*`) and `church/static/church/landing.js` | The public front page, redesigned 26-27 Nov 2026: see "The landing page" below |
| Sign-in page | `accounts/auth_base.html` (with `login.html`), its own `static/css/auth.css` (classes `au-*`) and `accounts/static/accounts/auth.js` | Sign in, full-page, redesigned 27 Nov 2026: see "The sign-in page" below. Signing up is registering a church |
| Church registration | `church/register.html`, `auth.css` with its own `static/css/register.css` and `church/static/church/register.js` | Register your church as a four-step wizard, 27 Nov 2026: see "Registering a church" below |

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

- **Nav:** the gold logo (to `/`) and, signed in, the account menu (as on
  the landing page). Since 28 Nov 2026 **Back to Churches** is a round
  back-arrow button above the cover, on the left, with a "Back to
  Churches" tooltip (`.pf-back`, `data-tip`).
- **Header (28 Nov 2026, Facebook-style):** the logo circle
  (`--pf-logo`, 150 px, 112 px on phones) overlaps the cover's lower left;
  the name (and CHORD's "Church" eyebrow) sits beside it in `.pf-head`,
  with **Edit profile** on the right for the people who manage the
  church; less space below the cover. On phones the logo and name centre.
- **Cover:** a rounded banner with the default green-and-gold gradient,
  no stock photos. Since 27 Nov 2026 a church's own banner, when it has
  one (`.pf-banner--image`): the cover takes the banner's 3:1 shape, at
  most 360 px tall, and the image fills it (`object-fit: cover`, never
  stretched), without the texture lines. The church's logo (or the CHORD
  fallback, the people icon on green) in a circle overlapping its lower
  left either way.
- **Sidebar, the only place for the church's details:** About
  (clamped to five lines with Read more; the name moved to the header on
  28 Nov 2026), then Contact: address (opens a
  map search), phone (`tel:`) and email (`mailto:`), each with
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
  rows), solid like the rest; on 28 Nov 2026 `camera`, `pencil`, `upload`
  and `arrow-up-right`.
- **Editing tools (Church CMS, 28 Nov 2026),** only for the people who
  manage the church: a pale admin bar ("You manage this page", View as
  visitor); a camera button on the cover and a camera badge on the logo,
  each opening a small menu (Upload, Remove) and showing the required size;
  a picture shows at once with an "Uploading…" overlay while it is sent;
  the **Edit profile** modal (`.pf-modal`): a preview card (cover, logo,
  name, live while typing), then fieldsets Church information, Contact and
  Public page, with Cancel and a Save button that spins while saving, and
  an inline "Discard your changes?" prompt. Messages appear as toasts at
  the top (`.pf-toast`, a timer bar, gone after 5 s or on dismiss). Motion
  follows the Animation Plan (150–250 ms) and stops under
  `prefers-reduced-motion`.
- **Account menu (landing and profile, 28 Nov 2026):** initials button,
  a menu card (name, role line, Dashboard, My Church, Sign Out) that fades
  and slides in (160 ms), closes on outside click or Escape and moves with
  the arrow keys; a sheet anchored under the nav on phones
  (`.lp-acct*` in `landing.css`).

## The sign-in page (redesign, 27 Nov 2026)

Sign in (`/accounts/login/`) as a full-page split. Designed as interactive
mockups and approved by the UI/UX owner on 2026-11-27 (a card version
first, then the full-page version with the church registration wizard);
built on branch `joy-ui-ux-v2`. **There is no separate sign-up page**
(owner, 27 Nov 2026): signing up for CHORD is registering a church, whose
first step makes the person's account ("Registering a church", below);
the old address `/accounts/signup/` redirects there, keeping its query
string. Since 28 Nov 2026 a visitor can also make an account in the
sign-up pop-up of a public service request ([[Occasions]]).

- **Files:** `accounts/auth_base.html` holds the page (head, photo, Back to
  Home, heading, messages; blocks `title`, `description`, `photo_title`,
  `photo_tagline`, `col_class`, `heading`, `intro`, `form`, `after`);
  `login.html` extends it.
  `accounts/includes/auth_field.html` draws each field (also on the
  registration page), `accounts/includes/auth_submit.html` the main
  button. They load their own `static/css/auth.css` (classes `au-*`, every
  rule under `body.au`) and `accounts/static/accounts/auth.js`; no other
  page loads them.
- **Unchanged behind them:** Django's `LoginView` and
  `AuthenticationForm`, CSRF protection,
  server-side validation, `next` and the redirects; no Google, Facebook or
  Apple sign-in.
- **Layout:** two equal halves filling the window, with no card. The
  photograph (`images/landing/signup-worship.*`, see `SOURCES.md`) fills
  the left half edge to edge and stays in place while the form scrolls,
  under a deep-green overlay: the gold logo upper left (to `/`), the
  heading in gold and the tagline at the bottom. Decorative: `alt=""`. The
  form sits in the middle of the right half, 420 px wide at most, with
  **Back to Home** (an outlined pill
  with the `arrow-left` icon) at its top right.
- **Sign in:** "Bringing Worship Together" and the tagline on the photo;
  "Welcome Back" and "Sign in to continue to CHORD"; **Email or
  username** (person icon) and Password (lock icon, Show button); **Forgot your password?**
  right under the password field; the green **Sign In** button; "Don't
  have an account? **Sign up**", which opens Register your church. No
  Sign Up / Sign In toggle.
- **Fields:** labels above; 48 px inputs, 12 px corners, outlines
  `#6E8A83` (3.73:1 on white, the owner's choice for these pages), a gold
  focus ring; "Optional" beside the label of an optional field. Help text
  under each field; the server's errors under it in the danger colour
  (`id_<field>_error`, which Django's `aria-describedby` names); the
  form's own errors above the fields in a box with the `alert-circle`
  icon (`role="alert"`): on sign-in, Django's "Please enter a correct
  username and password…", the username kept and the password never sent
  back.
- **Show password:** the word **Show** (then **Hide**) inside each password
  field (44 px, `aria-pressed`, read as "Show password"), hidden until the
  script runs; a shown password is hidden again before sending, so
  password managers save it. Field names and `autocomplete` stay Django's.
- **Password checklist** (the registration wizard's account step): Django's help list
  replaced by four short items, keeping its id: 8 or more characters, Not
  only numbers, Unlike your name or email (ticked as the person types) and
  Not a common password (dashed: only the server knows the list). Under
  Confirm password, "Passwords match" or "don't match yet".
- **Buttons:** pills, 48 px; the main one green with gold text (gold with
  dark text in dark mode); while sending, a spinner and "Signing in…" /
  "Creating account…", disabled and `aria-busy`, so a second press or
  Enter does nothing. No delay is added; Back makes it usable again.
- **Light or dark:** the device's (only signed-out people see these
  pages); gold headings and links in dark mode.
- **Responsive:** below 992 px the photo takes 42%; below 720 px it becomes
  a 230 px banner above the form, with a light **Home** pill on it in place
  of Back to Home; names one per row below 480 px.
- **Motion:** input focus and button hover (a 1 px lift); the spinner; a
  fade between the two pages through the browser's page transitions, the
  photo held still (Chrome, Edge and Safari; Firefox switches at once).
  None of it with `prefers-reduced-motion`.
- **Icons added:** `arrow-left` and `alert-circle`, solid like the rest; `image` (the banner's drop area, 27 Nov 2026).

## Registering a church (redesign, 27 Nov 2026)

Register your church (`/churches/register/`) as a four-step wizard on one
page, approved with the full-page sign-in; since 27 Nov 2026 it is CHORD's
only sign-up (the landing page's Sign up and the sign-in page's Sign up
open it, and `/accounts/signup/` redirects to it). `church/register.html`
loads `auth.css` (tokens, fields, buttons), its own `static/css/register.css`
and `church/static/church/register.js`, then `auth.js`.

- **One form, sent once.** The four steps are sections of one form;
  `RegisterChurchView` checks everything when it is sent and comes back on
  the first step with an error, in the steps' order (`data-au-start`), with every step open in
  the stepper. Without the script every step shows at once, with Complete
  registration at the end.
- **Layout:** a green header (gold logo; "Already have an account? Sign
  in" for visitors; Back to Home); the stepper down the left on green
  ("Register your church", "Four short steps. Nothing is saved until you
  complete the registration.", the four steps with their icons, and for
  visitors "Already have an account? **Sign in** and your church is added
  to it"); on the right a progress bar ("Step 2 of 4 · Church
  information", 50%), the step, and Previous / Cancel / Step x of 4 / Next
  pinned to the bottom. The last step's button is the gold **Complete
  registration**, with a spinner and "Registering…" while sending.
- **Steps** (in this order since 27 Nov 2026, the owner's choice: the church first, the account last before review):
  1. **Church information:** Church name (the only field needed), address,
     contact number and church email, all optional.
  2. **Church profile:** logo ("512 × 512 px recommended (1:1). PNG,
     JPEG, GIF or WebP, 2 MB at most.", with a preview and Remove); the
     **banner** (below); description (2000 characters, with a count) and
     Public visibility as two cards: **Public** (listed in the directory,
     the default) or **Not public**.
  3. **Account information:** for a visitor, First name and Last name side
     by side, Middle name and Suffix (both optional) below them at every
     width, Email address ("You sign in with it, and reset your
     password."), Password with the checklist and Confirm password
     (`SignUpForm`). No username: the person signs in with the email.
     Signed in: their own account (initials, name, email, and the username
     when it isn't the email) and "Not you? Sign out".
  4. **Review and confirm:** the account, the church information and a
     preview of the public profile, each with **Edit**.
- **Checking each step:** Next (or Enter) checks the step first: the
  first and last name, a valid email, the password's length, not only
  numbers, the two passwords the same, the church's name, the church
  email, the logo's size. Errors show under the field and the first one
  takes the focus. The server checks everything again.
- **The stepper:** the current step gold, finished steps ticked; any step
  reached can be opened again. Each step's heading takes the focus when it
  opens. On a phone the stepper runs across the top, under the header.
- **The banner** (owner, 27 Nov 2026; optional): a wide 3:1 drop area
  between the logo and the description, on the green-and-gold cover with
  the `image` icon, "Drag an image here or choose one below", and below it
  Choose image (then Replace image), Remove and the hint "1920 × 640 px
  recommended (3:1). JPG, PNG or WebP, 5 MB at most."
  - **Choosing or dropping** an image shows it at once, filling the area
    without stretching, with its name, size and pixel size, and a note
    when it isn't 3:1 or is under 1200 px wide.
  - **Refused at once:** another type ("Choose a JPG, PNG or WebP image.")
    or more than 5 MB, with the size.
  - **Between steps** the file stays in the form, and the review's profile
    preview shows it as the cover.
  - **On the server** (`images.BannerFieldMixin`): the type, size, real
    format and pixel count are checked again. A WebP copy is saved (turned
    upright, hidden details left out, at most 1920 px wide, never enlarged
    or cropped) as `church/banner/<random>.webp`.
  - **After a correction** from the server the page asks for the banner
    again, as for the logo.
- **Not in it:** the public address in the preview (the server chooses the
  slug) and the "registered" screen of the mockup. Since 27 Nov 2026 a
  registered church goes straight to its dashboard, set up, with the
  welcome toast (below); no second setup wizard.
- **Responsive:** below 992 px a 250 px stepper without hints and one
  column of fields; below 720 px the stepper across the top and Cancel and
  the step count hidden from the bottom bar.
- **Motion:** each step slides in 18 px and fades (from the left when
  going back), the progress bar grows; none with `prefers-reduced-motion`.

## The welcome toast (27 Nov 2026)

Shown once on the dashboard after registering a church
(`templates/includes/welcome_toast.html`, styles at the end of
`static/css/chord.css`, `static/js/welcome-toast.js`). It's a Django
message tagged `chord-welcome`; `base.html` shows it right after the
navigation bar and leaves it out of the usual alerts. Django never shows a
message twice, so a refresh or a later sign-in doesn't bring it back.

- **Look:** deep green (`#173630`) with a thin gold border (`#2E4A44` in
  dark mode); a gold circle with a green check; "Welcome to CHORD!" in
  Raleway gold; the message in light text; an X (44 px, "Dismiss the
  welcome message"); a 3 px gold countdown bar along the bottom. At most
  560 px wide, centred 12 px under the navigation bar; on phones the full
  width less 12 px each side.
- **Behaviour:** slides down 14 px and fades in; closes itself after five
  seconds (the bar shrinks over that time). Hovering or focusing it
  pauses it; the X or Escape closes it. It fades out as it goes.
- **Never in the way:** not a modal. The region under the navigation bar
  lets clicks through, so the dashboard stays usable around it.
  `role="status"` and `aria-live="polite"`.
- **Reduced motion:** no slide, fade or countdown animation; it still
  closes after five seconds.

## The app sidebar and dashboard (redesign, 27 Nov 2026)

Every signed-in page with a church: `templates/base.html` with
`includes/app_sidebar.html` and `includes/app_header.html`,
`static/css/sidebar.css` and `apps/church/static/church/sidebar.js`; the
menu is built by `apps/church/navigation.py`. Other pages keep the plain
top bar.

- **Sidebar:** `#173630` (`#0B1F1B` in dark mode), the gold CHORD logo
  (`church/includes/landing_logo.html` with `variant="gold"`, unchanged),
  then the church panel: the church's own logo or initials on gold, its
  name in Raleway, and the role line. Since 28 Nov 2026 the logo opens the
  landing page (a "Go to Homepage" tooltip on hover or focus), and the
  panel is a link to the church's page with a small gold "View page ↗"
  under the role line whenever that page can be opened (otherwise a plain
  panel). Links in `#E6E2E1`, sub-links in
  `#A9BDB7`; the current page gold with a 4 px gold bar at the left edge.
  Categories open with a chevron (Bootstrap collapse); Management has two
  nested groups. Settings and Sign Out sit at the foot.
- **Icon-only:** 80 px wide from 768 px, by the button beside the logo;
  each category becomes a dropdown (fixed position, over the page). The
  logo shows whole at 56 px.
- **It remembers:** the mode and the open categories and groups (cookies
  the server reads, so the page arrives drawn that way) and the menu's
  scroll position (session storage). A thin scrollbar (6 px) that brightens
  on hover; collapse animations are off with reduced motion.
- **Phones (below 768 px):** a Bootstrap offcanvas panel, opened by the
  menu button in the header (focus, Escape and the backdrop are
  Bootstrap's).
- **Header:** sticky, white (the raised surface in dark mode): the
  category (when there is one) and current page, the bell with the unread
  count, the account menu (only the letter on phones). The church's name
  is only in the sidebar's panel.
- **Dashboard** (`static/css/dashboard.css`): the greeting, then the date
  and a one-line summary; four figure cards (four in a row, two on
  tablets, one below 400 px) with an icon, the number in Raleway 800 and
  the dates under it; smaller figures as pills; then Action required
  (a gold rule beside each item, one button), Upcoming (compact cards: a
  64 px date block, green for services and gold for bookings, the name,
  time and theme, status pills, a chevron; the whole card is the link),
  the lineup status bar (confirmed `#2F7D5B`, draft gold, none `#C9C2BF`,
  a one-line legend), and a side column of Create (record-making
  shortcuts only), My schedule and Announcements, each with one link in
  its header.

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
