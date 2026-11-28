# Animation Plan

How CHORD moves: the UI/UX owner's approved animation and microinteraction
plan (the handoff of 28 Nov 2026, Part F), with the motion already built
and approved. Applies to every screen redesigned on `joy-ui-ux-v3`
([[UI-UX-Master-Plan]]).

**Sources:** the written plan (authoritative) and the built baseline,
measured from the stylesheets. The approved artifact
(`https://claude.ai/artifact/XjV7jeDC63if6mbVNw2q6t`) could not be opened
from Claude Code, so nothing here was checked against it.

## 1. Direction

Purposeful motion that improves feedback, navigation, loading, content
transitions, workflow progress and understanding. Polished and interactive,
never slow or distracting. Don't animate elements for decoration.

## 2. Timing standards

| Interaction | Duration |
|---|---|
| Button press and input feedback | 100–150 ms |
| Hover effects | 150–200 ms |
| Camera overlay | 150–200 ms |
| Dropdowns and popovers | 150–250 ms |
| Sidebar transitions | 200–300 ms |
| Modals | 200–350 ms |
| Planning step transitions | 200–350 ms |
| Song addition and removal | 150–250 ms |
| Song reordering | 150–250 ms |
| Staggered reveal | 40–80 ms between items |
| Toast entrance and dismissal | 200–300 ms |

Natural easing (the built standard: entrances `cubic-bezier(.2, .8, .2, 1)`,
state changes `ease`, long reveals `cubic-bezier(.2, .7, .2, 1)`, spinners
and countdowns `linear`). No exaggerated bouncing, needless rotation or slow
animation. Guidelines, adjustable for usability. Exits faster than entrances.

## 3. Technical requirements

- Prefer CSS transitions and keyframes, Bootstrap transitions, SVG
  animation, minimal vanilla JavaScript and HTMX lifecycle events
  (`htmx:beforeRequest`, `htmx:afterSwap`…). No animation libraries (no
  Framer Motion, no GSAP).
- **Performance:** `transform` and `opacity`; minimal layout shift and
  repaint; no artificial loading delays; loading indicators stop when the
  request finishes; don't replay entrance animations on every HTMX update
  or navigation; clean up listeners and states; fine on low-end devices.
- **Accessibility:** `prefers-reduced-motion` turns every animation and
  transition off (timed behaviour still happens without movement, such as
  a toast closing after 5 s); visible focus; keyboard paths; mobile
  alternatives to hover; never information by motion alone; no flashing;
  no distracting continuous animation.
- Animations never interfere with authentication, authorisation,
  validation, database operations, workflow rules or server-confirmed
  state: a status changes on screen only after the server confirms it.

## 4. Built and approved motions (the baseline)

| Motion | Spec | Where |
|---|---|---|
| Hover and focus | `.15s`–`.2s ease` on colour, border, shadow; buttons lift 1 px; press scales to `.97` (`.12s`) | everywhere |
| Card hover | lift 2–4 px, stronger shadow, `.2s`–`.25s`; directory covers zoom slightly | landing, directory, dashboard |
| Menu or popover | fade and slide 6 px (scale `.98`→1), `.2s cubic-bezier(.2,.8,.2,1)`; close `.15s` | account popover, CMS camera menus, public menus |
| Chevron | rotates 180° in `.2s`–`.22s` | account button, sidebar, landing menu |
| Menu item hover | tint `.16s`, nudge right .15 rem | account popover |
| Modal | backdrop fades `.26s`; dialog rises 12 px, scale `.97`→1, `.26s`; close `.16s` | Edit Profile, CMS editor |
| Sheet on phones | slides up from the bottom | Edit Profile below 576 px |
| Close button | rotates 90° on hover or focus | Edit Profile |
| Inline error | fades `.2s`; field error shakes 3 px once (`.32s`) | CMS editor, Edit Profile |
| Busy button | "Saving…" and a 1 em spinner (`.7s`–`.8s linear`) | CMS editor, Edit Profile, sign-in |
| Value changed | pop to scale 1.1 at 40 %, `.32s` | Edit Profile initials |
| Segmented switch | thumb slides `.26s` | Appearance selector |
| Theme change | colours cross-fade `.3s` (`chord-theme-fade`) | Appearance selector |
| Toast | slide 12 px and fade `.28s`; out `.2s`–`.25s`; 3 px gold countdown bar over 5 s; hover or focus pauses | CMS toasts, welcome toast, account toast |
| Tooltip | fade and rise 2 px `.18s`, hover (pointer devices) or focus | "Go to Homepage", back arrow |
| Wizard step | slides 18 px and fades (from the left going back); progress bar grows | registration |
| Sidebar | Bootstrap collapse; icon-only switch; remembered state | app sidebar |
| Landing reveal | sections rise 18 px and fade `.6s`–`.95s` | landing |
| Landing intro | first visit per browser session only; at least 0.8 s (approved exception), leaves by 4 s, fails safe at 6 s; never without JavaScript | landing |

## 4b. Audit (UI/UX Phase 11, 28 Nov 2026)

Checked across `components.css`, `planning.css` and `account.css`: every
redesign stylesheet ends with a `prefers-reduced-motion` block (tested);
movement uses `transform` and `opacity`; durations sit in the standards
above (hover 150–200 ms, dropdowns 180–200 ms, modals 240–260 ms, toasts
280 ms in and 200–220 ms out, staggers 60 ms). Two loops exist and only
while something real is happening: the suggestions waveform (while a run
works) and spinners (while a request is in flight). Entrance animations run
once per page: list staggers, the calendar month, the error page; the
dashboard's figures count up once per browser session only. Nothing
animates around a chord sheet being read.

## 5. Per-area plan

- **Public website:** keep the landing animations (scroll fade-ins, image
  hover, carousel, nav hover indicators, button feedback) and the branded
  intro, not replayed on ordinary navigation. **Directory:** smooth result
  transitions, real search loading, gentle card elevation, subtle empty
  state; don't re-animate the whole directory for minor changes.
- **Sign in:** subtle entrance, input focus, password-visibility feedback,
  real button loading, validation transitions. **Registration:** animated
  progress bar, step transitions, completed-step checks, image previews,
  upload feedback, real submission loading, messages; entered data kept.
- **Sidebar and navigation:** smooth expand and collapse, nested
  dropdowns, chevron rotation, active-page transition, hover, off-canvas,
  account popover; state preserved; no flicker or re-render.
- **Dashboard:** a subtle initial KPI count-up where appropriate (real
  numbers only, not replayed on every visit), chart reveal from real data,
  event card elevation, smooth Action Required updates, loading and empty
  transitions.
- **Church CMS:** camera and pencil overlays fade in, image replacement
  previews, real upload progress, modal fade and scale, dismissal, live
  preview transitions, saving feedback, toasts, validation; editing
  reachable without hover.
- **Personal profile:** popover slide, fade and chevron; hover; smooth
  dismissal; into Edit Profile naturally; modal open and close, live
  preview, real saving, toast. No picture or banner animation (rejected).
- **Shared components:** buttons (hover, press, loading, success,
  disabled); forms (focus borders, validation, saving); tables (row hover,
  filter transitions, loading, status updates after the server confirms);
  cards (elevation or border, selection); dropdowns (fade and slide,
  chevron, selected state); loading (branded spinner, skeletons, content
  reveal, real upload progress); empty states (subtle appearance,
  explanation, action).
- **Public service request and verification:** modal transitions into
  verification, code-entry focus, invalid-code feedback, an accurate resend
  countdown, real loading, email-error feedback, a success check, a
  submission toast. Security unchanged; no fake timers.
- **Management:** filtering and search transitions, real loading
  skeletons, clickable row hover, status change after server confirmation,
  details expansion, busy buttons, toasts.
- **Worship planning:** animated stepper, progress transitions, completed
  checks, short fade or slide between steps, selection feedback,
  confirmation transition, real processing feedback; entered data and
  validation untouched.
- **Song recommendations:** processing (music-inspired waveform or dots,
  skeleton cards, an accurate message); results (staggered reveal, artwork
  hover, selected highlight, filter transitions, expandable explanations);
  adding (Add → Added check, smooth insertion, brief highlight, count);
  removing (fade or collapse, Add restored, count); reordering (position
  transitions, handle feedback, accessible controls); preview (detail
  reveal, Spotify control feedback, chord sheet expansion); confirmation
  (review transition, completion check, toast after the real save).
- **Songs and rehearsal:** result transitions, artwork hover, real
  retrieval loading, selection, editor preview transitions, playback
  feedback, lineup navigation; no continuous animation near a chord sheet
  being read.
- **Calendar:** date and view transitions, event hover, event popovers,
  assignment feedback, real loading.
- **Members and teams:** row hover, detail transitions and expansion, role
  change feedback, real saving.
- **Announcements and notifications:** card reveal, content expansion,
  image hover, publishing feedback, notification popover, read and unread
  transitions, dismissal. **Toasts:** slide and fade, dismissal, semantic
  icons, close button, countdown where appropriate. The five-second
  "Welcome to CHORD" toast after registration stays and is never replayed
  on ordinary sign-in.
- **Settings and reports:** category transitions, input focus, real
  saving, success messages, chart reveal from real data, filter
  transitions, detail expansion.
