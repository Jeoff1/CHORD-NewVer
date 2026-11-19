# Workflow review, 2026-11-19

The code reviewed against the [[workflow-spec]], following [[Review-Prompt]].
The previous review is `docs/workflow-review.md` (2026-11-18).

## What was reviewed

- **Code:** `master` at `239d167` ("Docs: keep today's theme-tag rule"). The
  `phase-5-song-suggestions` worktree is at the same commit. Phases 0 to 5
  and the Phase 5 follow-up are built; Phase 6 is next.
- **Spec:** `docs/CHORD-Vault/workflow-spec.md` (updated 2026-11-18). Where
  the spec and [[Design-Decisions]] differ, Design-Decisions wins
  (`AGENTS.md`).
- **Checks run** (read-only; no code changed): Ruff lint passed, Ruff format
  check passed (182 files), `manage.py check` found no issues,
  `makemigrations --check` found no changes, and `manage.py test` ran
  **444 tests, all passing** (120 s). Coverage was not run, because it
  writes a data file.
- File paths are relative to the repository root.

**Status key:** **Pass**: built and matches the spec. **Partial**: built,
but incomplete or slightly different. **Fail**: built in a way that
contradicts the spec. **Not found**: no code exists yet. "What to fix" names
the phase of the [[Development-Plan]] that builds it. Finding numbers
(F1 to F14) point to [[#5. Findings by when to fix them]].

---

## 1. Review table

### Roles

| Check | Status | Evidence | What to fix |
|---|---|---|---|
| Pastor schedules services | Pass | `pastoral_staff` holds `add_worshipservice` and `change_worshipservice` (`apps/accounts/roles.py:43-45`) | None |
| Pastor posts the theme (title, scripture, sermon notes) | Pass | `Theme.title`, `scripture` and `notes` (`apps/worship/models/schedule.py:147-188`); `pastoral_staff` holds `change_theme` (`roles.py:46`) | None |
| Pastor can review, edit and confirm a lineup | Partial | The pastor can review suggestions (`roles.py:58`, panel at `apps/worship/templates/worship/service_detail.html:45`). There is no lineup to edit or confirm | Phase 6 |
| The pastor's decision is final, as a permission held by the pastoral role | Not found | No final-say permission and no confirmation logic exist | Phase 6, after F1 is decided |
| Worship leader generates the suggested lineup | Pass | `SuggestView` queues a run (`apps/worship/views/suggestions.py:132-149`); the worker carries it out (`apps/worship/suggesting.py:136-213`) | None |
| Leader swaps, locks, reorders and re-keys songs | Not found | No Lineup or Lineup Item | Phase 6 |
| Leader confirms the lineup | Not found | No confirmation | Phase 6 |
| Leader adds chord sheets and approves pasted ones | Not found | No Chord Sheet | Phase 7 |
| Team member sees a lineup only after it is confirmed | Partial | The pre-confirmation lineup (the suggestions) is hidden: every panel and suggestion URL needs `worship.suggest_songs`, which `team_member` lacks (`roles.py:90-93`). Tested in `apps/worship/tests/test_suggestion_views.py:87`. No confirmed lineup exists to show | Phase 6: gate the Lineup the same way and test it for every role (see F4, F5) |
| Team member plays songs and reads chord sheets | Not found | `team_member` has no `songs.view_song` | Phase 7 |
| Team member may paste a chord sheet, pending approval | Not found | No Chord Sheet | Phase 7 |
| Admin manages users, roles and settings | Pass | User and role views (`apps/accounts/views.py`); the permission matrix | None |
| Admin manages the Spotify connection | Partial | The app's Spotify credentials come from `.env` (`config/settings.py:157-158`). There is no per-user connection | Phase 7 (see F14) |
| The Administrator role can't be deleted and holds every permission | Pass | `apps/accounts/views.py:296-297`; `roles.py:139-141`. Tested in `test_role_management.py:64` and `test_roles.py:24`, `:58` | None |
| Office staff (optional) keeps the member directory | Pass | The `office_staff` role (`roles.py:22-39`) | None |

### Song selection

| Check | Status | Evidence | What to fix |
|---|---|---|---|
| 1. Pastor posts a theme | Pass | `Theme`; `request_run` refuses a service without a theme (`suggesting.py:73-74`) | None |
| 2. The theme becomes several search phrases | Pass | `search_phrases`: the short title, then KeyBERT-style phrases chosen with MMR (`apps/worship/phrases.py:60-91`). The count is the church setting `phrases_per_theme` (`apps/worship/models/suggestions.py:36-40`) | None |
| 3a. Searches all of Spotify, 10 per request, paging by offset | Pass | `PAGE_SIZE = 10`, offset paging stopping at 1000 (`apps/songs/spotify.py:43-44`, `:241-261`) | None |
| 3b. A filtered search that finds nothing is retried without the genre | Pass | `search_tracks` (`spotify.py:229-236`); each retry is recorded for information only (`suggesting.py:262-273`) | None |
| 3c. Follows the Spotify safeguards | Pass | See the safeguards table below | None |
| 4a. Removes duplicates | Pass | `clean_tracks` keys on base title and first artist (`apps/songs/cleanup.py:39-54`); the pool has one row per Spotify track (`apps/songs/models.py:144-150`) | None |
| 4b. Removes karaoke, instrumental and backing-track versions | Partial | `JUNK` matches only the singular words, so albums such as "Piano Instrumentals" or "Backing Tracks Vol 1" get through (`cleanup.py:11-15`; checked by hand) | F9 |
| 4c. A live version is dropped only when the plain version was also found | Pass | `cleanup.py:52-53`. Tested in `apps/songs/tests/test_cleanup.py:19-32` | None |
| 5a. Lyrics come from LRCLIB, one request at a time | Pass | `LrclibClient` spaces its requests (`apps/songs/lyrics.py:131-137`). Across processes, the worker and `process_songs` share one advisory lock (`apps/core/locks.py:29-43`, `run_worker.py:46-51`, `process_songs.py:29-41`). No web request calls LRCLIB | None |
| 5b. Lyrics are cached; songs already in the pool skip the lookup | Pass | Lyrics are stored on `Song.lyrics`. Only songs still pending are looked up (`suggesting.py:280`, `songs/models.py:52-53`) | None (see F11 for failed lookups) |
| 5c. Songs with no lyrics are set aside | Pass | Only `FOUND` songs are analysed (`apps/songs/analysis.py:222`), and only accepted songs are ranked (`suggesting.py:315-320`) | None |
| 6a. The classifier reads only the lyrics, drops non-worship songs and suggests tags | Pass | The engine receives only the lyrics text and the label hypotheses (`analysis.py:184-201`) | None |
| 6b. The raw worship score is stored in its own field | Pass | `Song.worship_model_score` (`songs/models.py:96-101`), apart from `worship_score` (`:102-107`). Tested in `test_analysis.py:269` | None |
| 6c. The Trusted Artist bonus is a church rule applied after the model | Pass | `trusted_artist_bonus` and `decide_check` (`analysis.py:130-155`), with the comment the decision asks for | None |
| 6d. The pass mark (default 0.5) is a church setting | Pass | `WorshipCheckSettings.pass_mark` (`songs/models.py:191-197`). Changing it re-decides unreviewed songs without a model (`analysis.py:262-294`) | None |
| 6e. Optional stricter mark or review for unlisted artists, off by default | Pass | `unlisted_rule` defaults to off (`songs/models.py:198-205`); applied in `decide_check` (`analysis.py:150-155`). Tested in `test_analysis.py:135` | None |
| 7a. Every accepted song in the pool is ranked | Pass | `_rank` reads `Song.objects.accepted()` (`suggesting.py:315-320`) | None |
| 7b. Embedding similarity on a fixed scale, with the four labels | Pass | `relevance` and `MATCH_LABELS` (`apps/worship/ranking.py:28-33`, `:70-82`) | None |
| 7c. Familiarity from past usage in confirmed lineups | Partial | `familiarity` adds 0.6 for "the team knows it", but its usage part is always 0 because `song_usage()` returns `{}` (`ranking.py:56-62`, `:85-87`) | F3 |
| 7d. Season fit | Pass | `Season.contains` (`models/suggestions.py:136-144`); `ranking.py:130` | None |
| 7e. Penalty for recent use | Partial | `recency()` is built (`ranking.py:90-96`) but always returns 0, for lack of usage data | F3 |
| 7f. Versions grouped and one kept, in the agreed order; the pool keeps every version | Pass | `versions.group` and its preference order (`apps/worship/versions.py:74-103`) | None |
| 8a. Top songs are placed in the service's slots | Pass | `sequencing.place` (`apps/worship/sequencing.py:58-88`). Slots are church-edited Template Slots | None |
| 8b. Feel is a preference: each step costs the feel weight, and an unset feel costs half a step | Pass | `feel_distance` and `UNKNOWN_FEEL_STEPS = 0.5` (`sequencing.py:22-41`). The weight is a church setting (`models/suggestions.py:68-73`). Tested in `test_suggestion_rules.py:294-319` | None |
| 8c. A lineup never holds two songs with the same title | Pass | `sequencing.py:64-72`. Tested in `test_suggestion_rules.py:325` | None |
| 8d. Feel is left unset when the analysis isn't sure | Pass | `guess_feel` (`analysis.py:167-173`) | None |
| 9a. Each suggestion stores why it was picked | Pass | `Suggestion.reasons` and `slot_reason` (`models/suggestions.py:273-278`), filled in by `ranking.py:139-154` and `versions.py:96-101` | None |
| 9b. Suggestions only for holders of suggest-songs (leader and pastor by default) | Pass | `SUGGEST` on every view (`views/suggestions.py:30`, `:81`, `:135`, `:156`); the panel needs `can_suggest` (`service_detail.html:45`); the default grants are in `roles.py:58`, `:79`. Tested in `test_suggestion_views.py:87` and `:385` | None |
| 9c. One-click "set feel" and "not a worship song" | Pass | `SuggestionFeelView` and `NotWorshipView` (`views/suggestions.py:107-129`); both are audited | Phase 6 (see F4) |
| 9d. A theme without notes gets a hint; notes are not required | Pass | `theme_needs_notes` (`views/suggestions.py:71`); `suggestions.html:20-22`. Tested in `test_suggestion_views.py:492-498` | None |
| 10. Leader reviews; leader or pastor confirms; the pastor's decision wins; "Edited by pastor" | Not found | No Lineup, confirmation or reopening | Phase 6, after F1 and F2 (see F6) |
| 11. Every keep, swap and remove is logged as feedback | Not found | No Suggestion Feedback model | Phase 6 |

### Chords and playback

| Check | Status | Evidence | What to fix |
|---|---|---|---|
| Chord sheets are required in a confirmed lineup, and allowed at any time | Not found | No Chord Sheet | Phase 7 |
| "Find chords": paste a chart, convert it to ChordPro, save it, approved at once | Not found | ChordSheetJS is not in `static/vendor/` | Phase 7 |
| A team member's paste is pending until the leader or pastor approves it | Not found | None | Phase 7 |
| Only the original ChordPro and key are stored; the service key is on the lineup item; transpose on load | Not found | None. The plan puts the service key on the Lineup Item (`Development-Plan.md:300-301`) | Phases 6 and 7 |
| Spotify-only playback: SDK for Premium users, embed otherwise; no automatic retry after a 429 | Not found | Only an "Open in Spotify" link (`apps/songs/templates/songs/song_detail.html:13`) | Phase 7 |
| No audio is stored | Pass | No audio fields, uploads or downloads anywhere | None |
| The lineup is saved as a playlist on confirmation, with a "Save to Spotify" fallback | Not found | None | Phase 7 (see F10) |

### Spotify safeguards

| Check | Status | Evidence | What to fix |
|---|---|---|---|
| Stop on the first 429 | Pass | `_call` records the limit and raises unless a short wait may be waited out once (`spotify.py:279-304`). Tested in `test_spotify_limits.py:74` | None |
| A shared "blocked until" time, checked by every process | Pass | `SpotifyLimit` rows (`songs/models.py:227-258`), checked before every call (`spotify.py:285-287`). The web views use the same client (`apps/songs/views.py:200`, `:228`). Tested in `test_spotify_limits.py:96` | None |
| Retry at most once, then fail the run | Pass | `spotify.py:299-304`; the run fails with the message (`suggesting.py:142-143`). Tested in `test_spotify_limits.py:132` | None |
| A Retry-After over one hour counts as a quota lockout | Pass | `spotify.py:181-182`. Tested in `test_spotify_limits.py:164` | None |
| QUOTA_EXCEEDED pauses Spotify, tells the leader, and ranks the pool | Pass | `spotify.py:178-180`; fallback in `suggesting.py:187-193`; message in the panel (`views/suggestions.py:68-70`). Tested in `test_suggesting.py:234` | None |
| One worker, enforced by an advisory lock | Pass | `locks.py:29-43`; `run_worker.py:46-51`. Tested in `test_suggesting.py:357` and `test_commands.py:44` | None |
| Never fetch a track already in the pool | Pass | `apps/songs/views.py:222-226`; the pipeline adds tracks from search results only (`apps/songs/pool.py:30-41`) | None (see F12) |
| No search-as-you-type | Pass | Find on Spotify searches only when the form is submitted (`spotify_search.html:11-14`) | None |
| Spotify calls and every 429 recorded on the run | Pass | `_record_spotify_usage` (`suggesting.py:216-226`); fields at `models/suggestions.py:192-199`; each 429 is logged (`spotify.py:191-196`) | None |

### Hard rules

| Check | Status | Evidence | What to fix |
|---|---|---|---|
| Spotify data, and any score it adjusts, is never ML input or training data | Pass | Engines receive only lyrics, theme text and tag labels (`analysis.py:184-201`, `phrases.py:71`, `suggesting.py:178-180`, `:229-236`). Titles and artists are used only outside models: version grouping (`versions.py:50-52`, `:81-88`) and sorting ties (`ranking.py:165`). There is no training yet | Phase 9 must keep the listed fields out |
| Lyrics never come from Spotify | Pass | LRCLIB only (`lyrics.py:21`); no Spotify lyrics endpoint anywhere (searched) | None |
| No Ultimate Guitar scraping or private API | Pass | No such code (searched) | Keep Phase 7 to pasting |
| No Recommendations, Audio Features or Audio Analysis | Pass | Only `/search`, `/tracks/{id}` and the token endpoint (`spotify.py:238-239`, `:246`, `:310-315`) | None |
| Stored Spotify data is limited to ID, title, artist, album and length | Pass | `songs/models.py:76-80`; `Track` holds only these (`spotify.py:78-102`) | None |
| Spotify tokens are stored encrypted and never shown or logged | Not found | No user tokens exist yet. The app token stays in memory (`spotify.py:218`, `:306-325`). The plan specifies Fernet with a key in `.env` (`Development-Plan.md:352-357`); `cryptography` isn't in `requirements.txt` yet | Phase 7 |
| A lineup is not visible to team members before it is confirmed | Partial | Suggestions are hidden and tested (see 9b). No Lineup exists yet | Phase 6 |

### Expected tables

| Check | Status | Evidence | What to fix |
|---|---|---|---|
| User | Pass | `accounts.User` (`apps/accounts/models.py`) | None |
| Spotify connection | Not found | None | Phase 7 |
| Service | Pass | `worship.WorshipService` (`models/schedule.py`) | None |
| Theme | Pass | `worship.Theme` (`models/schedule.py:147`) | None |
| Assignment | Not found | None | Phase 8 |
| Search run | Pass | `worship.SearchRun` (`models/suggestions.py:147`) | None |
| Song | Pass | `songs.Song` (`songs/models.py:59`) | None |
| Song tag (stored as `ThemeTag`, `Song.tags` and `Song.tag_scores`) | Pass | `songs/models.py:21-37`, `:119-124` | None |
| Song embedding (stored as `Song.embedding`, named by `analysed_with`) | Pass | `songs/models.py:125-126` | None |
| Lineup | Not found | None | Phase 6 |
| Lineup item | Not found | None | Phase 6 |
| Suggestion feedback | Not found | None | Phase 6 |
| Chord sheet | Not found | None | Phase 7 |
| Song usage | Not found | `ranking.song_usage()` is a placeholder (`ranking.py:56-62`) | Phase 6 (F3, F8) |
| Announcement | Not found | None | Phase 8 |
| Attendance (stored as `WorshipService.attendance`) | Pass | `models/schedule.py:107-109` and the `record_attendance` permission | None |

---

## 2. What is not part of this flow

None of these contradicts the flow. Most are supporting pieces that
`AGENTS.md` or [[Design-Decisions]] ask for.

- **Members module:** households, custom fields, membership statuses, and
  CSV import and export (`apps/members/`). The spec mentions it only through
  the optional Office Staff role. `AGENTS.md` keeps it as built.
- **Church setup:** the Church Profile, Modules that can be switched off,
  Labels, the setup wizard and the dashboard (`apps/church/`).
- **Audit trail** for services, themes, templates, songs and settings
  (`apps/audit/`).
- **Scheduling extras:** service templates with Song Slots, Schedule weeks
  ahead, the month calendar, rehearsal time, a cancelled flag, and sermon
  series.
- **Song library extras:** editing tags, feel and the worship check by
  hand; "the team knows it"; "Check again"; **Find on Spotify** to add one
  track without a theme (`apps/songs/views.py:180-247`); the `seed_hymns`
  and `download_models` commands.
- **Suggestion extras:** "Rank the song pool only" without Spotify; the
  worker works through missing lyrics and analysis between runs
  (`run_worker.py:78-95`); the church sets search genres, market, pages,
  weights, the repeat window and the number of songs kept
  (`models/suggestions.py:25-111`).
- **Theme notes hidden from team members:** only people who plan see them
  (`service_detail.html:35`, `views/base.py:66-70`).
- **Full lyrics on the song page** for holders of `songs.view_song`, with a
  copyright note (`song_detail.html:80-82`; see F13).
- **Plan items that the spec doesn't have:**
  - Phase 6: **sending a lineup back with notes**, and an **overused songs**
    report (see F2);
  - Phase 7: personal transpose, capo view, Nashville numbers, a
    practise-along toggle, and a key from a singer's range;
  - Phase 8: team parts and profiles, blackout dates and swap requests
    (`AGENTS.md` lists swaps as in scope);
  - Phase 9: a page showing both sets of weights.

---

## 3. The 3 most important fixes, in priority order

1. **Settle the lineup rules Phase 6 depends on, before building it**
   (F1, F2). The rules don't yet say:
   - whether reopening a lineup hides it from the team again;
   - whether a pastor's edit to an unconfirmed draft locks the leader out;
   - which permission counts as the pastor's final say, when Administrators
     hold every permission and one person can hold both roles;
   - whether "send back with notes" is a lineup state.

   Record the answers in Design-Decisions and the spec first.
2. **Build Lineup and Lineup Item as their own records, not views of a
   run's Suggestions** (F4, F5). Today a one-click correction re-places the
   whole run (`views/suggestions.py:99`). A "Not a worship song" anywhere
   also hides that song from every run (`suggesting.py:424`). Once lineups
   exist, neither may rearrange a lineup the leader edited, or change a
   confirmed one. Gate the lineup with a real permission, and test team
   visibility for every role, by page and by URL.
3. **Fill in `song_usage()` from confirmed lineups, and log Suggestion
   Feedback** (F3, F8). Familiarity and recent use (step 7) start working,
   and Phase 9 gets its training data (step 11).

---

## 4. Verdict

**Mostly follows the flow:** everything built so far (song selection steps
1 to 9 and every Spotify safeguard) matches the spec, no hard rule is
broken, and all checks pass. Review and confirmation, feedback, chords,
playback and seven expected tables are not built yet.

---

## 5. Findings by when to fix them

### Must fix before Phase 6

- **F1. Lineup states are underspecified.** Design-Decisions doesn't say:
  - whether a reopened lineup stays visible to the team;
  - whether a pastor's edit to an *unconfirmed* lineup locks the leader out
    (the text says "confirmed or edited");
  - which permission is the final say. Administrators hold every
    permission, so an Administrator's edit would also lock the leader out
    and read "Edited by pastor".

  `docs/CHORD-Vault/04-Development/Design-Decisions.md:152-155`.
- **F2. The plan's Phase 6 has items the spec and Design-Decisions don't:**
  "sending back with notes" (a new lineup state, which interacts with F1)
  and an "overused songs" report. Decide whether to keep them, then align
  the lower source. `docs/CHORD-Vault/04-Development/Development-Plan.md:303-304`, `:316`.

### Fix during Phase 6

- **F3.** `song_usage()` always returns `{}`, so the usage part of
  familiarity and the recent-use penalty are always 0.
  `apps/worship/ranking.py:56-62`.
- **F4.** Each one-click correction re-places the run's slots, and
  `results()` hides any song whose worship check later changes. A
  lineup built on Suggestions would be rearranged, or lose songs, after it
  was edited or confirmed. Lineup Items need their own rows, and
  corrections must leave edited or confirmed lineups alone.
  `apps/worship/views/suggestions.py:99`; `apps/worship/suggesting.py:376-395`, `:424`.
- **F5.** `can_plan` already checks `worship.change_lineup`, which no model
  declares yet. Phase 6 must declare that exact permission (or change
  `can_plan`) and keep it from team members. `apps/worship/views/base.py:69`.
- **F6.** "Edited by pastor" needs a church Label: there is no Label for the
  pastoral role, and the core rule requires Labels for wording that differs
  between churches. `apps/church/labels.py:19-44`.
- **F7.** Suggestions can be requested for a cancelled or past service;
  `request_run` checks only for a theme. Decide whether lineups for those
  can be confirmed. `apps/worship/suggesting.py:73-74`.
- **F8.** The spec lists Song usage as a table, but Design-Decisions computes
  it from confirmed lineups. Add it to the spec's "stored as" list once it
  is built. `docs/CHORD-Vault/workflow-spec.md:118-128`.

### Later

- **F9.** The cleanup filter misses plurals: "Piano Instrumentals" and
  "Backing Tracks Vol 1" get through. `apps/songs/cleanup.py:11-15`.
- **F10.** On a 429, a web request can wait up to 30 s before its one
  retry, as Find on Spotify does. Phase 7's "save as playlist on
  confirmation" must not make confirming wait like this.
  `apps/songs/spotify.py:46`, `:303`; `apps/songs/views.py:200`.
- **F11.** A lyrics lookup that failed (`FAILED`) is never retried
  automatically; only "Check again" retries it. `apps/songs/pool.py:56-57`;
  `apps/songs/models.py:52-53`.
- **F12.** Adding a track from Find on Spotify calls `/tracks/{id}` again,
  although the search has just returned that track: one extra Spotify call
  per add. `apps/songs/views.py:228`.
- **F13.** The song page shows full lyrics to anyone with `songs.view_song`.
  Phase 7 opens song pages to team members, so decide then whether they see
  the lyrics. `apps/songs/templates/songs/song_detail.html:80-82`.
- **F14.** The spec gives Admin "the Spotify connection", but
  Design-Decisions plans a connection per user (the leader's account for
  playlists, each user's for playback). Clarify the spec before Phase 7.
  `docs/CHORD-Vault/workflow-spec.md:17`.
