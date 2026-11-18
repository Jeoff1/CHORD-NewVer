# Workflow review: CHORD-NewVer against the workflow spec

Reviewed on 2026-11-18. This review only read the code. No tests or checks were run.

## What was reviewed

- **Spec:** `docs/CHORD-Vault/workflow-spec.md`. The request named `docs/workflow-spec.md`, but that file does not exist.
- **Code:** the newest code is in the worktree `.claude/worktrees/phase-4`, on branch `phase-5-song-suggestions`. It holds:
  - the Phase 4 commit `d81b354` (song pool), which is also on `master`;
  - **uncommitted Phase 5 work**: `apps/worship/models/suggestions.py`, `migrations/0003_suggestions.py`, `suggesting.py`, `phrases.py`, `ranking.py`, `sequencing.py`, `apps/songs/cleanup.py` and `management/commands/run_worker.py`.
  - Rows below marked "(uncommitted)" refer to that Phase 5 work.
- **Main checkout:** the main checkout is on branch `phase-4-song-pool` at the Phase 3 commit. It has one uncommitted change, in `apps/core/testing.py`. It is behind `master` and was not used for this review.
- **File paths** below are relative to the repository root. They point to the worktree's copy of the code.

**Status key:**

- **Pass:** built, and it matches the spec.
- **Partial:** built, but incomplete or slightly different.
- **Fail:** built in a way that contradicts the spec.
- **Not built yet:** no code exists.

"Plan" means `docs/CHORD-Vault/04-Development/Development-Plan.md`.

---

## 1. Hard rule violations

**No hard rule is violated.** I searched every branch and the uncommitted files. Nothing calls Spotify Recommendations, Audio Features, Audio Analysis, any Spotify lyrics endpoint (`spclient`, `color-lyrics`) or Ultimate Guitar. The Spotify client only calls `/search` and `/tracks/{id}` (`apps/songs/spotify.py:106`, `:113`).

Two hard rules need attention before later phases:

1. **Trusted Artist bonus (ambiguous; needs a decision).** The model only ever receives lyrics. However, the worship check adds `TRUSTED_ARTIST_BONUS = 0.25` when the Spotify artist name is on the church's Trusted Artists list (`apps/songs/analysis.py:235`, `:274-275` and `:302-309`). This causes two problems:
   - The Spotify artist name changes the classifier's accept or reject decision, which is spec step 6.
   - The bonus is saved into `Song.worship_score`. Phase 9 (learning to rank) could later train on that value, and Spotify data would then reach training data, which hard rule 1 forbids.

   The code comment says this is fine because the comparison happens "outside the engine". The spec does not say whether that is acceptable.
2. **Spotify token encryption is not in the plan.** Phase 7 of the plan adds a per-user "Spotify connection … with tokens refreshed as needed", but it never says the tokens are encrypted. `requirements.txt` has no encryption library, and `AGENTS.md` only says tokens are "never shown or logged". If the plan is built as written, it will break the hard rule.

---

## 2. Review table

### Roles

| Area | Check | Status | Evidence | What to fix or build next |
|---|---|---|---|---|
| Roles | Pastor schedules services | Pass | Role `pastoral_staff` has `worship.add_worshipservice` and `change_worshipservice` (`apps/accounts/roles.py:89-90`). Views: `ServiceCreateView` and `ScheduleAheadView` (`apps/worship/views/schedule.py:130`, `:241`) | None |
| Roles | Pastor posts the theme (title, scripture, sermon notes) | Pass | `Theme.title`, `scripture` and `notes` (`apps/worship/models/schedule.py:167-208`). `ThemeView` needs `worship.change_theme`, which `pastoral_staff` holds (`roles.py:91`) | None |
| Roles | Pastor can review, edit and confirm a lineup | Not built yet | No Lineup model or views exist (Plan Phase 6) | Build in Phase 6 |
| Roles | Pastor's decision is final | Not built yet | No confirmation logic exists | Phase 6: a pastor's confirmation locks out leader edits; test it for every role |
| Roles | Worship leader generates the suggested lineup | Partial (uncommitted) | The pipeline exists: `suggesting.request_run` and `execute` (`apps/worship/suggesting.py:57`, `:123`). However, no URL or view starts a run, the service page's `{% block planning %}` is empty (`service_detail.html:45`), and no default role holds `worship.suggest_songs` (`suggestions.py:183`; missing from `roles.py:103-119`) | Add a "Suggest songs" view and a progress panel. Grant `suggest_songs` and `view_searchrun` to `worship_leader` and `pastoral_staff` |
| Roles | Leader swaps, locks, reorders and re-keys songs | Not built yet | Not present (Plan Phase 6) | Build in Phase 6 |
| Roles | Leader confirms the lineup | Not built yet | Not present | Build in Phase 6 |
| Roles | Leader adds missing chord sheets | Not built yet | Not present (Plan Phase 7) | Build in Phase 7 |
| Roles | Team member sees a lineup only after confirmation | Not built yet | No lineup exists. `team_member` holds only `worship.view_worshipservice` (`roles.py:120-123`). Suggestions are not shown anywhere today | Phase 6. **Note:** `ServiceDetailView` is open to team members, so any suggestion panel added to that page must check `suggest_songs` |
| Roles | Team member plays songs and reads chord sheets | Not built yet | `team_member` has no `songs.view_song` | Phase 7: open song pages only for songs in confirmed lineups |
| Roles | Team member may paste a chord sheet for the leader to approve | Not built yet | Not present, and **not in the plan**: Phase 7 has no approval step | Add a pending-approval state to Chord Sheet in the Phase 7 plan |
| Roles | Admin manages users, roles and settings | Pass | `UserListView`, `UserCreateView`, `RoleListView`, `PermissionMatrixView` (`apps/accounts/views.py:119-319`); church settings in `ProfileSectionView` (`apps/church/views.py:53`) | None. The Administrator role can't be deleted, but the spec calls Admin "optional" (see ambiguities) |
| Roles | Admin manages the Spotify connection | Not built yet | The app's credentials come only from `.env` (`config/settings.py:157-158`). There is no per-user connection | Phase 7 |

### Song selection

| Area | Check | Status | Evidence | What to fix or build next |
|---|---|---|---|---|
| Song selection | 1. Pastor posts a theme | Pass | `Theme` model and `ThemeView` (see Roles). `request_run` refuses a service without a theme (`suggesting.py:60-61`) | None |
| Song selection | 2. Theme becomes several search phrases | Pass (uncommitted) | `search_phrases`: the short title, then KeyBERT-style phrases chosen with MMR (`apps/worship/phrases.py:60-90`). The number of phrases is `SuggestionSettings.phrases_per_theme` (default 4) | Add tests (none exist for `phrases.py`) |
| Song selection | 3a. Searches all of Spotify, 10 results per request, paging by offset | Pass | `PAGE_SIZE = 10`, `offset = page * PAGE_SIZE`, stops at 1000 (`apps/songs/spotify.py:22-23`, `:108-128`) | None. The default is 2 pages per phrase, set by `pages_per_phrase` |
| Song selection | 3b. A filtered search that finds nothing is retried without the genre | Pass | `search_tracks` reruns without `genre:` when nothing came back (`spotify.py:96-103`). Tested in `apps/songs/tests/test_clients.py` | None |
| Song selection | 4. Removes duplicates and live, karaoke and instrumental versions | Partial (uncommitted) | `clean_tracks` (`apps/songs/cleanup.py:156-171`) always drops karaoke, instrumental and backing tracks. A live version is dropped only when the plain version is also in the results; a live-only song is kept. Duplicate Spotify IDs are also blocked by the `one_song_per_spotify_track` constraint (`songs/models.py:119-125`) | Decide whether every live version must be dropped (see ambiguities). Add tests for `cleanup.py` |
| Song selection | 5a. Lyrics come from LRCLIB, one request at a time | Pass | `LrclibClient` makes one call at a time, with a 0.35 s gap and Retry-After handling (`apps/songs/lyrics.py:261-331`) | Caveat: this holds within one process only. `claim_next_run` uses `SKIP LOCKED` to allow several workers (`suggesting.py:78-94`), and `process_songs` can run alongside the worker. Either allow only one worker, or share a lock between processes |
| Song selection | 5b. Lyrics are cached; songs already in the pool skip the lookup | Pass | Lyrics are stored on `Song.lyrics`. Only `PENDING` songs are looked up (`suggesting.py:220`, `pool.py:95`) | None |
| Song selection | 5c. Songs with no lyrics are set aside | Pass | Only `FOUND` songs are analysed (`analysis.py:315`), and only analysed, accepted songs are ranked (`suggesting.py:251-256`) | None |
| Song selection | 6. A classifier drops non-worship songs and suggests theme tags | Pass (see hard rule note) | Zero-shot worship check and tag scores on the lyrics (`analysis.py:267-299`). ONNX engine in `apps/songs/ml/onnx.py`. People's corrections are kept (`analysis.py:341-349`) | Resolve the Trusted Artist bonus (hard rule note 1) |
| Song selection | 7a. Ranking by embedding similarity between theme and lyrics | Pass (uncommitted) | `cosine(theme_vector, song.embedding)`, scaled from 0 to 1 (`apps/worship/ranking.py:186-198`) | Add tests |
| Song selection | 7b. Familiarity (past usage) | Partial | `familiarity()` uses `team_knows` plus the usage count, but `song_usage()` always returns `{}` (`ranking.py:133-139`). As a result, the past-usage part is always 0 | Phase 6: work out usage from confirmed lineups |
| Song selection | 7c. Season fit | Pass (uncommitted) | `Season.contains()` and the season tags (`suggestions.py:103-133`, `ranking.py:189-200`) | Add tests |
| Song selection | 7d. Penalty for recent use | Partial | `recency()` is implemented (`ranking.py:152-158`), but it always returns 0 because there is no usage data | Same as 7b |
| Song selection | 8. Top songs go into service slots (opener, praise, worship, response) | Pass (uncommitted) | `sequencing.place` fills slots by feel (`apps/worship/sequencing.py:352-381`). The default slots are Opening, Praise, Worship and Response (`worship/migrations/0002_seed_default_template.py:7-12`). Churches can change them | Add tests |
| Song selection | 9. Each suggestion stores why it was picked | Pass (uncommitted) | `Suggestion.reasons` (`suggestions.py:231`), filled from `ranking.py:209-224` plus the slot reason (`suggesting.py:279-281`) | Show the reasons in the review UI |
| Song selection | 10. Leader reviews; leader or pastor confirms; the pastor's decision wins | Not built yet | No review UI, Lineup or confirmation exists (Plan Phase 6) | Build in Phase 6 |
| Song selection | 11. Every keep, swap and remove is logged as feedback | Not built yet | No Suggestion Feedback model exists (Plan Phase 6) | Build in Phase 6 |

### Chords and playback

| Area | Check | Status | Evidence | What to fix or build next |
|---|---|---|---|---|
| Chords | Chord sheets are added only for songs in a confirmed lineup | Not built yet | No Chord Sheet model exists. The Phase 7 plan does not include this restriction | Add the rule to the Phase 7 plan |
| Chords | "Find chords": paste a chart, convert it to ChordPro (ChordSheetJS), save it for reuse | Not built yet | ChordSheetJS is not in `static/vendor/` (only Bootstrap and htmx are) | Phase 7 |
| Chords | Store only the original ChordPro text and key; the service key is on the lineup item; transpose when the page loads | Not built yet | Not present. The plan puts the service key on the Lineup Item (Phase 6), which matches the spec | Phases 6 and 7 |
| Playback | Spotify only: Web Playback SDK for Premium users, embedded player otherwise | Not built yet | Only an "Open in Spotify" link exists (`songs/templates/songs/song_detail.html:13`) | Phase 7 |
| Playback | No audio is stored | Pass | No audio fields, uploads or downloads exist anywhere | None |
| Playback | A confirmed lineup can be saved as a Spotify playlist | Not built yet | Not present | Phase 7 |

### Hard rules

| Area | Check | Status | Evidence | What to fix or build next |
|---|---|---|---|---|
| Hard rule | Spotify data is never ML input or training data | Partial (ambiguous) | The engines only receive lyrics, theme text and tag labels (`analysis.py:270-298`, `phrases.py:71`, `suggesting.py:161-163`). Ranking reads embeddings and church data; the song title is used only to break ties when sorting (`ranking.py:235`). **But** the Trusted Artist bonus feeds the Spotify artist name into the worship decision and into the stored `worship_score` | Get a decision on this, then keep the raw model score separate from any artist-based adjustment |
| Hard rule | Lyrics never come from Spotify | Pass | Lyrics come only from `lrclib.net` (`lyrics.py:214`). No Spotify lyrics endpoints anywhere | None |
| Hard rule | No Ultimate Guitar scraping or private API | Pass | No such code on any branch. The plan only describes pasting text | Keep it to pasting in Phase 7 |
| Hard rule | No Recommendations, Audio Features or Audio Analysis endpoints | Pass | Only `/search`, `/tracks/{id}` and the token endpoint are called (`spotify.py:20-21`, `:106`, `:113`). `Feel` is guessed from the lyrics instead (`apps/core/music.py`) | None |
| Hard rule | Stored Spotify data is limited to track ID, title, artist, album and length | Pass | `Song.spotify_id`, `title`, `artist`, `album`, `length_seconds` (`songs/models.py:75-79`). The `Track` data class keeps only these (`spotify.py:36-60`) | None |
| Hard rule | Spotify tokens are stored encrypted | Not built yet | The app token is kept in memory only, never in the database (`spotify.py:87`, `:172`). Per-user tokens don't exist yet. The plan does not mention encryption | Add encryption (key from `.env`) to the Phase 7 plan before building it |
| Hard rule | A lineup is not visible to team members before it is confirmed | Not built yet | No lineup exists, and suggestions are not shown anywhere | Phase 6: gate the data, and test it for every role |

### Expected database tables

| Area | Check | Status | Evidence | What to fix or build next |
|---|---|---|---|---|
| Tables | User | Pass | `accounts.User` (`apps/accounts/models.py:5`) | None |
| Tables | Spotify connection | Not built yet | None | Phase 7, with encrypted tokens |
| Tables | Service | Pass | `worship.WorshipService` (`schedule.py:115`) | None |
| Tables | Theme | Pass | `worship.Theme`, one per service (`schedule.py:167`) | None |
| Tables | Assignment | Not built yet | None. The `teams` module is registered, but no app exists (`apps/church/modules.py:46-52`) | Phase 8 |
| Tables | Search run | Pass (uncommitted) | `worship.SearchRun` (`suggestions.py:136`, migration `0003_suggestions.py`) | Commit it once tested |
| Tables | Song | Pass | `songs.Song` (`songs/models.py:58`) | None |
| Tables | Song tag | Pass | `songs.ThemeTag` plus the `Song.tags` many-to-many table. Per-tag scores are in the JSON field `Song.tag_scores` | None |
| Tables | Song embedding | Partial | Stored as the JSON field `Song.embedding`, with `analysed_with` naming the engine (`songs/models.py:100-101`). There is no separate table | Decide whether a separate table is needed (see ambiguities) |
| Tables | Lineup | Not built yet | None | Phase 6 |
| Tables | Lineup item | Not built yet | None | Phase 6 (service key, lock, reason) |
| Tables | Suggestion feedback | Not built yet | None | Phase 6 |
| Tables | Chord sheet | Not built yet | None | Phase 7 |
| Tables | Song usage | Not built yet | `ranking.song_usage()` is a placeholder that returns `{}` | Phase 6: a table, or a query over confirmed lineups |
| Tables | Announcement | Not built yet | The module is registered (`modules.py:53-58`), but no app exists | Phase 8 |
| Tables | Attendance | Partial | A headcount field, `WorshipService.attendance`, with the `record_attendance` permission (`schedule.py:127-139`). There is no separate table | Decide whether the spec means a headcount or attendance per person |

---

## 3. Code that is not in the spec

These items are extra; none of them contradicts the workflow.

- **Members module (Phase 2):** `Member`, `Household`, `MembershipStatus`, `RelationshipType`, `MemberField`, and CSV import and export (`apps/members/`). It has an **Office Staff** role to match. Neither the module nor the role appears in the workflow spec.
- **Church setup:** `ChurchProfile`, modules that can be switched on and off, and church-chosen labels (`apps/church/`). Custom fields (`apps/core/custom_fields.py`).
- **Audit trail:** `audit.AuditEvent` records changes to services, themes, templates and songs.
- **Supporting tables the spec doesn't list:**
  - `ServiceTemplate` and `TemplateSlot` (the slots are set per church, not fixed);
  - `SermonSeries`, `Season`, `SuggestionSettings` (the ranking weights the church sets);
  - `Suggestion`, `TrustedArtist`.
- **Song pool extras:**
  - people can override the worship check, tags and feel (`reviewed_at`, `reviewed_by`);
  - a `team_knows` flag feeds familiarity;
  - `feel` is guessed from the lyrics;
  - a "Check again" action;
  - a manual **Find on Spotify** page that adds single tracks without searching from a theme (`apps/songs/views.py:163-219`).
- **Pipeline extras:**
  - `use_spotify = False` ranks only the songs already in the pool;
  - the worker fills in missing lyrics and analysis between runs (`run_worker.py:59-62`);
  - the pipeline scores each theme against the theme tags.
- **Ranking scope:** step 7 ranks **every accepted song in the pool**, not just the songs this run found (`suggesting.py:251-256`). This may or may not be what the spec intends (see ambiguities).
- **Theme notes are hidden from team members.** Only users who can plan see them (`views/base.py:59-63`, `service_detail.html:35`).
- **Full lyrics are shown on the song page** to anyone with `songs.view_song` (`song_detail.html`). The page includes a copyright notice.
- **The Administrator role can't be deleted** and always holds every permission (`roles.py:164-171`). The spec calls Admin "optional".
- **Plan extras not in the spec:**
  - Phase 7: personal transpose, capo view, Nashville numbers, a key from a singer's range, and an "Open in Spotify" fallback;
  - Phase 8: team parts, blackout dates and swap requests;
  - Phase 6: reports, with CSV export.

---

## 4. Ambiguities in the spec

1. **Trusted Artist bonus.** Does hard rule 1 forbid only putting Spotify data *into the model*? Or does it also forbid using the artist name to adjust the classifier's result (step 6)?
2. **Theme text as model input.** The spec says "the model uses only LRCLIB lyrics and tags". But step 7 needs the theme text embedded as well, and the code also embeds it to pick search phrases. Should the rule read "lyrics, theme text and tags"?
3. **Live versions (step 4).** Should every live version be dropped, or only live copies of a song whose plain version was also found? The code does the second.
4. **What gets ranked (step 7).** Only the songs this run found, or the whole pool? The code ranks the whole pool.
5. **Separate tables.** Does the spec require separate tables for Song embedding, Song tag, Song usage and Attendance? Or are equivalent fields enough?
6. **Attendance.** A headcount per service (what the code stores), or a record per person?
7. **"Admin (optional)".** Optional as a role, or optional as a feature? The code requires an undeletable Administrator role.
8. **Chord sheets "only for songs in a confirmed lineup".** Does this stop a leader from adding a sheet to a song in the library ahead of time? And who approves a team member's pasted sheet: the leader only, or also the pastor?
9. **Pastor's decision is final.** If the leader confirms first and the pastor edits afterwards, does the lineup become unconfirmed? The plan says "a final decision locks out everyone without that permission", which is only one possible reading.
10. **Report format.** The spec has its own "What to produce" section, which uses "Not found" as a status and asks for 3 fixes. This report follows the request instead: "Not built yet" as a status, and 5 next steps.

---

## 5. Next 5 things to build or fix, in priority order

1. **Finish and secure Phase 5 before committing it.**
   - Add tests for `suggesting.py`, `ranking.py`, `phrases.py`, `sequencing.py` and `cleanup.py`. None exist yet.
   - Add the "Suggest songs" view and the progress panel.
   - Grant `worship.suggest_songs` and `view_searchrun` to `worship_leader` and `pastoral_staff`.
   - Add a test proving a team member cannot see suggestions on the service page.
2. **Decide on the Trusted Artist bonus** and record the decision.
   - If it stays: store the raw model score separately from the artist adjustment, so Phase 9 never trains on Spotify-derived values.
   - If it goes: remove `TRUSTED_ARTIST_BONUS`, and let people's reviews do that job.
3. **Phase 6: Lineup and Lineup Item, with confirmation.**
   - Include the service key, a lock, the reason for each song, and swap, reorder and remove.
   - The pastor's decision is final.
   - Team members can see a lineup only after it is confirmed.
   - Test the rules for every role.
4. **Phase 6: Suggestion Feedback and song usage.**
   - Log every keep, swap and remove.
   - Fill in `ranking.song_usage()` from confirmed lineups, so the familiarity and recent-use parts of ranking start working.
5. **Fix the Phase 7 plan before building it.**
   - Encrypt Spotify tokens (key from `.env`; add the encryption library).
   - Allow chord sheets only for songs in confirmed lineups.
   - Add a team member paste with leader approval.
   - Then build Chord Sheet, the ChordSheetJS paste conversion, transposing when the page loads, and Spotify playback with a fallback.

---

## 6. Verdict

**Mostly follows the design.** Everything built so far matches the spec and no hard rule is broken. The review and confirmation half of the workflow (lineups, feedback, chords, playback) is not built yet, and the Trusted Artist bonus and token encryption need decisions first.
