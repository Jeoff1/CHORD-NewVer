# UI/UX Master Plan

The UI/UX owner's approved plan for redesigning CHORD's screens, phase by
phase, on branch `joy-ui-ux-v3`. Read this, [[Animation-Plan]] and
[[Design-System]] before any UI/UX work. It sits under the project rules
in `AGENTS.md` and the numbered decisions; where it disagrees with
[[Design-Decisions]], flag it instead of choosing ([[00-Home]], "Agreed
design").

## Sources and how complete this note is

- **The approved interactive artifact (mockup):**
  `https://claude.ai/artifact/XjV7jeDC63if6mbVNw2q6t`. It is the visual
  source of truth for every phase: layouts, components, states and motion.
- **Not readable from Claude Code (28 Nov 2026):** the artifact read
  returned "not found, or not shared with this account" (it belongs to
  another account or organisation). So this note records everything that
  is known **outside** the artifact: the phase order, the rules, the
  approved revisions and what is already built. Sections marked
  **Awaiting the artifact** must be filled from it, screen by screen,
  before that phase is built. **Never invent a different redesign to fill
  a gap**: ask the UI/UX owner for the screen (a screenshot, an export of
  the artifact's HTML, or access for the signed-in account).
- Already-built designs are described in full in [[Design-System]]
  (landing, directory, church profile, sign-in, registration, welcome toast,
  sidebar and dashboard, tokens, account popover) and their reasons in
  [[Design-Decisions]].

## Design requirements that hold in every phase

These come from the approved designs already built and from `AGENTS.md`;
they bind every later phase.

- **One design system.** Colours, fonts, icons and tokens only from
  [[Design-System]] ("Tokens"): green `#173630`, deep green `#0B1F1B`,
  gold `#E5C690`, gold tint `#F3E6C9`, page `#E6E2E1`, surface `#FFFFFF`;
  dark mode page `#060F00`, surfaces `#0F241F` and `#173630`, headings gold.
  Raleway (600 to 800) for headings, Fira Sans Condensed for the rest; chords
  stay monospace. Solid icons from `templates/includes/icons/`.
- **Bootstrap stays the base** ([[0002-server-rendered-ui]]):
  server-rendered Django templates, small vanilla scripts, htmx where it is
  already used. No front-end framework, no build step.
- **Professional, not social.** CHORD is a church management system: no
  social-media patterns (profile pictures, bios, banners, likes, feeds).
- **Light and dark mode** on every screen, set before the page draws
  (`User.theme`, else the device). Both must pass contrast
  ([[Design-System]], "Contrast").
- **Responsive:** phone (below 576 px), tablet (768 to 1199 px, the sidebar
  icon-only), desktop (1200 px and up). Touch targets at least 44 px. No
  sideways scrolling.
- **Accessible:** real buttons and links, labelled icon-only controls,
  visible focus (a 3 px gold outline), keyboard paths for every menu and
  dialog (Escape closes, focus returns), `aria-live` for toasts, and every
  animation off under `prefers-reduced-motion` ([[Animation-Plan]]).
- **Configure behaviour, not identity** (decision 0001): no denomination
  anywhere; UI words for member, worship service, sermon, lineup and team
  come from the Labels helpers, never hard-coded.
- **Permissions, not role names.** What a person sees follows their
  permissions in the Current Church; menus show only what they may open.
- **Module switches:** a switched-off Module's screens and links vanish.
- **Preserve what works.** Each phase restyles and reorganises; it keeps
  every route, form field, permission, audit record and test unless the
  UI/UX owner and lead developer approve a change.

## Backend restrictions

- **No new model fields or migrations** without the lead developer's
  approval. When a phase's design needs one, **skip that feature, record it
  under the phase below as "Blocked: needs backend approval", and build the
  rest.**
- **Rejected by the lead developer (28 Nov 2026):** personal profile
  pictures (upload or display), About Me or bio, personal banners, the
  camera overlay on personal avatars, and the fields and migrations for
  them. Don't propose them again without the lead developer.
- **Awaiting the lead developer:** a private church's own page opening for
  the people who manage it (Phase 1; [[Design-Decisions]], "Signed-in
  website access and the Church CMS"). Everyone else keeps getting 404.
- The rules in `AGENTS.md` on Spotify, LRCLIB, Ultimate Guitar,
  OpenStreetMap and copyrighted lyrics hold for every screen: a redesign
  never adds a Spotify call, stores a new Spotify field, or shows lyrics
  outside the church's installation.
- Out of scope (`AGENTS.md`): giving and finance, records, ministries,
  events, per-person attendance, SMS. A mockup screen for one of these is
  not built; ask first.

## Phase breakdown

Status: **Done** (built, checked, committed), **Next**, **Not started**.

| Phase | Scope | Status |
|---|---|---|
| 1 | Signed-in website access and the Church CMS | Done (`02b00ea`) |
| 2 | Personal profile, simplified: account popover and Edit Profile | Done (`2d51a37`) |
| 3 | Shared UI Components | Next: awaiting the artifact |
| 4 | Management, Services and Bookings | Not started |
| 5 | Worship Planning, Song Recommendations and Lineup Builder | Not started |
| 6 | Songs, Song Pool, Find Songs, Chord Viewer, Chord Editor and Rehearsal | Not started |
| 7 | Calendar and Scheduling | Not started |
| 8 | Members and Teams | Not started |
| 9 | Announcements and Notifications | Not started |
| 10 | Settings and Reports | Not started |
| 11 | Final UI/UX Consistency, Responsiveness, Accessibility and Animation Audit | Not started |

### Phase 1: Signed-in website access and the Church CMS (done)

Built as approved; full detail in [[Design-Decisions]], "Signed-in website
access and the Church CMS", and [[Design-System]], "The church profile".
`/welcome/` is the landing page for everyone; the sidebar logo opens it;
the church panel opens the church's page; the people who manage a church
edit its page in place (cover and logo camera menus, Edit profile modal
with live preview, View as visitor). No migration.

### Phase 2: Personal profile, simplified (done)

The original plan (a profile picture, bio and two-column modal with a
hover-to-edit avatar) is **superseded**: the lead developer rejected the
fields. What was built and approved after the UI/UX owner's review
([[Design-Decisions]], "Personal profile"):

- One **account popover** on every signed-in page: initials avatar, full
  name (first, middle, last, suffix), role line, church card, a text-only
  centred **Edit Profile** button, the church switcher **only for people in
  more than one church**, the person's links, an **Appearance** switch
  (Light, Dark, Device) directly in the popover, **Account Settings** and
  **Sign Out**.
- **Edit Profile**: a dialog with only first name, middle name, last name
  and suffix, a live preview, background save, audit trail.
- **The official CHORD logo** is a link on every page that shows it:
  `/welcome/` when signed in (never the dashboard; the person stays signed
  in), the landing page at `/` for a guest, with a "Go to Homepage"
  tooltip. Church logos keep their own links.

### Phase 3: Shared UI Components

**Scope:** the pieces every later phase reuses, built once and used
everywhere: page header and actions, buttons, cards, tables and list
toolbars, filters and search, forms and fields (inline errors), status
pills and badges, tabs, modals and confirm dialogs, toasts, dropdown
menus, pagination, empty states, loading states (skeletons, spinners),
breadcrumbs or back links. Today's versions are listed in
[[Design-System]], "Page patterns" (`apps/core/templatetags/ui.py`,
`templates/includes/`), and the newer approved ones are the CMS modal and
toasts (`profile.css`), the account popover and dialog (`account.css`)
and the welcome toast.

**Awaiting the artifact:** the exact look of each component (sizes,
radii, shadows, spacing, states: hover, focus, active, disabled, loading,
error) and which existing patterns it replaces.

### Phase 4: Management, Services and Bookings

**Scope (current screens):** the sidebar's Management category: Services
(`worship:home`, `service_create`, `schedule_ahead`, `service`,
`service_update`, `template_list` and its forms, `attendance`) and
Bookings, the on-screen name of the Occasions Module (`occasions:home`,
`list`, `create`, `detail`, `update`, `requests`, `request`, `decide`,
`withdraw`, and the public `my_requests`).

**Awaiting the artifact:** list, detail and form layouts; the request
review flow; status and action placement.

### Phase 5: Worship Planning, Song Recommendations and Lineup Builder

**Scope:** guided service planning (Phase 9C: the four steps Theme, Praise
Team, Song Lineup, Confirm, and the next-step panel), the theme page
(`worship:theme`, sermon PDF, scripture suggestions), suggestions
(`suggest`, `suggestions`, feel and not-worship feedback) and the lineup
(`lineup` and its add, swap, regenerate, confirm, send back, reopen and
save-to-Spotify actions). The lineup comes first and suggestions assist
(decision 0015). The pastor's decision is final, as a permission. Team
members see a lineup only once confirmed.

**Awaiting the artifact:** the step layout, the lineup builder
(drag and drop or buttons), suggestion cards, the confirm rundown.

### Phase 6: Songs, Song Pool, Find Songs, Chord Viewer, Chord Editor and Rehearsal

**Scope:** the Song Pool (`songs:list`, `detail`, `update`, check again),
Find Songs (`spotify_search`, `spotify_add`), the chord sheet viewer and
editor (`chordsheet`, approve, discard; ChordPro, pasted in by people,
never scraped), transposing and keys, the Spotify player card, and
rehearsal views of a confirmed lineup. Lyrics stay inside the church's
installation; no Recommendations, Audio Features or Audio Analysis calls.

**Awaiting the artifact:** pool table or cards, the search flow, the
viewer (chords over lyrics, key controls), the editor, the rehearsal
screen.

### Phase 7: Calendar and Scheduling

**Scope:** the calendar (`worship:calendar`: services and bookings on one
calendar), My schedule (`teams:my_schedule`), availability and blackout
dates, replies to assignments.

**Awaiting the artifact:** month, week or list views, event chips,
day details.

### Phase 8: Members and Teams

**Scope:** Users (`accounts:user_list`, create, add existing, update,
history, set password, remove), Roles and permissions (`role_list`,
`permission_matrix`), the Audit log (`audit:log`), the Team roster
(`teams:roster`, assign, remove, swap requests, parts). The Member
Directory is **retired** (`settings.RETIRED_MODULES`): a church's people
are its Users, under Members in the sidebar. Don't bring it back.

**Awaiting the artifact:** the people list, the person page, the roster
grid, the permission matrix.

### Phase 9: Announcements and Notifications

**Scope:** announcements to the whole team or one service team
(`announcements:list`, `create`, `archive`) and notifications
(`notifications:list`, open, read all; the header bell and count).

**Awaiting the artifact:** the announcement list and composer, the
notification list and any bell dropdown.

### Phase 10: Settings and Reports

**Scope:** the Settings hub (`church:settings` sections, Modules,
Personal: Account and Appearance, Worship and Teams settings, the Spotify
and suggestion settings) and Reports (`worship:reports`, song usage,
attendance as a headcount per service; Phase 9A member reports when built).

**Awaiting the artifact:** the hub layout, settings forms, report tables
and charts.

### Phase 11: Final UI/UX Consistency, Responsiveness, Accessibility and Animation Audit

Every screen checked against this note, [[Design-System]] and
[[Animation-Plan]]: one component per job, the same spacing and type, light
and dark mode, phone, tablet and desktop widths with no sideways scroll,
keyboard paths and focus, labels and contrast, `prefers-reduced-motion`,
error and empty states. Fix what is found; record what is left.

## Implementation workflow

The UI/UX owner's current workflow (28 Nov 2026):

1. Work only on `joy-ui-ux-v3`. Before starting, check the branch and
   whether `master` has new commits; report any, never merge on your own.
2. One phase at a time, in the order above, following the artifact and
   [[Animation-Plan]]. Preserve every approved design and existing
   behaviour.
3. Run `.\scripts\check.ps1 -Quick` after each change and the full
   `.\scripts\check.ps1` (with coverage) when the phase is done; it must
   pass. Report real results.
4. Update the vault in the same phase: a dated entry at the top of
   [[Development-Log]], the module notes affected, [[Design-System]] for
   new patterns, [[Design-Decisions]] for approved changes, this note's
   phase table, and [[00-Home]].
5. Make **one local commit per phase** (the pre-commit hook runs the full
   check; never `--no-verify`). **Never push to GitHub** until the UI/UX
   owner's final review.
6. Continue to the next phase without waiting for approval. Stop only for
   critical errors, significant design deviations, required backend
   decisions, or when every phase is done.
7. A feature that needs unapproved backend changes is skipped and
   documented under its phase; the rest of the phase goes ahead.
8. If the session stops (limits or interruption), keep the commits and
   write in [[Development-Log]] exactly where work stopped.
