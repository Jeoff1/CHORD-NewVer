# Development Log

Newest entries first. Template: `Templates/Development-Log-Entry`.

## 2026-11-20: README

- Added `README.md` at the project root, the first page someone opening
  the repository sees. It says:
  - what CHORD does, and what's built and what's next;
  - the stack;
  - quick-start commands, linking to [[Environment-Setup]] for the full
    steps;
  - how to run the website and the search worker, and how to try
    suggestions without Spotify;
  - the checks script, the folder layout, and where the docs start
    ([[00-Home]]);
  - the rules on secrets, Spotify data and lyrics.
- Checks: documentation only, no code changed, so `scripts/check.ps1` was
  not run.

## 2026-11-19: Phase 6 part B approved; "swapped in" feedback label

On branch `phase-6-lineups`; not merged yet.

- **Approved and recorded** in [[Design-Decisions]] (Phase 6), the
  [[workflow-spec]] (step 11, song usage, attendance report) and the
  [[Glossary]] (Suggestion Feedback, Song Usage):
  - **the feedback labels:** regenerated and pool songs leave none, and
    confirming again replaces the feedback;
  - **usage counting:** the report counts past services only; ranking
    counts every confirmed lineup of an earlier service;
  - **the overused highlight:** a song sung again sooner than the repeat
    window;
  - **the report permissions:** `worship.view_song_usage` for Worship
    Leader and Pastoral Staff; attendance reuses `record_attendance`.
- **Changed:** an alternative chosen in a swap now gets its own label,
  **swapped in** (a positive, like kept), so Phase 9 can tell it from a
  top pick that stayed. A swapped-in song that is later swapped out or
  removed is labelled swapped or removed.
- **Migration `worship/0009_feedback_swapped_in`:** the new label choice.
  Nothing is backfilled: lineups reviewed earlier kept no record of which
  "kept" songs came from a swap.
- **Notes:** [[Worship]] (feedback labels).
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 564
  tests passed (2 new), with 97% coverage (`feedback.py` 97%).

## 2026-11-19: Phase 6, part B: feedback, song usage and reports (Phase 6 done)

On branch `phase-6-lineups`. The phase is not merged yet.

- **Suggestion Feedback** (migration `worship/0008`; `feedback.py`):
  - while a lineup is reviewed, `Lineup.suggestion_outcomes` follows each
    suggestion placed in it: kept, swapped or removed. Regenerating
    forgets the songs it replaces, and pool songs leave none;
  - confirming saves the rows, replacing an earlier confirmation's;
  - the features are only the lyrics-based scores and the church's own
    data (`SuggestionFeedback.FEATURES`). No Spotify field, no Trusted
    Artist bonus, no version choice, no genre-filter record;
  - existing lineups start with their placed suggestions as kept.
- **Song usage** (`usage.py`, review F3): `ranking.song_usage()` reads the
  confirmed lineups of services, not cancelled, before the one being
  ranked. Familiarity and recent use now count.
- **Reports** (`reports.py`, `/worship/reports/`):
  - song usage, with a period filter and CSV export, highlighting songs
    sung again within the repeat window;
  - attendance, the headcount per service held, which doesn't exist until
    a headcount is recorded;
  - a new permission, `worship.view_song_usage`, for Worship Leader and
    Pastoral Staff. The attendance report uses `record_attendance`.
- **Wording:** the feel-mismatch reason now reads "Its feel (upbeat)
  doesn't match this slot, which asks for slow, but it fit best."
- **Notes:**
  - [[Worship]];
  - [[Design-Decisions]] (song usage done; the wording);
  - [[Glossary]] (Suggestion Feedback, Song Usage);
  - [[Development-Plan]] (Phase 6 done);
  - [[00-Home]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 562
  tests passed (23 new), with 97% coverage (`feedback.py` 96%,
  `reports.py` 95%, `lineups.py` 99%).

## 2026-11-19: Phase 6, part A click-through: four display fixes

On branch `phase-6-lineups`, from the user's click-through.

- **Feel reasons follow the slot.** A lineup song now stores only its
  theme reasons (match, tags, other versions). Its feel reason is worked
  out for the slot it is in now (`LineupItem.slot_reason`, from the new
  `sequencing.slot_reason`), so a song moved, swapped, added or
  regenerated into a slot never shows another slot's feel.
- **Full names.** A shared `display_name` (`apps/core/people.py`) and
  `{{ user|person_name }}` filter give the full name, or the username when
  there is none.
  - The lineup page already used it for "Confirmed by", "Sent back by" and
    the Mark: on the development database, "Pastor" is named "Church
    Pastor".
  - "About this search" ("Asked for … by") and the song page ("Reviewed
    by") printed usernames; both now use it.
- **No nested brackets.** "Other versions in the pool" now reads "Title,
  Artist; Title, Artist". The lineup audit lists songs the same way.
- **Arrows.** ↑ and ↓ show only where `lineups.allowed_moves` allows the
  move. The server still refuses the same moves; moving into a locked
  song's place now reads "<song> can't move into a locked song's place."
- **Migration `worship/0007_lineup_reason_text`:**
  - drops the feel reasons already stored on lineup songs;
  - rewrites saved "Other versions" reasons, on lineup songs and on
    suggestions, into the new form;
  - updates the help text of `LineupItem.reasons`.
- **Notes:**
  - [[Worship]];
  - [[Code-Conventions]] (naming people; no nested brackets).
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 539
  tests passed (13 new), with 97% coverage.

## 2026-11-19: Phase 6, part A review: the Mark, and adding any pool song

On branch `phase-6-lineups`, after the user reviewed part A.

- **Approved and recorded:** the user approved eight of part A's choices.
  They are now in [[Design-Decisions]] (Phase 6, "Approved after part A"),
  the [[workflow-spec]] and the [[Glossary]]:
  - default permissions come from `DEFAULT_ROLE_PERMISSIONS`;
  - both the leader and the pastor can save suggestions as the lineup;
    Office Staff can't see lineups;
  - locking isn't an edit, and a locked song stays put;
  - reopening or sending back clears the mark; confirming again clears
    the note;
  - a cancelled service's lineup can't be confirmed; a past service's can;
  - swap and regenerate use the latest finished run;
  - a never-confirmed draft is a 404 for team members;
  - leaders see theme notes.
- **Changed: adding from the pool.** Any pool song can now be added,
  except one a person marked "Not a worship song". Songs that failed the
  Worship Check, or were never checked, can be added and show a warning in
  the review and on the Add page. The team doesn't see the warning.
- **Changed: the leader's edits are marked.** The leader's edit to a
  confirmed lineup without the pastor's lock keeps it confirmed and marks
  it "Changed by <name>", with the time; no lock follows. Only the latest
  mark shows: the pastor's "Edited by" replaces it, and reopening or
  sending back clears it.
- **Model:** the mark is now general: `edited_at`, `edited_by` and
  `edited_with_final_say` replace `pastor_edited_at` and
  `pastor_edited_by`. Migration `0006_lineups` was regenerated in place,
  because it was never applied or pushed.
- **Notes:**
  - [[Design-Decisions]];
  - [[workflow-spec]] (roles, step 10);
  - [[Glossary]] (Locked Song and Mark added; Pastor's Lock updated);
  - [[Worship]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 526
  tests passed (9 more than part A), with 97% coverage (`lineups.py` 99%,
  the lineup views 97%).

## 2026-11-19: Phase 6, part A: lineups, review and the final say

Branch `phase-6-lineups`. Built from [[Design-Decisions]] (Phase 6) and
[[0008-final-say-permission]], with findings F4, F5 and F7 of the
[[2026-11-19-Workflow-Review]].

- **Models** (migration `worship/0006_lineups`):
  - Lineup: draft or confirmed, the source run, the latest confirmation,
    the pastor's lock, the "Edited by" mark, and the send-back note;
  - Lineup Item: song, slot, order, Service Key, notes, reasons and a lock;
  - the permissions `view_lineup`, `add_lineup`, `change_lineup` and
    `finalize_lineup`.
- **Rules** (`apps/worship/lineups.py`):
  - save the reviewed suggestions as the lineup (its own copy, F4);
  - swap, lock, reorder, remove, add from the pool, key and notes, and
    regenerate around locked songs; never two songs with the same title;
  - confirm, the pastor's lock, the mark, reopen and send back, all
    checked against `finalize_lineup`, never a role name.
- **F7:** a cancelled or past service gets no suggestions
  (`suggesting.planning_closed`) and no new lineup. A cancelled service's
  lineup can't be confirmed.
- **F5:** `can_plan`'s `change_lineup` now exists. The worship leader now
  sees theme notes; team members still don't.
- **Default roles:**
  - Pastoral Staff: view, add, change and finalize;
  - Worship Leader: view, add and change;
  - Team Member: view.

  Granted through `DEFAULT_ROLE_PERMISSIONS`, which the post_migrate sync
  applies on every `migrate` (the project's way of granting new
  permissions; see `accounts/migrations/0003`).
- **Labels:** a new `pastor` Label (default "Pastor").
- **Screens:**
  - the lineup page, swap, Add a song, Key and notes, and Send back;
  - a lineup card on the service page;
  - in the suggestions panel, "Save these songs as the lineup". The
    panel hides "Find songs" for cancelled or past services.
- **Other changes:**
  - `suggesting._feel_weight` became `feel_weight`, so regenerating uses
    the run's feel weight;
  - a new test builder, `make_search_run`;
  - the church tests' Label data now includes the `pastor` Label.
- **Notes:**
  - [[Worship]] (lineups, permissions, roles, settings);
  - [[Church-Setup]] (Labels);
  - [[Accounts]];
  - [[Glossary]] (Service Key);
  - [[Code-Conventions]] (builder);
  - [[Development-Plan]] (part A ticked; Phase 6 in progress; F7 added);
  - [[00-Home]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 517
  tests passed (73 new), with 97% coverage (`lineups.py` 99%, the lineup
  views 96%).

## 2026-11-19: workflow review; Phase 6 lineup decisions

- **Review:** [[2026-11-19-Workflow-Review]] reviewed the code on `master`
  (`239d167`) against the [[workflow-spec]], following [[Review-Prompt]].
  Verdict: mostly follows the flow, and no hard rule is broken. It made 14
  findings (F1 to F14), each sorted as must fix before Phase 6, fix during
  Phase 6, or later. Read-only: Ruff lint and format check passed,
  `manage.py check` was clean, there were no missing migrations, and 444
  tests passed (coverage not run).
- **Decisions approved by the user (F1, F2, F6):**
  - the final say is the permission `worship.finalize_lineup`, held by
    Pastoral Staff by default and by the Administrator. Code checks the
    permission, never a role name. There is a new church Label, `pastor`
    (default "Pastor");
  - the pastor's edits to a draft don't lock the worship leader out. The
    pastor's lock starts when the pastor confirms a lineup, or edits a
    confirmed one, and lasts until the pastor reopens it;
  - a reopened lineup counts as unconfirmed: team members see a "being
    revised" note instead;
  - the mark reads "Edited by <pastor Label> (<person's name>)", with the
    time;
  - sending back returns a lineup to draft with a note; it adds no state;
  - overused songs are highlighted in the song usage report, not given a
    report of their own.
- **Also aligned:**
  - F14: the spec now has one Spotify connection per user, as in
    Design-Decisions;
  - F8: song usage is computed from confirmed lineups, not stored.
- **Notes:**
  - [[0008-final-say-permission]] (new);
  - [[Design-Decisions]] (Phase 6, and the Phase 8 notification);
  - [[workflow-spec]] (roles, step 10, hard rules, tables);
  - [[Development-Plan]] (Phase 6 items and "done when");
  - [[Glossary]] (Final Say, Pastor's Lock and Send Back added; Lineup
    updated);
  - [[00-Home]] (links).
- **Readings approved by the user:**
  - "the pastor's lock" is the name, kept apart from the lock on a song;
  - only holders of the final say can send a lineup back, and sending back
    a confirmed lineup reopens it;
  - "overused" means sung again within the church's repeat window.
- **[[Concept-Brief]] updated to match, with the user's agreement:**
  - the pastor's lock starts only when the pastor confirms a lineup, or
    edits a confirmed one;
  - the mark reads "Edited by <pastor Label> (<name>)", with the time;
  - Spotify has one connection per user (the Admin row).
- Checks: documentation only, no code changed, so `scripts/check.ps1` was
  not run.

## 2026-11-18: theme tags keep today's rule

Tag options measured on the 23 seeded hymns with the ONNX models (in
memory; nothing changed), aiming for 3 to 5 sensible tags per song:

| Option | Tags per song | Songs with 3–5 tags | Faith given to |
|---|---|---|---|
| Today (0.5 or more, best four) | 3.7 | 21/23 | most hymns |
| (a) stand out on the model's margin, stricter | 2.6 | 14/23 | most hymns |
| (a) stand out on the model's margin, looser | 4.0 | 21/23 | 18/23 |
| (a) against each tag's average over the pool | 4.1 | 18/23 | 2/23 |
| (c) lyrics embedding against tag name and keywords | 2.3–3.4 | 8–16/23 | — |

- **Kept today's rule.** "(a) against each tag's average" was the most
  specific, but it makes a song's tags depend on the rest of the pool,
  bringing back the relative-score problem the fixed relevance scale just
  removed, and it gave Christ the Lord Is Risen Today "Birth of Jesus".
  The margin variants were close to today's tags or too few; (c) missed
  obvious tags (Silent Night without Birth of Jesus).
- Recorded "(a) against each tag's average" in the [[Development-Plan]]'s
  Future experiments, to revisit when the pool is larger. Updated
  [[Design-Decisions]] (the decision), the plan's Phase 5 follow-up list,
  [[Worship]] and [[00-Home]], which had it as open.
- Checks: documentation only, no code changed, so `scripts/check.ps1` was
  not run.

## 2026-11-18: unset feel costs half a step; theme-tag options measured

- **Placement:** a song whose feel isn't known now costs half a step (0.075
  with the default feel weight) in a slot that asks for a feel, so it never
  beats a known close match. In the before-and-after comparison, Come, Thou
  Fount (feel unset, 0.39) had taken Praise from Blessed Assurance
  (upbeat, 0.52). Updated: [[Design-Decisions]], [[workflow-spec]] step 8,
  [[Worship]].
- **Theme tags, measured only** on the 23 seeded hymns with the ONNX
  models, aiming for 3 to 5 tags per song: (a) stand-out on probabilities
  or margins, (a) against each tag's own average margin, and (c) lyrics
  embedding against each tag's name and keywords. Results are in
  Design-Decisions (Phase 5 follow-up). Nothing applied.
- Verified: `scripts/check.ps1` passed: Ruff lint and format,
  `manage.py check` clean, no missing migrations, 444 tests passed, 97%
  coverage.

## 2026-11-18: Phase 5 smoke-test fixes

The user's first live smoke test (seeded hymns, then Spotify) found nine
issues; the agreed fixes are in [[Design-Decisions]] (Phase 5 follow-up).

- **Fixed scale:** relevance and match labels come from the engine's
  `similarity_range`, not the pool; "doesn't match the theme well" added.
  Default weights recalibrated (familiarity 0.2, season 0.15, recent use
  0.3); a migration moves a church still on the old defaults.
- **Feel:** placement treats feel as a preference with a feel mismatch
  weight (a setting, 0.15); feel is left blank when the analysis isn't
  sure (a migration queues unreviewed songs for analysis again); one-click
  feel correction in the panel, kept by later analysis (`feel_reviewed`).
- **Worship check:** the pass mark is a church setting (Settings → Worship
  check), with the optional rule for artists not on the Trusted Artists
  list, off by default and applied after the model. Changing the rules or
  the list rechecks unreviewed songs without a model. One-click "Not a
  worship song". Each search's genre-filter result is recorded on the run,
  for information only.
- **Versions** of one song are grouped after ranking and one is kept; the
  pool keeps all. A lineup never holds two songs with the same title.
- A hint in the panel when the theme has no notes.
- `seed_hymns` now adds 23 public-domain hymns, with eight carols, four
  slow hymns and two Easter hymns.
- Fixed: a similarity exactly on a label's line could get the label below
  (floating point); relevance is now rounded first.
- **Measured, not changed:** a "neutral" class for theme tags can't help;
  the zero-shot model has only two classes. Awaiting a decision.
- Notes: [[Worship]], [[Glossary]] (Pass Mark, Worship Check Settings,
  Version; Feel and Worship Check reworded), [[0006-onnx-runtime-for-song-analysis]]
  update, [[Code-Conventions]], [[Environment-Setup]] (with the smoke-test
  commands), [[workflow-spec]] steps 6 to 9, the [[Development-Plan]]
  (follow-up list, and tempo from LRCLIB as a future experiment), and
  Design-Decisions (follow-up section; Phase 9 now also excludes the new
  artist rule, the kept version and the genre record from training).
- Verified:
  - `scripts/check.ps1` passed: Ruff lint and format, `manage.py check`
    clean, no missing migrations, 442 tests passed (404 before), 97%
    coverage.
  - Before-and-after rankings computed in memory with the ONNX models on
    the smoke-test runs ("Grace and salvation", "The birth of Jesus"); the
    two "Good News" recordings and three "Silent Night" versions now count
    once each.
  - Not applied to the development database yet: run `migrate`.

## 2026-11-18: Phase 5, song suggestions

- **The suggestion pipeline** ([[Worship]]), from the work in progress
  committed earlier: Suggestion Settings, Seasons, Search Runs and
  Suggestions; search phrases, Spotify search with the unfiltered retry,
  cleanup, lyrics, analysis, ranking over the whole pool, sequencing into
  the song slots, and reasons.
- **Fixed** in that work: `phrases.py` counted each chosen phrase twice,
  so a run searched about half the phrases the settings asked for.
- **Built to [[Design-Decisions]], Phase 5:**
  - the model's worship score (`Song.worship_model_score`, lyrics only)
    kept apart from the Trusted Artist bonus (`worship_score`); a
    migration queues analysed songs to be analysed again;
  - the Spotify safeguards in `apps/songs/spotify.py`, with the shared
    block saved as **Spotify Limit** rows; a quota pause makes a run rank
    the pool instead; Spotify requests and 429s are recorded on each run;
    Find on Spotify never fetches a pooled track and shows a pause;
  - one search worker, enforced by a PostgreSQL advisory lock
    (`apps/core/locks.py`), which `process_songs` also takes;
  - suggestions only for `worship.suggest_songs` (Worship Leader and
    Pastoral Staff by default).
- **Screens:** the Suggested lineup panel on the service page (HTMX
  progress while a run works), and Seasons and Suggestion settings in the
  worship settings.
- **`manage.py seed_hymns`**: nine public-domain hymns, to try
  suggestions without Spotify.
- **Notes:** [[0007-search-worker]] (new); [[0006-onnx-runtime-for-song-analysis]]
  update note; [[Glossary]] (Worship Check, Trusted Artist, and six new
  terms); [[Code-Conventions]]; [[Environment-Setup]]; `AGENTS.md` (one
  worker, and where the safeguards live); the [[Development-Plan]] Phase 5
  ticked and set Done; Design-Decisions' Phase 5 heading set done.
- Verified:
  - `scripts/check.ps1` passed: Ruff lint and format, `manage.py check`
    clean, no missing migrations, 404 tests passed (298 before), 97%
    coverage. The guard test passed.
  - Not verified live: Spotify (no credentials in `.env` yet) and the ONNX
    models on the new pipeline. The tests use FakeHttp and the keyword
    engine.
  - The migrations were not applied to the development database; run
    `python manage.py migrate`.

## 2026-11-18: the user's decisions on the remaining contradictions

- **Source order:** the [[Concept-Brief]] now ranks after
  [[Design-Decisions]] and before the [[workflow-spec]], in `AGENTS.md`
  and in the header of Design-Decisions.
- **Notifications:** Phase 6 shows an "Edited by pastor" mark with its
  time to everyone who can see the lineup, with no notification system.
  Phase 8 notifies the assigned team members in the app. Changed in
  Design-Decisions (Phases 6 and 8), the spec and the plan.
- **Spotify playlist:** saved automatically on confirmation; with no
  connection, or on a 429, it is skipped and a "Save to Spotify" button
  lets the leader retry. Changed in Design-Decisions (Phase 7), the spec
  and the plan.
- **One worker:** Phase 5 enforces it with a PostgreSQL advisory lock
  taken at worker startup; `claim_next_run` stays. Changed in
  Design-Decisions (Phase 5, with a test and a reminder to update the
  Worship note, decision 0006 and the Glossary with the code), the spec
  and the plan.
- **Office Staff** stays: added to the brief's roles table and the spec as
  an optional role that keeps the member directory up to date.
- **[[Development-Plan]]:**
  - the out-of-scope line now matches the brief;
  - Phase 5 now lists the Design-Decisions items: the raw model score,
    suggestions hidden from team members, the Spotify safeguards, one
    worker, the missing tests, and the notes to update;
  - Phase 6 now has the pastor's rules and the tests for each role;
  - Phase 7 now has Find chords, the chord-sheet count per lineup, the
    practise-along toggle, and the automatic playlist;
  - Phase 8 now has in-app notifications;
  - Phase 9 now excludes Spotify data from the training features, with a
    test;
  - the Phase 10 Development Mode question is moved to "Decided since".
- [[Project-Overview]] and [[00-Home]]: theme text as model input, and
  the brief's full out-of-scope list. [[0003-editable-roles]]: a dated
  update note (five default roles; the finance and records examples are
  out of scope).
- The spec's "What to produce" section moved to [[Review-Prompt]]
  (`04-Development/Reviews/`).
- Checks: documentation only, no code changed, so `scripts/check.ps1` was
  not run. Every `[[link]]` in the changed notes resolves.

## 2026-11-18: vault aligned with the updated brief and design decisions

- `AGENTS.md`, the [[Concept-Brief]] and [[Design-Decisions]] were updated
  by the user, answering the open questions of the workflow review
  (`docs/workflow-review.md`). The rest of the vault now follows them:
  - [[workflow-spec]]: theme text as model input, live versions, ranking
    the whole pool, the raw model score and the Trusted Artist bonus,
    suggestions hidden from team members, the pastor's decision rules,
    training features, chord sheets allowed early with approval of team
    members' pastes, encrypted tokens, the playback 429 fallback, a new
    Spotify safeguards section, an undeletable Administrator, and which
    expected tables are stored as fields.
  - [[0005-worship-planning-scope]]: the brief's longer out-of-scope list,
    the main module's priority, the stack departures (ONNX Runtime, JSON
    embeddings instead of pgvector; job queue still to record), Members
    beyond the basic directory, and the Administrator role.
  - [[Development-Plan]] Phase 7: chord sheets allowed before
    confirmation, approval of team members' pastes as a permission,
    encrypted Spotify tokens, the playback 429 fallback, the safeguards for
    server-side calls, and the Design-Decisions tests.
  - [[00-Home]]: links to the workflow spec and Design-Decisions, and the
    Phase 5 status note.
- Branch: `master` (Phase 4) was merged into `phase-4-song-pool` first, so
  these notes build on the Phase 4 vault.
- Checks: documentation only, no code changed, so `scripts/check.ps1` was
  not run. Links were checked by hand.

## 2026-11-17: Phase 4, the song pool

- **[[Worship]]'s song pool** (`apps/songs`):
  - Song, Theme Tag (30 neutral tags seeded, with keywords) and Trusted
    Artist (empty);
  - the Spotify client (app token, paged search, genre filter with an
    unfiltered retry, one track by ID) and the LRCLIB client (one request
    at a time, fallback search, Retry-After);
  - the ML engine: ONNX Runtime models or the keyword stand-in
    ([[0006-onnx-runtime-for-song-analysis]]), and `manage.py
    download_models`;
  - analysis from lyrics only: worship check, up to four theme tags, feel
    guess and embedding; a reviewed song keeps its corrections;
  - `manage.py process_songs` for lyrics and analysis;
  - the song library: list with filters, song page, editing, Check again,
    Find on Spotify, and the two settings lists;
  - default-role permissions and the audit trail.
- Shared pieces: `apps/core/http.py` (every outside call) and, in
  `apps/core/testing.py`, `ChordTestRunner` (network blocked, keyword
  engine), `FakeHttp` and `make_song`.
- Model choice: the 13 MB xtremedistil zero-shot model was tried and
  dropped for DeBERTa-v3-xsmall (96 MB). On four public-domain hymns and
  four invented secular songs, DeBERTa passed every hymn (0.86 to 0.999)
  and failed every secular song (0.01 or less). An invented love song in
  church imagery also passed (0.85); people correct such cases.
- Verified:
  - `scripts/check.ps1` passed: Ruff clean, `manage.py check` clean, no
    missing migrations, 298 tests passed, 97% coverage. The guard test
    passed. `ml/onnx.py` is 52% covered: tests never load a model.
  - By hand: `download_models` fetched both models, and the ONNX engine
    analysed the eight sample texts in about 1 s each. Three live LRCLIB
    lookups gave the expected found, found and not found.
  - Not verified live: Spotify, because no credentials are in `.env` yet.
    Its client is tested against the documented response shapes.
  - Migrations applied to the development database.

## 2026-11-17: Phase 3, worship schedule and themes; the scope change

- **Scope.** The project now follows the [[Concept-Brief]]
  ([[0005-worship-planning-scope]]). The [[Development-Plan]] was rewritten
  around it: Phases 3 to 10 are new, and Giving, Records, Services,
  Ministries and Events are out of scope.
- **Re-scoped the configuration layer:**
  - Modules are now Members, Worship, Teams and Announcements. A Module
    can span several apps and can need another Module ([[Church-Setup]]).
  - Labels are now member, worship service, sermon and lineup.
  - Default roles are now Administrator, Office Staff, Pastoral Staff,
    Worship Leader and Team Member ([[Accounts]]).
  - Two data migrations tidy existing installations: stale Module switches
    and Labels are dropped, and unused obsolete roles are removed.
- **[[Worship]]** (`apps/worship`), first part:
  - Service Templates with Song Slots, and one seeded neutral template;
  - Worship Services, the schedule list and the month calendar;
  - "Schedule weeks ahead" for templates with a usual day and time;
  - Themes with Series, and notes shown only to people who plan;
  - a headcount per service;
  - default-role permissions and the audit trail.
- Shared pieces: `apps/core/music.py` (Feel); a church-edited list's title
  can follow a Label; test builders `make_service` and `make_theme`.
- Installed the ML runtime chosen for later phases (ONNX Runtime,
  tokenizers, NumPy, huggingface-hub); nothing uses it yet.
- Verified:
  - `scripts/check.ps1` passed: Ruff clean, `manage.py check` clean, no
    missing migrations, 197 tests passed, 97% coverage. The guard test
    passed.
  - Migrations applied to the development database.

## 2026-11-16: Phase 2, Members

- [[Members]] (`apps/members`):
  - Member, Membership Status (with "counts as active"), Household and
    Household Roles, with neutral defaults seeded;
  - list, detail, add, edit, archive and restore;
  - the own-record page, private photos and files;
  - CSV import (preview, problem report, duplicate check) and CSV export
    using the same columns;
  - the privacy rules applied to lists, search, forms, import and export;
  - default role permissions.
- Shared pieces in `apps/core`:
  - church-edited lists (`ChoiceItem`, `SettingList`, `setting_list_urls`);
  - Custom Fields (`CustomFieldDefinition`, `CustomFieldsFormMixin`;
    [[0004-custom-field-values-as-json]]);
  - private file storage (`PRIVATE_MEDIA_ROOT`, `private_file_response`,
    `PrivateFileInput`).
- The "Members" Module now opens from the navigation and dashboard. The
  account menu shows "My member record" for linked accounts.
- Fixed while testing:
  - an import file with only blank headers was reported as "no rows"
    instead of "empty";
  - the household list wasn't reliably ordered;
  - the permission matrix tests now submit every role's ticks, as the page
    does.
- Verified:
  - `scripts/check.ps1` passed: Ruff clean, `manage.py check` clean, no
    missing migrations, 150 tests passed, 97% coverage. The
    guard test passed.
  - Migrations applied to the development database.

## 2026-11-16: Phase 1, Church Setup and Access

- [[Church-Setup]] (`apps/church`):
  - the Church Profile, as a single row, with its logo, currency and time
    zone;
  - the Module registry, `ModuleRequiredMixin` and navigation for
    switched-on Modules only;
  - Labels, with the `{% label %}` template tag;
  - the three-step setup wizard and the settings pages;
  - the dashboard.
- [[Accounts]]:
  - Roles on Django groups, with six seeded default roles
    ([[0003-editable-roles]]);
  - the permission matrix;
  - user management (add, edit, deactivate, set password);
  - My profile, password change, and password reset by email;
  - rules that protect the last administrator.
- Audit trail (`apps/audit`): `AuditEvent` and the
  `snapshot`/`diff`/`record_change` helpers, used by every Phase 1 screen,
  and the audit log page.
- Shared pieces in `apps/core`: `FilteredListView`, `FormPageMixin` and
  `form_page.html`, plus pagination and search templates. Also new: 403 and
  404 pages, and styled checkbox lists.
- Fixed while testing:
  - saving a new Church Profile over the existing row lost its creation
    time;
  - checkbox lists put the checkbox class on their outer wrapper;
  - the audit `diff()` ignored deleted values.
- Added Pillow 13.0.0 (image uploads).
- Verified:
  - `scripts/check.ps1` passed: Ruff clean, `manage.py check` clean, no
    missing migrations, 84 tests passed, 98% coverage. The guard test
    passed.
  - On the development server, protected pages redirect to sign in, and
    the sign-in and password reset pages render.

## 2026-11-15: Phase 0, engineering baseline

- Made the first Git commit (the foundation) and did Phase 0 on the
  branch `phase-0-baseline`.
- Added `apps/core`:
  - shared abstract models (`TimeStampedModel`, `PublicIdModel`);
  - a project form renderer that gives every form Bootstrap markup;
  - shared test-data builders;
  - the home page.
- Added the base template, with Bootstrap 5.3.3 and HTMX 2.0.4 stored in
  `static/vendor/` ([[0002-server-rendered-ui]]).
- Added sign in and sign out ([[Accounts]]).
- Added `scripts/check.ps1` and coverage.py.
- Added the denomination-free guard test.
- Documented the conventions in [[Code-Conventions]].
- Verified:
  - `scripts/check.ps1` passed: Ruff clean, `manage.py check` clean, no
    missing migrations, 13 tests passed, 100% coverage.
  - The guard test failed as expected on a temporary file containing a
    banned word; the file was then removed.
  - On the development server: an anonymous visitor to `/` is redirected
    to sign in, the sign-in page shows the Bootstrap form, and the vendor
    files are served (HTTP 200).

## 2026-11-15: Development plan

- Wrote the [[Development-Plan]]: ten phases for the management side, from
  the engineering baseline to hardening. The music features (ML song
  recommendation, playback, chord sheet viewer) are deferred to Phase 10.
- Each phase has task checklists and a "done when" condition, and the plan
  has a shared definition of done.
- No code changed.

## 2026-11-15: Documentation vault

- Set up this Obsidian vault in `docs/CHORD-Vault/`.
- Moved the glossary and the decision record into the vault so all project
  documentation lives in one place.

## 2026-11-15: Core design rule

- Decided that churches configure what they do instead of choosing a
  denomination: [[0001-configure-behavior-not-identity]].
- Defined the project's terms in [[Glossary]] and sketched the
  [[Services]] module.
- Added agent instructions (`AGENTS.md`, `CLAUDE.md`) so future development
  follows the rule.

## 2026-11-15: Project foundation

- Created the Django 5.2 project (`config/`) with settings read from `.env`.
- Created PostgreSQL database `chord_newver_db`, separate from the original
  CHORD's.
- Added the custom user model in `apps/accounts` and ran the initial
  migrations.
- Verified: `manage.py check` clean, Ruff clean, database connection to
  PostgreSQL 17 confirmed.
