# UI/UX Master Plan

The UI/UX owner's approved plan for redesigning CHORD's screens, phase by
phase, on branch `joy-ui-ux-v3`. It preserves the detailed requirements
of the UI/UX owner's handoff ("CHORD — Complete UI/UX Development Handoff
and Continuation Plan", with its "Current instructions" of 28 Nov 2026), so
any session or coding assistant can continue without the original
conversation. Read it with [[Animation-Plan]] and [[Design-System]] before
any UI/UX work.

It sits under the project rules in `AGENTS.md` and the numbered decisions;
where it disagrees with [[Design-Decisions]], flag it instead of choosing.

## 0. Sources, and what is documented versus seen

- **Written plan (authoritative):** the handoff above, given in full by the
  UI/UX owner on 28 Nov 2026. Its "Current instructions" supersede its
  older historical parts where they conflict (notably Phase 2 and the Git
  rules, both recorded below as they now stand).
- **Approved interactive artifact (visual reference):**
  `https://claude.ai/artifact/XjV7jeDC63if6mbVNw2q6t`. **It could not be
  opened from Claude Code** (it belongs to another account); nobody working
  from this note has inspected it. The UI/UX owner authorised building from
  this written plan and the existing design system instead (28 Nov 2026).
  Where the plan describes a layout, follow it; where only the artifact
  would show an exact visual detail, reuse the established baseline
  ([[Design-System]]) rather than inventing a new look, and note it as
  "not checked against the artifact". Some artifact screens predate the
  lead developer's latest changes: adapt them to current functionality.
- **Visual baseline:** every design already built and approved
  ([[Design-System]]: landing, directory, church profile and CMS, sign-in,
  registration, welcome toast, sidebar and dashboard, account popover).

## 1. Project background

CHORD is a church management and worship planning web application. The
UI/UX owner designs; the lead developer owns backend functionality, forms,
database architecture and business logic. Goal: make the whole system
modern, professional, responsive, interactive, accessible and visually
consistent, **continuing** the existing redesign, never restarting it.

- Repository `Jeoff1/CHORD-NewVer`, branch `joy-ui-ux-v3`; local site
  `http://127.0.0.1:8000/`.
- Phase 1 committed and pushed (`02b00ea`); Phase 2 committed locally
  (`2d51a37`, 1,487 tests, 97% coverage); plan checkpoint `391af18`.

## 2. Preserve existing work

Treat all implemented and approved designs as the baseline. Don't restart
the redesign, replace approved layouts with generic templates, restore
removed functionality, rewrite working components without need, replace
working functionality with mock data, discard changes, or modify `master`.
Don't assume a design is built because a document or the artifact shows it:
distinguish built from planned.

## 3. Technology

Keep Django, PostgreSQL, Bootstrap 5.3.3, HTMX, Django templates, HTML,
CSS and vanilla JavaScript ([[0002-server-rendered-ui]]). No React, Vue,
Tailwind, Node.js or other frameworks without approval; if the artifact
uses one, it is a visual reference only, translated into the existing
architecture. Reuse local dependencies and assets.

## 4. Global design system

### Colours

| Element | Colour |
|---|---|
| Primary deep green | `#173630` |
| Primary warm gold | `#E5C690` |
| Dark background | `#060F00` |
| Dark surface | `#0F241F` |
| Light background | `#E6E2E1` |
| Light surface | `#FFFFFF` |
| Input border | `#6E8A83` |

Reuse the CSS variables and tokens in [[Design-System]] ("Tokens"). Don't
change global styling without need or replace the dark surface. Keep
semantic colours for success, warning, error, information, destructive
actions and record statuses. **Don't make everything green or gold.**

### Typography

Raleway for headings, titles and prominent numbers; Fira Sans Condensed for
body text, forms, labels, descriptions and navigation. Consistent sizes,
weights, line heights, hierarchy and spacing.

### Branding

The official CHORD logo, in its proportions and approved variants (gold on
green, the original on light grounds); never a generic music icon. Keep
CHORD branding distinct from church logos.

### Visual direction

Modern, professional, warm and welcoming, organised, functional,
consistent, responsive, accessible. Comfortable spacing, consistent radii,
subtle borders, appropriate shadows, clear hierarchy, smooth animation,
purposeful icons. Avoid excessive cards, nested containers, repeated
headings, repeated navigation, unnecessary buttons, excessive whitespace
and distracting animation. **Professional, not social:** no social-media
patterns.

## 5. Completed Phase 1 (preserve; don't redo)

- **Signed-in landing page:** `/welcome/` for everyone; `/` stays the
  dashboard signed in. The original landing design (hero, headline,
  sections, carousel) and the guest experience are unchanged. Signed in:
  no hero buttons (Go to Dashboard, Explore Churches) and no "Signed in
  as" indicator; the account popover instead (Phase 2). The pillar reads
  "Your modules — Switch on what you use"; never restore "Your wording —
  Set by your church".
- **Sidebar:** the CHORD logo opens the landing page without signing out,
  with a "Go to Homepage" tooltip; no View Website link; the church
  identity panel opens the church's public page with a small "View page"
  mark; no dropdown or editing modal on that panel.
- **Church CMS** (Facebook-inspired public church page): compact back
  arrow above the banner, wide cover, logo overlapping the banner's lower
  left, the name beside it, church information, announcements, available
  services, upcoming services; no large gap under the banner. Managers get
  hover-to-edit camera controls on logo (512 × 512 px) and cover
  (1920 × 640 px): upload, replace, remove, immediate preview, real upload
  feedback, validation, gradient and initials fallbacks. The editor modal
  with live preview: name, About, address with the OpenStreetMap location
  picker, phone, email, the public-page switches, Save Changes, Cancel,
  validation errors, unsaved-changes prompt. **No Website, Currency or
  Time zone.** View as visitor, toasts, server-side authorisation, audit
  log, POST-only `church:profile_edit`.
- **Pending (lead developer):** church managers may preview their own
  private church page; everyone else (team members included) gets 404.
  Don't broaden access; if rejected, restore the earlier rule and keep the
  rest of the CMS.
- No new model fields or migrations; one endpoint (`church:profile_edit`),
  one route (`/welcome/`).

## 6. The lead developer's latest updates (preserve)

- **Praise Team:** every church has its own (parts, profiles, blackout
  dates); churches registered after Phase 9B get the Praise Team planning
  step; the Praise Team switch sits under Worship on the Modules page and
  is respected.
- **Service scheduling:** a new worship service fills in the template's
  next usual day and time.
- **Location picker** (registration, Church details, CMS): Use My Current
  Location, Pick on the Map, the tile-access fix; only the address text is
  saved.
- **Date and time:** separate date and time inputs with calendar and clock
  icons; a date needs a time (validation); never silently midnight; style
  the existing inputs consistently.
- **Removed, don't restore:** Sermon Series (Theme form, theme card,
  settings), the Labels page, custom terminology, Website, Currency, Time
  zone, the Website link on the public page, the Member Directory,
  Households. Stored data and hidden module code stay; don't delete it.
- **Members sidebar:** Users, Roles and Permissions, Audit Log; not in
  Settings.
- **Public service request sign-up:** a visitor fills in a public church's
  service request; a modal makes their account (name, email, password); a
  six-digit emailed code verifies it; the account is created and signed
  in, the request sent, and they join that church as a Church Member.
  Existing accounts sign in in the same modal. Requests to other churches
  don't join them. Churches that accept only their own members' requests
  ask visitors to sign in first. Security unchanged: hashed codes, 10-minute
  expiry, at most 5 wrong attempts, 60-second resend cooldown, at most 5
  codes per address per hour, email failure handling, backend validation.
  UI: clean sign-up modal, existing-account sign-in, clear verification,
  six-digit entry, accessible resend countdown, real loading, validation
  and email errors, success feedback; the request survives moving between
  steps; no artificial delays or misleading progress.

## 7. Phase 2: Personal profile (done; supersedes the original plan)

The historical plan (Discord-inspired popover with a profile picture,
username and bio; a two-column Edit Profile with a hover-to-edit avatar)
is **superseded**. The lead developer **rejected personal profile
pictures, bios and banners**: no fields, uploads or migrations for them,
ever, without the lead developer. Built and approved (`2d51a37`;
[[Design-Decisions]], "Personal profile"):

- Initials-only account popover on every signed-in page: initials, full
  name, role, church, a text-only centred Edit Profile, the church switcher
  only for people in more than one church, the person's links, a direct
  Light / Dark / Device selector, Account Settings, Sign Out.
- Edit Profile: the existing name fields (first, middle, last, suffix) with
  a live preview, background save, audit trail.
- Every official CHORD logo links to the landing page (`/welcome/` signed
  in, `/` for guests) with "Go to Homepage"; the landing footer's
  scroll-to-top is acceptable. Church logos and CMS editing intact.
- Password and sensitive settings stay in Account Settings.

## 8. Phase 3: Shared UI components

Reusable styling and consistent interactions across the system.

- **Buttons:** primary (gold background, deep-green text where
  appropriate), secondary (outlined or muted surface), destructive (danger).
  Consistent sizes, icons, spacing, hover, focus and disabled states.
- **Forms:** visible labels, consistent input heights, related fields
  grouped, existing fields and behaviour preserved, errors under the field,
  entered values kept after errors, accessible uploads, the separate date
  and time controls and the location picker preserved.
- **Tables:** clean headings, consistent row spacing, subtle dividers,
  search and filters where supported, sorting where appropriate,
  pagination, status indicators, compact record actions, responsive.
- **Cards:** consistent padding, surfaces, subtle borders, hierarchy,
  clickable where appropriate, no excessive nesting.
- **Search:** search icon, clear button, accessible focus, real loading
  feedback, empty-result messages, reset filters where appropriate.
- **Modals:** heading, description, Save/Confirm/Cancel, Escape, focus
  management, destructive confirmation, mobile behaviour.
- **Notifications (toasts):** branded; success, warning and error variants
  with icons; manual dismissal; accessible announcements.
- **Empty states:** icon, concise explanation, relevant action, no fake
  records.
- **Page headers:** title, brief description when needed, the relevant
  primary action, optional breadcrumbs on deeper pages; no navigation
  repeated from the sidebar.

## 9. Dashboard and navigation consistency

Preserve the built dashboard; never replace it with a simplified artifact
dashboard. Real data and existing periods only: greeting, date, upcoming
worship services, pending service requests, confirmed lineups, song pool
count, active members where permitted, personal assignments, upcoming
bookings, Action Required, Upcoming Services and Events, latest
announcements, personal schedule. No invented statistics or percentage
changes. Upcoming events: compact horizontal cards (date and time, title,
status, destination, subtle chevron).

Sidebar: persistent, collapsible, categories and nested groups, active
page, remembered scroll, mobile off-canvas, CHORD logo, church panel,
Settings and Sign Out at the foot; the real navigation tree and
permissions. Request a Service and My Requests stay out of the regular
administrator sidebar; eligible members keep theirs.

## 10. Phase 4: Management — Services and Bookings

- **Service requests:** searchable table, existing status filters,
  requester, service type, requested date, status, compact actions, summary
  counts when available.
- **Request details:** summary, requester, service information,
  requirements, attachments, approve and reject, status history (as they
  exist).
- **All bookings:** searchable list, date and service-type filters,
  status, existing create actions, clickable records.
- **Book a service:** existing forms in clear related sections; every
  field, separate date and time, validation, business rules and
  requirements preserved.
- **Booking details:** summary, schedule, authorised contact information,
  status, management actions.
- No payment systems or duplicate workflows; coordinate with the lead
  developer before changing shared backend forms. (Bookings are the
  on-screen name of the Occasions Module; fees and requirements beyond what
  exists are out of scope.)

## 11. Phase 5: Worship planning, song recommendations and lineup builder

The core feature; give it particular attention.

- **Worship services page:** upcoming and past services, search and
  filters as they exist, date and time, theme, planning status, actions.
- **Service details:** service information, theme, scripture, Praise
  Team, lineup, planning status. No Sermon Series.
- **Guided planning:** Theme → Praise Team → Song Lineup → Confirm, with
  module settings and workflow restrictions respected.
- **Theme:** organised Bible book, chapter and verse controls, the chosen
  scripture shown, theme information organised, validation kept.
- **Praise Team:** roles and assignments organised, assigned and
  unassigned clearly distinct, availability, module switch, scheduling and
  blackout rules kept.
- **Confirm:** a complete review (theme, scripture, team when applicable,
  final lineup) and the existing confirmation and saving logic.
- **Lineup builder (desktop):** side by side: left, recommendations with
  search and filters, artwork, title, artist, available recommendation
  information, Add; right, the lineup with count, order, remove,
  reordering, Review Lineup. Above: the service, theme, scripture and the
  stepper. On mobile, stacked.
- **Processing:** a subtle music-inspired loading animation (waveform or
  dots, or the branded indicator), skeleton song cards, accurate wording
  such as "Finding songs for your worship theme…". No artificial delays,
  no fake progress percentages.
- **Results:** staggered reveal, available artwork, title, artist,
  existing recommendation information and supported explanations; scores
  only if the engine gives meaningful ones; no invented match percentages.
- **Selecting:** Add turns into an Added check; the song slides into the
  lineup; the count updates; a brief highlight; duplicates prevented by the
  existing rules. **Removing:** collapse or fade, Add restored, count
  updated. **Reordering:** existing ordering, smooth transitions,
  accessible controls. **Preview:** metadata, Spotify link or controls,
  chord sheet, explanation, without leaving the workflow where possible.
- Preserve the recommendation algorithm, Spotify integration, song pool
  restrictions, chord sheets, permissions, empty-pool handling and
  validation. No new playback features or engine changes without approval.
  The lineup comes first and suggestions assist (decision 0015); the
  pastor's decision is final, as a permission; team members see a lineup
  only once confirmed.

## 12. Phase 6: Songs, chord sheets and rehearsal

Modern music-app inspiration with CHORD branding.

- **Song pool:** searchable library, artwork, title, artist, metadata,
  chord sheet availability, actions, supported filters and sorting.
- **Find songs:** Spotify-inspired discovery: clear search, organised
  results, existing Spotify metadata, Add to Song Pool, loading and empty
  states.
- **Song details:** artwork, title, artist, metadata, chord sheets,
  editing actions.
- **Chord sheet viewer:** readability first: lyrics and chords, chord
  symbols distinct, comfortable width, existing transposition and
  rehearsal controls, minimal distraction.
- **Chord sheet editor:** spacious editing area, organised controls,
  existing preview, clear saving feedback, format and validation kept.
- **Rehearsal:** the chord sheet as the focus, the existing player, lineup
  navigation, accessible controls, layouts for musicians, minimal motion
  while reading.
- Spotify configuration and worship-check settings stay in Settings.
  Never call Spotify Recommendations, Audio Features or Audio Analysis;
  lyrics only from LRCLIB and only inside the church's installation.

## 13. Phase 7: Calendar and scheduling

- **Calendar:** worship services, bookings, assignments and relevant
  events with meaningful colours, existing date navigation, supported
  views and filters, event details, responsive. Nothing unsupported.
- **Team roster:** by service and role, assigned members, unassigned roles
  clear, scheduling rules, availability and blackout dates kept.
- **My schedule:** chronological (date, time, service, role, status,
  existing reply and swap actions).

## 14. Phase 8: Members and teams

A professional personnel layout. Members holds only Users, Roles and
Permissions and Audit Log.

- **Users:** searchable table, initials avatar, full name, role, account
  status, permitted actions.
- **Roles and permissions:** clear categories, organised existing
  controls, a matrix or grouped layout, actual permission names and rules,
  no new permissions.
- **Audit log:** chronological, timestamps, action descriptions, the
  authorised user, existing search, filters and details.
- Privacy and permission restrictions kept. No Member Directory or
  Households.

## 15. Phase 9: Announcements and notifications

- **Announcements:** a clean church news feed: title, date, content,
  existing images or attachments, author where supported, visibility;
  create, edit, archive and visibility as they exist. Private announcements
  never on public church pages.
- **Notifications:** the existing system made consistent: a popover from
  the bell, unread count, read and unread states, icons, timestamps, record
  links, Mark as Read, Mark All as Read where supported. No duplicate
  notification system.

## 16. Phase 10: Settings and reports

- **Settings:** centralised; organise the actual settings (church profile,
  personal account, services, worship, songs and Spotify, teams, modules,
  appearance, others that exist). The Praise Team switch stays under
  Worship on Modules. Don't restore Labels, Sermon Series, Website,
  Currency, Time zone or hidden member modules. Clear category navigation,
  consistent forms, save controls, validation, success messages.
- **Reports:** clear headings, existing date filters, actual statistics,
  charts or tables, existing export, loading and empty states. No invented
  metrics.

## 17. Phase 11: Final UI/UX audit

Review the whole application: visual consistency, typography, colour,
icons, forms, tables, navigation, responsiveness, light and dark mode,
accessibility, performance, animation, loading and empty states, error
pages, permissions and functionality. Remove duplicate navigation tabs,
repeated buttons, repeated church names, repeated contact information,
repeated settings shortcuts, prototype explanation cards, hard-coded sample
statistics and placeholder documentation shown to users. Keep essential
record actions and workflow navigation.

## 18. Design research

Before redesigning a major module, inspect the existing page and compare
suitable references where they can be reached (Mobbin, Dribbble, Behance,
SaaSFrame, Land-book, Facebook, Discord, Spotify, modern SaaS and church
management apps) to improve hierarchy, navigation, layout, forms, tables,
cards, modals, interactions, animation, responsiveness and accessibility.
Adapt, never copy branding or functionality. If a reference can't be
reached, say so instead of claiming it was inspected. The artifact stays
the primary reference.

## 19. Responsive design and accessibility

- **Desktop:** persistent sidebar, organised content, comfortable spacing,
  multi-column where appropriate.
- **Tablet:** adjustable (icon-only) sidebar, fewer columns, sensible form
  widths, responsive tables.
- **Mobile:** off-canvas navigation, stacked layouts, touch targets of at
  least 44 px, responsive modals and editing actions, no page-level
  sideways scroll (tables may scroll inside their own box), nothing that
  needs hover.
- **Accessibility:** meaningful labels and accessible names, keyboard
  navigation, visible focus, contrast, modal focus management, Escape,
  accessible errors, reduced motion, statuses that don't rely on colour
  alone.

## 20. Backend safety and restrictions

Preserve models, forms, field names and values, form methods and actions,
CSRF, HTMX requests, template variables, routes, authentication,
authorisation, validation, church data isolation, module restrictions,
business logic, records, environment configuration and uploaded media. Never
paste artifact code over working templates; when a design conflicts with a
backend requirement, adapt the design.

Before any new model field, migration, table, authentication or permission
change, significant endpoint or business logic: explain the feature, the
limitation, the backend change, conflicts and a recommendation, and wait for
approval. **In the continuous run (28 Nov 2026), skip such a feature,
record it under its phase in this note as "Blocked: needs backend
approval", and continue with the rest.** Personal profile picture, bio and
banner fields are rejected.

`AGENTS.md` rules hold on every screen: Spotify supplies candidates and
playback only and its data never reaches a model; store only the allowed
Spotify fields; no Recommendations, Audio Features or Audio Analysis calls;
lyrics only from LRCLIB; no Ultimate Guitar scraping; OpenStreetMap only
in the browser on the person's action; copyrighted lyrics and chord sheets
stay inside the installation. Out of scope: giving and finance, records,
ministries, events, per-person attendance, SMS.

## 21. Implementation workflow (current, 28 Nov 2026)

1. Work only on `joy-ui-ux-v3`. Verify the Git state first; report new
   `master` commits, never pull, merge, rebase, reset or touch `master`.
2. One phase at a time in this order; never several at once.
3. Before each phase: inspect the existing pages, the design system and
   the available functionality; note conflicts and unsupported items.
4. Run `.\scripts\check.ps1 -Quick` after changes and the full
   `.\scripts\check.ps1` (with coverage) at the end of the phase; fix
   errors and regressions; report real results; never run two test runs on
   the same test database at once.
5. Update the vault: [[Development-Log]] (dated entry with checks), the
   module notes, [[Design-System]] for new patterns, [[Design-Decisions]]
   for approved changes, the phase table below, [[00-Home]]. Prototype
   explanations go in the docs, never in the interface.
6. **A separate commit per phase** after the checks pass (the pre-commit
   hook runs the full check; never `--no-verify`), then **push it with
   exactly `git push origin joy-ui-ux-v3`** and verify the push (the UI/UX
   owner's instruction of 28 Nov 2026, superseding the earlier no-push
   rule). Before every commit and push, check the branch is `joy-ui-ux-v3`.
   Never commit to, push to or merge into `master`, never force-push, no
   pull requests: only the lead developer merges into `master`. If the
   branch is wrong or a push is rejected, stop and tell the UI/UX owner.
7. Continue to the next phase without per-phase approval. Stop only for a
   critical error, a substantial design deviation, or a backend or
   security decision. Skip and document blocked backend features.
8. If `origin/master` gets new commits, report the synchronisation
   concern before continuing; never merge it on your own.
9. After Phase 11: showcase the whole running site (desktop, mobile, light,
   dark, interactions, animations) for the final review. Report honestly
   if browser verification isn't available.
10. Work efficiently: reuse components, don't redo approved designs, keep
   reports short, document progress before a session ends; if interrupted,
   inspect the state first and record where work stopped.

## 22. Phase status

| Phase | Scope | Status |
|---|---|---|
| 1 | Church CMS and public navigation | Done, pushed (`02b00ea`) |
| 2 | Personal profile (simplified) | Done, pushed (`2d51a37`) |
| 3 | Shared UI components | Done |
| 4 | Management: Services and Bookings | Done |
| 5 | Worship planning, recommendations, lineup builder | Done |
| 6 | Songs, chord sheets and rehearsal | Done |
| 7 | Calendar and scheduling | Done |
| 8 | Members and teams | Done |
| 9 | Announcements and notifications | Done |
| 10 | Settings and reports | Not started |
| 11 | Final UI/UX audit | Not started |

### Blocked: needs backend approval

- **Album artwork (Phases 5 and 6).** CHORD stores only a track's ID,
  title, artist, album and length, plus its own playlist IDs (`AGENTS.md`,
  decision 0010); cover art reaches the browser only inside the Spotify
  player. Showing artwork in the song pool, Find Songs or suggestions would
  need a new stored field or new Spotify calls: a policy and backend
  decision for the owner and lead developer. Meanwhile songs show a branded
  tile with their initial (`.chord-art`).

### Flagged conflicts (resolved by source order, not by preference)

- **Lineup builder sides (Phase 5).** §11 puts recommendations on the
  left and the lineup on the right. Decision 0015 ("the lineup comes
  first; suggestions assist", a numbered decision, which outranks this
  plan) and the built Song Lineup page put the lineup first, on the left,
  with suggestions beside it on the right. Kept as built; the UI/UX owner
  may ask to swap the columns (a template change only).
- **Add → Added and drag and drop (Phase 5).** Adding a song and moving it
  are server actions that reload the page, so "Added" appears as the "In
  the lineup" pill (with a check that pops) after the server confirms, the
  button shows the busy spinner meanwhile, and reordering keeps the up and
  down buttons (accessible; no drag and drop without a new endpoint). No
  invented scores or match percentages; the worker's real progress bar
  stays.
