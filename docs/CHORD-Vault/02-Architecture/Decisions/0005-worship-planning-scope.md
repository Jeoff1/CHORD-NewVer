---
status: accepted
---

# Worship planning is the scope; church administration stays light

CHORD's scope is now the [[Concept-Brief]] (2026-11-16, updated
2026-11-18): turning a service's theme into a confirmed song lineup with
tracks, chord sheets and keys, with only light church management around
it. This replaces the earlier plan, which built church administration
first and left the music features for later. The user chose to build it
inside this project and to rewrite the plan around the brief (2026-11-16),
because the brief's core is what the adviser asked for and the project
already has sign-in, Roles, church setup, Members and the audit trail.

The theme-based song lineup is the main module. When time is short, it is
finished and polished before any supporting module (`AGENTS.md`).

## What changed

- **Dropped from the plan and the Module registry:** Giving, Records,
  Services (Service Requests), Ministries and Events. None had been built,
  so no data is lost. Their Labels (service, offering, ministry, officiant)
  and the default roles made for them (Finance, Records Keeper, Ministry
  Leader) went with them; a role some user still holds is kept.
- **Also out of scope, by the updated brief (2026-11-18):** leadership
  appointment and ordination, SMS messaging, check-in and follow-up, and
  per-person attendance. None was planned or built. Attendance is a
  headcount per service.
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
- **ONNX Runtime** instead of PyTorch with sentence-transformers and
  transformers pipelines ([[0006-onnx-runtime-for-song-analysis]]).
- **Embeddings as JSON on the song** instead of PostgreSQL with pgvector.
  This is enough at this project's scale; pgvector is worth considering
  only if the pool grows past several thousand songs ([[Design-Decisions]]).
- **The job queue** (the search worker instead of Celery or BullMQ) is
  recorded in its own decision when Phase 5 is finished, and the
  learning-to-rank library when Phase 9 starts.

## Consequences

- The Members Module goes beyond the brief's basic directory (names,
  contact details, households and CSV import): it also has membership
  statuses, custom fields, photos and CSV export. It stays as built and
  isn't extended further without the user's agreement.
- "Pastor" in the brief is the **Pastoral Staff** default role plus the
  "final say on a lineup" permission. The church renames the role and
  decides who holds the permission. What the final say means in practice is
  in the brief's Roles section and [[Design-Decisions]] (Phase 6).
- The Administrator role can't be deleted and always holds every
  permission ([[0003-editable-roles]]); the brief now says the same.
- The brief's "Service" is CHORD's **Worship Service**; "service" alone no
  longer means a requested service.
- The [[Services]] design note is kept for reference, marked out of scope.

## Update (2026-11-24)

At the adviser's request, special services (weddings, funerals and the
like) are back in scope as **occasions**: scheduled, and requested by
church members, but without the old design's fees, requirements or church
records ([[0012-occasion-services]]). The rest of this decision stands.
Per-person attendance is still out of scope; the adviser's request for "who
attended a service" is on hold ([[Design-Decisions]], "Adviser comments, 24
Nov").
