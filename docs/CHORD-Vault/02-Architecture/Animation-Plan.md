# Animation Plan

How CHORD moves: the UI/UX owner's approved motion rules for every screen
redesigned on `joy-ui-ux-v3` ([[UI-UX-Master-Plan]]). Motion explains a
change (something opened, saved, moved or failed); it is never decoration
for its own sake, and it never delays someone doing their work.

## Sources and how complete this note is

- **The approved interactive artifact** (`https://claude.ai/artifact/XjV7jeDC63if6mbVNw2q6t`)
  holds the animation plan as approved. It could not be read from Claude
  Code on 28 Nov 2026 (not shared with this account), so the values below
  are the ones **already approved and built** (Phases 1 and 2, the
  landing, directory, church profile, sign-in, registration, welcome toast,
  sidebar and dashboard), measured from the stylesheets. They are binding.
  **Awaiting the artifact:** any per-screen motion the artifact specifies
  for Phases 3 to 11 that isn't covered here; add it under "Per-phase
  motion" when the artifact is available. Don't invent new motion styles
  in the meantime: reuse the ones below.

## Rules

1. **Short.** Interface feedback 120 to 260 ms; the Design System's band
   is **150 to 250 ms** for most transitions ([[Design-System]], "The
   church profile"). Larger surfaces (a modal, a sheet) at most 260 ms in,
   160 ms out. Exits are faster than entrances.
2. **Only cheap properties:** `opacity` and `transform` for movement;
   `background-color`, `border-color`, `color` and `box-shadow` for state.
   Never animate `width`, `height`, `top` or `left` of large areas.
3. **Small distances:** slides of 4 to 18 px, scales between .97 and 1.1.
4. **Easing:** entrances `cubic-bezier(.2, .8, .2, 1)` (a soft
   ease-out, `--acct-ease`); simple state changes `ease`; long reveals
   `cubic-bezier(.2, .7, .2, 1)`; the landing intro `cubic-bezier(.4, 0,
   .2, 1)`; spinners and countdowns `linear`.
5. **Reduced motion is total.** Under `prefers-reduced-motion: reduce`
   every animation and transition in the redesign stops (each stylesheet
   ends with its own block); timed behaviour still happens (a toast still
   closes after 5 s), only without movement. Scripts read
   `matchMedia("(prefers-reduced-motion: reduce)")` and skip their waits.
6. **Nothing blocks.** Content is usable while it animates; no animation
   hides a control the person needs; toasts don't take clicks from the page
   around them. The only deliberate delay is the landing intro (below).
7. **Keyboard and screen readers first.** Focus moves when a menu or dialog
   opens and returns when it closes; motion never replaces an
   `aria-live` message or a visible state.

## Standard motions (as built)

| Motion | Spec | Where |
|---|---|---|
| Hover and focus on buttons, links, cards | `.15s` to `.2s ease` on colour, border, shadow; buttons lift 1 px; press scales to `.97` (`.12s`) | everywhere (`dashboard.css`, `landing.css`, `account.css`, `auth.css`) |
| Card hover | lift 2 to 4 px and a stronger shadow, `.2s` to `.25s`; directory cards zoom the cover slightly | landing, directory, dashboard |
| Menu or popover open | fade and slide down 6 px (scale `.98` to 1), `.2s cubic-bezier(.2,.8,.2,1)`; close `.15s ease` up 4 px | account popover, CMS camera menus (`pf-drop`), public menus |
| Chevron | rotates 180° in `.2s` to `.22s` when its menu opens | account button, sidebar categories, landing menu |
| Menu item hover | background tint `.16s`; account items nudge right by .15 rem | account popover |
| Modal open | backdrop fades `.26s`; dialog rises 12 px and scales `.97` to 1 in `.26s cubic-bezier(.2,.8,.2,1)`; close `.16s` | Edit Profile, Church CMS editor |
| Sheet (phones) | modal slides up from the bottom (`translateY(100%)` to 0) | Edit Profile below 576 px |
| Close button | rotates 90° on hover or focus | Edit Profile |
| Inline error | fades in `.2s`; a field error shakes 3 px once (`.32s`) | CMS editor, Edit Profile |
| Button busy | label changes to "Saving…" and a 1 em spinner turns (`.7s` to `.8s linear`) | CMS editor, Edit Profile, sign-in |
| Value changed | the changed avatar or figure pops (scale 1.1 at 40 %, `.32s`) | Edit Profile initials |
| Segmented switch | thumb slides to the choice `.26s cubic-bezier(.2,.8,.2,1)` | Appearance in the account popover |
| Theme change | the page cross-fades colours `.3s` (class `chord-theme-fade` for 300 ms) | Appearance switch |
| Toast in and out | in: slide 12 px and fade `.28s`; out `.2s` to `.25s`; a 3 px gold countdown bar over 5 s; hover or focus pauses it | CMS toasts, welcome toast, account toast |
| Tooltip | fades and rises 2 px in `.18s`, on hover (pointer devices) or keyboard focus | "Go to Homepage", back arrow |
| Wizard step | the step slides 18 px and fades (from the left when going back); the progress bar grows | church registration |
| Sidebar collapse | Bootstrap collapse; icon-only mode switch; off under reduced motion | app sidebar |
| Landing reveal | sections rise 18 px and fade as they enter, `.6s` to `.95s cubic-bezier(.2,.7,.2,1)` | landing page |
| Landing intro | first visit in a browser session only: logo scales in `.9s`, equaliser bars, a progress line; stays at least 0.8 s (the owner's approved exception), leaves by 4 s at most, fails safe at 6 s; never without JavaScript | landing page |

## Per-phase motion

- **Phase 3 (shared components):** the motions above become shared
  classes so every Module uses the same timings (menus, modals, toasts,
  tooltips, busy buttons, inline errors, hover lifts). **Awaiting the
  artifact** for any component-specific motion (skeleton shimmer, tab
  indicator, table row states).
- **Phases 4 to 10:** reuse the shared motions. **Awaiting the artifact**
  for screen-specific motion (for example drag-and-drop in the lineup
  builder, transposing chords, calendar view changes).
- **Phase 11:** audit every screen against this note: durations within the
  band, only cheap properties, reduced motion total, nothing blocking.
