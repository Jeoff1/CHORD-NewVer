---
status: accepted
---

# Worship planning is the scope; church administration stays light

CHORD's scope is now the [[Concept-Brief]] (2026-11-16): turning a
service's theme into a confirmed song lineup with tracks, chord sheets and
keys, with only light church management around it. This replaces the
earlier plan, which built church administration first and left the music
features for later. The user chose to build it inside this project and to
rewrite the plan around the brief (2026-11-16), because the brief's core is
what the adviser asked for and the project already has sign-in, Roles,
church setup, Members and the audit trail.

## What changed

- **Dropped from the plan and the Module registry:** Giving, Records,
  Services (Service Requests), Ministries and Events. None had been built,
  so no data is lost. Their Labels (service, offering, ministry, officiant)
  and the default roles made for them (Finance, Records Keeper, Ministry
  Leader) went with them; a role some user still holds is kept.
- **Modules now:** Members, Worship, Teams (needs Worship) and
  Announcements. One Module may span several Django apps: Worship is
  `apps/worship` (planning) and `apps/songs` (the song pool).
- **Labels now:** member, worship service, sermon, lineup.
- **Default roles now:** Administrator, Office Staff, Pastoral Staff,
  Worship Leader, Team Member.
- **Kept:** [[0001-configure-behavior-not-identity]] still governs every
  feature. Service templates, song slots, theme tags, seasons, team parts,
  search genres and ranking weights are church settings with neutral
  defaults.

## Where CHORD departs from the brief's suggested stack

The brief calls its stack "suggestions, not requirements".

- **Django templates, Bootstrap and HTMX** instead of React or Next.js with
  a separate API ([[0002-server-rendered-ui]]). Song pages add focused
  scripts for the chord viewer and the player.
- **One Django project** instead of a web app plus a separate ML service.
  The ML code runs only in the search worker, a separate process started
  with `manage.py run_worker`, so web requests never load a model.
- Later decisions record the ML runtime and the job queue as they are
  built.

## Consequences

- The Members Module is more than the brief's "basic" directory; it stays
  as built.
- "Pastor" in the brief is the **Pastoral Staff** default role plus the
  "final say on a lineup" permission. The church renames the role and
  decides who holds the permission.
- The brief's "Service" is CHORD's **Worship Service**; "service" alone no
  longer means a requested service.
- The [[Services]] design note is kept for reference, marked out of scope.
