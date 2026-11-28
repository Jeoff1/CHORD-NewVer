# Design decisions and safeguards for CHORD

**For Claude Code:** read this file before starting any development phase. Each section says which phase it applies to. When you start that phase, build what the section describes and add the listed tests. Don't build items for a later phase early.

Sources rank in this order (`AGENTS.md`): the rules in `AGENTS.md`, the numbered decision records, this file, `docs/CHORD-Vault/01-Project/Concept-Brief.md`, `docs/CHORD-Vault/workflow-spec.md`, then `docs/CHORD-Vault/04-Development/Development-Plan.md`. If this file disagrees with the Concept Brief, the spec or the plan, this file wins. Update the lower source to match, and say so in your summary.

These decisions answer the open questions in `docs/workflow-review.md`, section 4, and the findings of the [[2026-11-19-Workflow-Review]] that needed a decision.

---

## Phase 5: song suggestions (done 2026-11-18)

### Trusted Artist bonus (review question 1)

Decision: keep the Trusted Artist list, but separate it from the model.

- Store the classifier's raw worship score in its own field, for example `Song.worship_model_score`. Only lyrics may affect this value.
- Apply `TRUSTED_ARTIST_BONUS` as a separate, church-owned rule after the model runs. Store the adjusted result in a different field, for example `Song.worship_score`, or compute it when needed.
- The Spotify artist name must never be passed to any ML engine.
- Add a code comment at the bonus explaining that it is a church rule, not model input, and that it must never be used as a training feature (see Phase 9).

If the project owner later decides to remove the bonus instead: delete `TRUSTED_ARTIST_BONUS` and its fields, and let manual reviews handle trusted artists.

Tests:
- The raw model score is the same whether or not the artist is on the Trusted Artist list.
- The adjusted score includes the bonus only for listed artists.

### Theme text as model input (question 2)

Decision: the model may use lyrics, theme text and tags. The theme is the pastor's own text, not Spotify data.

- Update hard rule 1 in the spec to read: "The model uses only LRCLIB lyrics, the church's theme text, and tags."

### Live versions (question 3)

Decision: keep the current behaviour. Drop a live version only when the plain version is also in the results. Many worship songs are released only as live recordings.

- Update spec step 4 to say this.
- Tests for `apps/songs/cleanup.py`: a live-only song is kept; a live duplicate of a studio song is dropped; karaoke, instrumental and backing tracks are always dropped.

### What gets ranked (question 4)

Decision: rank every accepted song in the pool, not only the songs this run found. The pool is meant to grow over time.

- Update spec step 7 to say this.

### Separate tables vs fields (question 5)

Decision: equivalent fields are acceptable. No new tables are needed for Song embedding, Song tag scores or Attendance.

- Update the spec's table list to say "stored as" with the actual model and field names, for example "Song embedding: stored as `Song.embedding` (JSON)".
- JSON embeddings are fine at this project's scale. Only consider pgvector if the pool grows past several thousand songs.

### Suggestions are hidden from team members

- Any "Suggest songs" panel or suggestion list on the service page must check the `worship.suggest_songs` permission.
- Grant `worship.suggest_songs` and `worship.view_searchrun` to `worship_leader` and `pastoral_staff` only.

Test: a team member viewing the service page sees no suggestions and cannot reach any suggestion URL.

### Spotify safeguards

Spotify limits calls in two ways, and doesn't publish the numbers:

- **Rate limit:** calls are counted in a rolling 30-second window. Going over returns HTTP 429 with a `Retry-After` header.
- **Quota:** counted per developer account and shared across all of that account's Development Mode apps. Going over returns HTTP 429 with `"reason": "QUOTA_EXCEEDED"` in the JSON body.

Developers report lockouts of 13 to 48 hours in Development Mode, especially when an app keeps calling after the first 429. Build these rules into `apps/songs/spotify.py`:

1. **Stop on the first 429.** Don't make another Spotify call until the `Retry-After` time has passed.
2. **Share the wait across processes.** Save a "Spotify blocked until" time in the database or cache, and check it before every Spotify call. The worker and web requests must all respect it.
3. **Never retry in a loop.** After waiting, retry a request at most once. If it fails again, give up and mark the search run as failed.
4. **Handle long waits.** If `Retry-After` is more than one hour, treat it like a quota lockout (rule 5).
5. **Handle `QUOTA_EXCEEDED`.** Pause all Spotify calls and save the pause. Show the worship leader a clear message. Fall back to ranking only songs already in the pool (`use_spotify = False`), so suggestions still work.
6. **Run one worker only.** Enforce it with a PostgreSQL advisory lock that the worker takes at startup: a second worker that can't take the lock refuses to start, with a clear message. Keep `claim_next_run` as it is. Document this in `AGENTS.md` and in `run_worker.py`. This also keeps LRCLIB to one request at a time across processes.
7. **Cache everything.** Never fetch a track already stored in the pool.
8. **No search-as-you-type.** On the "Find on Spotify" page, search only when the user submits the form.
9. **Log usage.** Record the number of Spotify calls on each `SearchRun`, and record every 429 with its reason and `Retry-After` value.

Tests, with Spotify mocked:
- A 429 stops the run, and no further Spotify calls are made before `Retry-After` passes.
- The blocked-until time is respected by a second process or request.
- A request is retried at most once.
- `QUOTA_EXCEEDED` pauses Spotify, shows the message, and the run falls back to ranking the existing pool.
- A `Retry-After` over one hour is treated like a quota lockout.
- A second worker refuses to start while the first holds the advisory lock.

### Notes to update with the Phase 5 code

When the code above changes, update the [[Worship]] module note, [[0006-onnx-runtime-for-song-analysis]] and the [[Glossary]] (Worship Check, Trusted Artist) to match.

---

## Phase 5 follow-up: smoke test fixes (done 2026-11-18)

Agreed after the first live smoke test, with the seeded hymns and with Spotify.

### Match labels and relevance on a fixed scale

- Relevance is the theme-to-lyrics similarity on a fixed scale set by the engine (`similarity_range`; for all-MiniLM-L6-v2, 0.20 maps to 0 and 0.60 to 1), not rescaled per run. The same similarity always gets the same relevance and label, whatever else is in the pool.
- Labels: similarity 0.50 or more "closely", 0.40 "fairly well", 0.30 "a little", below 0.30 "doesn't match the theme well".
- Default weights recalibrated for the new scale: familiarity 0.3 → 0.2, season 0.2 → 0.15, recent use 0.4 → 0.3 (the old per-run scaling stretched about 0.27 of similarity to 0–1, the fixed scale 0.40). A church still on the old defaults moves to the new ones; weights a church chose stay.

Tests: relevance is fixed and clipped; the same match gets the same relevance in any pool; each label's threshold; the new defaults.

### Theme notes

- Notes are not required. The suggestions panel shows a hint when the theme has none.

Test: the hint shows without notes and goes with them.

### Feel

- Placement treats feel as a preference: a song in a slot of another feel loses the church's **feel mismatch weight** (default 0.15) for each step between upbeat, mid-tempo and slow. Placement is best first. A slot without a feel costs nothing. A song whose feel isn't known costs half a step (0.075 with the default weight) in a slot that asks for a feel, so an unknown feel never beats a known close match (decided after the before-and-after comparison, 2026-11-18).
- The analysis leaves feel blank when unsure: the best feel must score at least 0.5 and beat the next by 0.2.
- One-click feel correction in the suggestions panel. A feel a person set is kept when the song is analysed again; the lineup is placed again at once.
- Words per minute from LRCLIB's timed lyrics, as a tempo signal: a future experiment (Development Plan), not built.

Tests: a close song of a near feel beats a weak song of the right feel; each step costs the weight; an unknown feel costs half a step, says so, and never beats a known close match; feel left blank when unsure; a feel a person set is kept; the one-click correction re-places, is audited, and needs both permissions.

### Worship check

- The pass mark (default 0.5) is a church setting (Settings → Worship check). Changing it decides the check again for every song nobody has reviewed, from the stored model score; no model runs.
- **Rule for artists not on the Trusted Artists list** (choice (c)): off by default. A church may choose that artists not on the list need a stricter pass mark (default 0.9), or that their songs wait for a person's review ("Not checked"). It is a church rule applied **after** the model, like the Trusted Artist bonus: the artist name is compared with the list outside any engine, never reaches the model, and is never a training feature (see Phase 9). Changing the list or the rule decides the check again for songs nobody has reviewed.
- One-click "Not a worship song" in the suggestions panel (choice (d)): the song counts as Reviewed, leaves the lineup, and isn't suggested again.
- Each Search Run records which searches found nothing in the genre and ran again without it (choice (e)). This is information only, shown in "About this search", and is never used in any decision about a song.

Tests: the pass mark decides; the stricter and review rules; off by default; rechecking without a model, keeping reviewed songs; a Trusted Artist change rechecks; the settings page and its permissions; "Not a worship song" leaves the lineup; searches are recorded and a song found without the genre is treated like any other.

### Versions of one song

- After ranking, versions of one song are grouped: lyrics similarity at least 0.90 with titles that begin the same way, or at least 0.95 whatever the titles. One version is kept: the one the team knows, then one a person reviewed, then one by a Trusted Artist, then the best scored. Its reasons name the other versions. The pool keeps every version.
- Placement never puts two songs with the same base title in one lineup.

Tests: versions grouped by lyrics and titles; different titles need nearly the same lyrics; the same title with other lyrics is another song; the preference order; a run keeps one version; one title once per lineup.

### Theme tags (measured; today's rule kept)

- Including a "neutral" class in the tag score can't help: the zero-shot model (deberta-v3-xsmall-zeroshot-v1.1-all-33) has only two classes, entailment and not entailment, so the score already uses all of them. Measured on the 23 seeded hymns and carols: identical tags, 12.5 tags over 0.5 per song either way.
- Then measured (2026-11-18), aiming for 3 to 5 sensible tags per song:
  - (a) tags that stand out from the song's own scores: on probabilities, nearly today's tags; on the model's margins (entailment logit minus not-entailment logit), at mean + 1.0 sd almost today's tags (Faith on 18 of 23 hymns), at mean + 1.25 sd too few (Christ the Lord Is Risen Today keeps only Faith);
  - (a) against each tag's own average margin over the pool (so an always-on tag like Faith must stand out): at z ≥ 0.5, 4.1 tags per song, Faith on 2 of 23, and the first tags usually right (Abide with Me: Trust, Surrender, Comfort, Guidance; Christ the Lord Is Risen Today: Resurrection, Joy), but a noisy tail (Blessed Assurance still gets Birth of Jesus and Resurrection);
  - (c) embedding similarity between lyrics and each tag's name and keywords: 2.3 to 3.4 tags per song, and it misses obvious tags (Silent Night without Birth of Jesus, the Easter hymn without Resurrection).
- Decision (2026-11-18): keep today's rule (tags scoring 0.5 or more, best four). "(a) against each tag's average" makes a song's tags depend on the rest of the pool, which brings back the relative-score problem the fixed relevance scale just removed, and it wrongly gave Christ the Lord Is Risen Today "Birth of Jesus". It is a future experiment in the Development Plan, to revisit when the pool is larger.

---

## Phase 6: lineups and confirmation (done 2026-11-19)

The rules below were completed on 2026-11-19 from the [[2026-11-19-Workflow-Review]] (findings F1, F2, F6 and F8).

### The final say is a permission (question 9; review F1c, F6)

- A dedicated permission, `worship.finalize_lineup`, gives the final say on lineups. The Pastoral Staff role holds it by default. The Administrator also holds it, as it holds every permission. Code checks this permission, never a role name ([[0008-final-say-permission]]).
- In these rules, **the pastor** means anyone who holds `worship.finalize_lineup`. The pastor's lock (below) stops only people without it; a holder is never locked out.
- A new church Label, `pastor` (default "Pastor"), names the pastoral role in UI text.

### Confirming, editing and the pastor's lock (review F1a, F1b)

A lineup is either a **draft** or **confirmed**. There is no other state.

- Either the worship leader or the pastor can confirm a lineup.
- The pastor's edits to a draft don't lock the worship leader out.
- The **pastor's lock** starts when the pastor confirms a lineup, or edits a lineup that is already confirmed. While it holds, the worship leader can't change the lineup. It lasts until the pastor reopens the lineup.
- If the pastor edits a confirmed lineup, it stays confirmed. It is marked "Edited by <pastor Label> (<person's name>)" with the time, for example "Edited by Pastor (Ana Cruz), Nov 22, 3:15 PM". Everyone who can see the lineup sees the mark. Phase 6 has no notification system; Phase 8 adds notifications (see below).
- If the worship leader edits a confirmed lineup that isn't under the pastor's lock (decided 2026-11-19, after part A), it stays confirmed and is marked "Changed by <person's name>" with the time, shown to everyone who can see the lineup. There is no lock.
- **Only the latest mark shows.** A later pastor's edit replaces a "Changed by" mark with the "Edited by <pastor Label> (<name>)" mark. Edits to a draft leave no mark.
- **Locking or unlocking a song isn't an edit:** it leaves no mark and puts on no lock.
- **Reopening:** the pastor can reopen a lineup. A reopened lineup counts as unconfirmed: it is a draft again, and the pastor's lock and the mark are cleared. Team members can't see it. Instead they see a note that the lineup is being revised, until it is confirmed again.
- **Sending back** (review F2) adds no state. Only the pastor can send a lineup back. It returns to draft, with a note for the worship leader. Sending back a confirmed lineup therefore reopens it, and the reopening rules apply. Confirming the lineup again clears the note.
- Team members see a lineup only once it is confirmed. A team member who opens a draft that was never confirmed gets "not found" (404).

### Approved after part A (2026-11-19)

The project owner approved these choices made while building part A:

- **Default permissions** come from `DEFAULT_ROLE_PERMISSIONS` in `apps/accounts/roles.py`, which the post_migrate sync grants on every `migrate`, not from a data migration. Permission rows don't exist while migrations run.
- **Who has which lineup permission by default:**
  - Worship Leader: view, save the suggestions as the lineup (`add_lineup`), and change;
  - Pastoral Staff: the same, plus the final say;
  - Team Member: view (confirmed lineups only);
  - Office Staff: none, so they can't see lineups.
- **Who sees theme notes:** people who can change lineups (`change_lineup`) or themes. Worship leaders therefore see the theme's notes; team members don't (review F5).
- **A locked song** can't be swapped, moved or removed, and no other song can move into its place, until it is unlocked.
- **Cancelled and past services:** a cancelled service's lineup can't be confirmed. A past service's lineup can still be edited and confirmed, for example to record what was actually sung.
- **Swap and regenerate** use the service's latest finished Search Run, which may be newer than the one the lineup was made from.

### Adding a song from the pool (decided 2026-11-19, after part A)

- Any song in the pool can be added, unless a person marked it "Not a worship song". The person's choice wins over the model.
- A song that failed the Worship Check, or was never checked (for example because LRCLIB had no lyrics), can be added. It shows a small warning in the review, for the people who plan; the team doesn't see the warning.

Tests: an unchecked song and a failed song can be added and show the warning; a song a person marked "Not a worship song" can't be added.

Tests, for every role:
- The leader can confirm; so can the pastor.
- The pastor's edits to a draft leave the leader free to edit it.
- The pastor's confirmation puts on the pastor's lock, and so does the pastor's edit to a lineup the leader confirmed. That edit keeps the lineup confirmed and marks it "Edited by <pastor Label> (<person's name>)" with the time, and everyone who can see the lineup sees the mark.
- The mark uses the church's `pastor` Label.
- The leader's edit to a confirmed lineup without the pastor's lock keeps it confirmed and shows "Changed by <name>" with the time to everyone who can see it, team members included, with no lock. A later pastor's edit replaces that mark, and reopening or sending back clears it. Locking or unlocking a song leaves no mark.
- The leader is blocked while the pastor's lock holds.
- Reopening by the pastor lifts the lock and makes the lineup a draft: team members see the "being revised" note, not the songs.
- Sending back returns the lineup to draft, and the leader sees the note. Someone without `worship.finalize_lineup` can't send a lineup back.
- The final say follows the permission, not the role: a user with `worship.finalize_lineup` but without the Pastoral Staff role has it; a Pastoral Staff user whose role lost the permission doesn't.
- A team member cannot see an unconfirmed lineup, by page or by URL.

### Song usage (review F8; approved after part B, 2026-11-19)

- Fill in `ranking.song_usage()` from confirmed lineups, so the familiarity and recent-use parts of ranking start working.
- Song usage is computed from confirmed lineups when needed. It is not stored in a table of its own. Lineups of cancelled services never count.
- **Ranking** counts every confirmed lineup of a service that starts before the one being ranked, even one that hasn't taken place yet, so next week's songs are held back when the week after is planned.
- **The song usage report** counts only services that have already taken place: what was actually sung.

Tests: only confirmed lineups of earlier services count (not drafts, cancelled services or later services); ranking changes once a lineup is confirmed; the report matches the confirmed lineups of services held.

### Suggestion Feedback (approved after part B, 2026-11-19)

Every suggestion placed in a lineup gets one label, followed during review and recorded when the lineup is confirmed:

- **kept**: placed when the lineup was made or regenerated, and still in it;
- **swapped in**: an alternative the leader chose in a swap, still in the lineup. It is a positive, like kept, but told apart from a top pick that stayed, so Phase 9 can learn from both;
- **swapped**: replaced by a swap;
- **removed**: taken out. A song labelled kept or swapped in that is no longer in the lineup counts as removed.

- Songs that regenerating replaces leave no feedback: no person turned them down. Songs added from the pool weren't suggested, so they leave none either.
- Confirming again (after reopening or sending back) replaces the earlier feedback, so it always matches the lineup as last confirmed.
- The rows hold only the features Phase 9 may train on (`SuggestionFeedback.FEATURES`): lyrics-based scores and the church's own data. Never a Spotify field, the Trusted Artist bonus or any score that includes it, which version of a song was kept, the reasons, or the genre-filter record.

Tests: each label, including a swapped-in song later swapped out or removed; regenerate and pool songs leave none; confirming again replaces the rows; the stored fields and the feature list hold none of the forbidden fields.

### Reports (approved after part B, 2026-11-19)

- **Song usage** needs a new permission, `worship.view_song_usage`, held by Worship Leader and Pastoral Staff by default.
- **Attendance** reuses `worship.record_attendance` (Pastoral Staff and Office Staff by default), so worship leaders don't see it by default.

### Click-through fixes (decided 2026-11-19, after part A)

- **A lineup song's feel reason follows its slot.** A lineup song keeps only its theme reasons (match, tags, other versions); the feel reason is worked out for the slot it is in now, after any move, swap, add or regenerate, so it never names another slot's feel.
- **People are named by their full name**, or their username when they have none, wherever text says who did something: "Confirmed by", the Mark, "Sent back by", "Asked for … by", "Reviewed by".
- **No nested brackets in text.** Songs are listed as "Title, Artist", separated by semicolons, because artist names may hold brackets, such as "Charles Wesley (1739)".
- **Move arrows show only where the move is allowed.** No ↑ or ↓ next to a locked song's place, or past either end. The server still refuses those moves, worded for the song being moved: "Hark! The Herald Angels Sing can't move into a locked song's place."

Tests: a moved song's reason names its new slot's feel; full names with the username fallback; the versions reason without nested brackets; arrows hidden where refused, and the refused move still blocked on the server.

### Feel reason wording (decided 2026-11-19, part B)

- A song placed in a slot of another feel reads "Its feel (upbeat) doesn't match this slot, which asks for slow, but it fit best.", so it reads naturally for every feel.

### Song usage report: overused songs (review F2)

- There is no separate overused-songs report. The song usage report highlights songs used more often than the recent-use window allows (the repeat window in Suggestion Settings).
- "More often than the window allows" means sung again sooner than the repeat window (approved after part B). With the default of 4 weeks, a song sung 3 weeks apart is highlighted; one sung exactly 4 weeks apart isn't. A repeat window of 0 highlights nothing.

Test: a song sung again within the repeat window is highlighted in the report; a song sung once is not; exactly the window apart is not.

---

## Phase 7: chord sheets and playback

### When chord sheets can be added (question 8)

- Chord sheets are **required** only for songs in a confirmed lineup, but are **allowed** at any time. A worship leader can add a sheet to any song in the pool ahead of time.
- A team member may paste a chord sheet for a song in a confirmed lineup. It is saved as "pending" and must be approved by the worship leader or the pastor before the team sees it.
- A sheet added by the worship leader or the pastor is approved immediately.

Tests: a team member's paste is pending; the leader or pastor can approve it; other team members can't see a pending sheet.

### Spotify token encryption

- Encrypt each user's Spotify access and refresh tokens before saving them. Use Fernet from the `cryptography` library, with the key read from `.env` (for example `SPOTIFY_TOKEN_KEY`).
- Add `cryptography` to `requirements.txt`, and add the new key to `.env.example`.
- Never show or log tokens, encrypted or not.

Test: the stored token value in the database is not the plain token, and decrypts back to it.

### Saving the lineup as a Spotify playlist

(Changed on 2026-11-22: first "on the worship leader's account"; now as below, with the Church Spotify Account.)

- When a lineup is confirmed, it is saved automatically as its **Lineup Playlist**: on the Church Spotify Account when one is connected (below), otherwise on the Spotify account of the person who confirmed it (the worship leader, or the pastor when the pastor confirms).
- If there is no usable account (no connection, a refusal), or Spotify returns a 429, the playlist is skipped and the lineup page shows a "Save to Spotify" button to people who may save, to try again later. Confirming the lineup never fails because of Spotify.

Tests: confirming saves the playlist when the leader is connected; with no connection, or on a 429, the lineup is still confirmed, no playlist is made, and the "Save to Spotify" button shows.

### Spotify safeguards for playback and playlists

- Apply all the Phase 5 Spotify rules to playback and playlist calls made from the server, such as creating the service playlist.
- Web Playback SDK calls happen in the user's browser. If one gets a 429, show a short message in the player and fall back to the embed player or the "Open in Spotify" link. Don't retry automatically.

### No web request waits on Spotify (review F10; decided 2026-11-19)

- No web request may wait out a Spotify Retry-After. Any Spotify call made during a web request fails fast on a 429: it records the limit (the shared block, as in Phase 5), doesn't wait, and doesn't retry.
- Saving the playlist when a lineup is confirmed fails fast the same way, and the lineup page shows "Save to Spotify" instead. So does any other web request, including Find on Spotify; today that search waits up to 30 seconds and retries once, and this changes it.
- The search worker keeps the Phase 5 rule: it may wait out a short Retry-After once.

Tests: a web request that meets a 429 sends one request, never sleeps, and records the block; confirming during a block still confirms and shows "Save to Spotify"; the worker's single short wait still works.

### Transposition on the server (decided 2026-11-19; decision 0009)

- All transposition runs on the server, in Python: the service key, a personal transpose, capo positions and Nashville numbers. Changing the key re-renders the sheet with htmx ([[0009-transposition-on-the-server]]).
- A pasted Ultimate Guitar-style chart (chords on the line above the words) is converted to ChordPro **on the server, in Python**, and the person sees the result before saving. The server checks that the saved text is valid ChordPro and refuses it, with a message naming the line, when it isn't. (Changed on 2026-11-20: ChordSheetJS was first chosen for the conversion, but it is GPL-2.0-only, so the user chose a Python converter.)
- Transposing is covered by the normal test suite, so "the viewer's transposing is tested" is checked by `scripts/check.ps1`.

Tests: transposing up and down by semitones and to a key, including sharps, flats and minor keys; capo positions; Nashville numbers; the htmx key change returns the re-rendered sheet; invalid ChordPro is refused.

### Keys a song was sung in (decided 2026-11-19)

- "A key from a singer's range" is replaced by **remembering the keys each song was sung in**. When the worship leader chooses a lineup song's service key, the service keys that song had in confirmed lineups are shown, most recent first. No melody data is needed.

Tests: the keys come only from confirmed lineups that set one, most recent first; a song never sung shows none.

### Practise-along toggle (decided 2026-11-19)

- The toggle shows the chords in the recording's key, because Spotify audio can't be pitch-shifted.
- Spotify gives no key, and Audio Features is banned, so a person enters the **recording's key** on the song. When it isn't set, the toggle is hidden.

Tests: no recording key, no toggle; with one, the toggle shows the chords transposed to it.

### Lyrics on the song page (review F13; decided 2026-11-19)

- Full lyrics on the song page are shown only to people who plan: Worship Leader and Pastoral Staff by default. This is a permission (for example `songs.view_lyrics`), never a role name.
- Team members see the words through the chord sheet.

Tests: the leader and the pastor see the lyrics; a team member, and anyone without the permission, doesn't, but still sees the chord sheet.

### Approved after part A (2026-11-20)

The project owner approved these choices made while building part A.

**Transposing** ([[0009-transposition-on-the-server]]):
- C major and A minor spell their chords with flats (Bb, Eb, Ab): borrowed flat chords are far more common in worship songs than sharp ones. Every other key uses its own sharps or flats.
- Nashville numbers in a minor key count from the minor tonic (1 = A minor in A minor, so Am is 1m). Numbers ignore a capo. In Nashville view on a minor-key song, a short note says so, such as "Numbers count from the minor key (1 = A minor)".
- Capo positions 0 to 7 are offered, each with the shapes it gives; shapes in C, D, E, G, A, Am, Dm and Em are marked easy.
- A personal transpose (another key, capo or numbers) lives only in the page address. It is never saved, so nobody else sees it.

**Chord sheets:**
- A song has at most one approved sheet. Saving by someone who may approve replaces it. Approving a pending sheet when the song already has an approved one is refused: discard the pending one or edit the approved one. Only pending sheets can be discarded.
- Each team member has at most one pending sheet per song; pasting again replaces it. Only the person who pasted it, and people who may approve, see it.
- "Required in a confirmed lineup" doesn't block confirming: sheets usually come after a lineup is confirmed. The lineup instead shows how many songs have an approved sheet and marks the ones that still need one.
- Each lineup song has its own page, with the sheet in the service key, opened from the lineup and the service page. Team members open it only once the lineup is confirmed.
- Find chords links to searches on Ultimate Guitar and the web, and to a web search limited to worshiptogether.com, which has no simple search address of its own.
- The audit trail records a sheet's song, status and key, never its text.

Tests: every key with the spelling above; Nashville numbers in minor keys, with the note; capo positions and easy shapes; one approved sheet per song and the approve and discard refusals; one pending sheet per member; the counts and marks on a confirmed lineup; the lineup song page for each role; the audit trail without the sheet text.

### Approved after part B (2026-11-22)

The project owner approved these, and the Church Spotify Account below.

**The playlist ID** ([[0010-store-own-playlist-id]]; changes a hard rule in AGENTS.md):
- Besides track ID, title, artist, album and length, CHORD may store the ID of a playlist it created itself, used only to find and update that playlist, never as model input or a training feature. Without it, each "Save to Spotify" would make a duplicate playlist.
- The lineup may also store which account owns the playlist (the church's, or a user's) and the track IDs saved.

**The browser player's token:**
- The Web Playback SDK needs an access token in the browser. The player receives the person's own short-lived access token from a POST-only, never-cached page, keeps it only in script memory, and never writes it to the page or logs it. The refresh token never leaves the server. The page gives each person only their own token.

**Smaller choices:**
- The player is on the lineup song page only.
- Songs not on Spotify are left out of the playlist, and the message says how many.
- The playlist line shows only to people who may save, except a playlist on the Church Spotify Account: it is public, so everyone who can see the confirmed lineup gets its link.
- Anyone signed in may connect their own Spotify account. (Since 2026-11-24, Phase 9A: the "Spotify account" menu link shows only to people who can see lineups, `worship.view_lineup`; the page itself still works for anyone signed in.)
- Find on Spotify fails fast on a 429 (review F10).

Tests: the token page refuses GET, never hands out another person's token, and sends no-store headers; a stored token isn't the plain token and decrypts back; songs not on Spotify are left out with the count; team members see no personal playlist link.

### Church Spotify Account (approved 2026-11-22; decision 0011)

An optional church setting ([[0011-church-spotify-account]], following [[0001-configure-behavior-not-identity]]):

- Whoever holds the permission that changes church settings (`church.change_churchprofile`, the Administrator by default; never a role name) can connect one Spotify account as the church's account, in church settings (the Spotify tab), and disconnect it. Its tokens are stored encrypted like personal ones and are never shown or logged. It asks only for the scopes playlists need: `playlist-modify-public` and `playlist-modify-private`.
- **When it is connected**, every Lineup Playlist (on confirmation and from "Save to Spotify") is made and updated on the church account, as a public playlist, whoever confirms or presses the button. Everyone who can see the confirmed lineup, team members included, gets an "Open the playlist" link.
- **When it isn't**, the playlist goes to the account of whoever confirms, as a private playlist, and "Save to Spotify" saves to the account of the person who presses it; only the owner gets the link.
- The church account is never used for playback; each person plays through their own connection or the embedded player.
- With the church account set but unusable (refused, revoked or a 429), the lineup still confirms and "Save to Spotify" shows for people who may save.
- **A stored playlist that can't be updated** is made again only on a 404, or on a 403 when the connected account doesn't own it; any other 403 is a refusal (changed 2026-11-23; see Phase 8, "Updating a stored Lineup Playlist").
- **One playlist per lineup.** Each service's lineup has its own playlist, named with the service name and date (for example "Sunday Church – Nov 29"). Confirming a new service's lineup makes a new playlist; reopening and confirming the same lineup again, or "Save to Spotify", updates that lineup's own playlist; other services' playlists are never changed.

Tests: with the church account, confirming makes a public playlist on it and a team member sees the link; saving again updates the same playlist; confirming two services makes two playlists, and editing one leaves the other unchanged; without it, the playlist goes privately to the confirmer's account; only holders of the church-settings permission can connect or disconnect it; its tokens are encrypted; it's never used for playback; a 429 or a refusal leaves the lineup confirmed with "Save to Spotify".

### Importing a ChordPro file (approved 2026-11-20)

- The chord sheet form has **Import a ChordPro file** next to the text box. It accepts .cho, .chopro, .chordpro, .pro and .txt files up to 200 KB, in UTF-8; other files get a clear message (a wrong type, too large, not UTF-8, empty).
- The file's text goes into the text box for the person to check; they then save as usual. The file itself is never stored: only the ChordPro text and its key are, as before.
- The key comes from the file's `{key: …}` (or `{k: …}`) line and fills the Key field, which the person can change. With no key line and no key chosen, the form asks for one, as before.
- Other directives, such as `{title}`, `{artist}`, `{tempo}` and `{comment}`, stay in the text as they are; they never change the song's own fields.
- Choices approved after building it (2026-11-20):
  - Importing is its own step: choose the file, then press **Import**, a separate button. The page works without JavaScript.
  - **The file's key wins:** a `{key:}` or `{k:}` line replaces whatever key was chosen before importing. A key line that names no real key (such as `{key: H}`) is ignored.
  - A file may be up to 200 KB, but a chord sheet holds at most 20,000 characters, so a longer file is **refused at import**, with that limit in the message.
  - Rhythm lines are converted in files that are already ChordPro too, not only in pasted chords-over-words charts (tablature is left as written).
- **Rhythm lines** such as `|D//G|////|D//G|////|` (Worship Together intros, optionally after a label such as "Intro:") get their chords in brackets, so they transpose. A rhythm line that can't be read becomes a comment. It is never a reason a sheet can't be saved.
- Worship Together's ChordPro downloads write a rhythm line inside one bracket, such as `[| D / / G | / / / / |]` (fixed 2026-11-20 after the click-through). A bracket holding bar lines (`|` or `||`) or beat slashes is read as a rhythm line, with spaces or none: each chord gets its own bracket, giving `| [D] / / [G] | / / / / |`. One that can't be read becomes a comment.
- Plain section lines in a ChordPro file (Intro, Verse, Pre-Chorus, Chorus, Bridge, Interlude, Instrumental, Outro, Ending or Tag, with an optional number and colon) show as section labels, like `[Verse]` in a pasted chart.
- **Chart marks** (approved 2026-11-20, after the click-through):
  - An optional chord in parentheses, such as Worship Together's `[(F#m7)]`, transposes and keeps its parentheses: `(F#m7)` in E is `(G#m7)` in F#.
  - N.C. (no chord), repeat marks such as `x2` or `(x2)`, and footnote marks such as `*` are kept as written and never transposed. A chord with a trailing mark, such as `D*`, moves its chord and keeps the mark.
  - Anything else in brackets that still can't be read is **kept as a ChordPro annotation** (`[*Zz9]`), shown as written and never transposed. The form warns, listing those lines ("These marks were kept as written and won't transpose: line 35 …"), but saves.
  - A **stray `]`** that closes nothing (a typo such as Worship Together's `[(Em7)]]King`) is removed, and the save warning lists it ("Removed a stray ] on line 53."). It doesn't block the save.
  - **Only what breaks the ChordPro text itself stops a save**: an unclosed `[`, a directive not alone on its line or not closed, a section opened but never closed, or no chord at all.
  - In the viewer, marks kept as written are shown apart from chords (grey italic). When the sheet has such marks and is shown moved from its own key (another key, a capo or Nashville numbers), a short note under the sheet says "Some marks were kept as written and aren't transposed." N.C., repeat and footnote marks are standard chart marks, not kept-as-written ones: they get neither the style nor the note.
- A team member's import follows the same rule as a paste: pending until approved.
- A person still brings in each chart. Nothing is fetched from any site.

Tests (made-up content only): the key read from `{key:}` and from `{k:}`; a file without a key; a wrong extension; a file over 200 KB; a file that isn't UTF-8; other directives kept and the song unchanged; a rhythm line that transposes, and one that becomes a comment; a team member's import staying pending; a bracketed rhythm line with spaces (D to E gives E and A), with none and with `||` bars; an unreadable bracketed line becoming a comment while the sheet saves; "Verse 1" and "Outro" lines showing as section labels; "(F#m7)" transposing with its parentheses; N.C. and x2 kept and not transposed; an unreadable mark such as "[Zz9]" saved as an annotation with the warning; an unclosed bracket still an error; the viewer's note showing only when the sheet has kept marks and is shown away from its own key.

---

## Phase 8: team and community

### Attendance (question 6)

Decision: a headcount per service. The existing `WorshipService.attendance` field is enough; no per-person attendance.

### Notifying the team (changed 2026-11-23)

(First: only the pastor's edit to a confirmed lineup. The project owner widened it on 2026-11-23.)

- Notifications are **in the app only**: no email or SMS.
- They go to that service's **assigned people whose reply is Pending or Accepted**, never to the person who caused them, when:
  - the pastor (a holder of `worship.finalize_lineup`) edits a confirmed lineup ("Edited by <pastor Label>");
  - anyone else edits a confirmed lineup ("Changed by");
  - the lineup is confirmed.
- A person is also notified **when they are assigned** to a service (unless they assigned themself).
- **Nothing on cancelled or past services.** Team members still see nothing of a lineup until it is confirmed, so edits to a draft notify nobody.
- The navigation shows the **unread count**; a person opens a notification (which marks it read) or marks all of them read.

Tests: after each of the three lineup events, each Pending or Accepted assigned person has a notification, and nobody else does (not a Declined one, not someone assigned elsewhere, not the person who caused it); a newly assigned person is notified; nothing for a cancelled or past service or a draft; the unread count and marking read.

### Administrator role (question 7)

Decision: keep the Administrator role undeletable, with every permission. (Done: the spec no longer calls Admin "optional".)

### Teams: decided before building (2026-11-23)

The project owner decided these before part A.

- **Team Profile:** just a person's Team Parts. **No vocal range**: since Phase 7, keys come from the keys a song was sung in, so nothing would use it.
- **Team Profiles belong to user accounts.** The Members module stays as built; a Member record is not needed to serve.
- **Who can be assigned:** only people whose Team Profile has that part.
- **Replies:** Pending, Accepted or Declined. A declined assignment stays on the service page for the leader to fill. No new assignments and no replies on a cancelled or past service.
- **Blackout Dates:** a range of whole days in the church's time zone. Nobody can be assigned on a day they blacked out. A blackout that overlaps an existing assignment (Pending or Accepted, on a service that isn't cancelled) is refused, with a message pointing to Decline or a Swap Request.
- **Swaps** (part B; details below): no approval. The first person who has the part, isn't blacked out that day and isn't already on that service takes it and gets the assignment. The audit trail records it.
- **Announcements** (part B): to "everyone" (everyone signed in) or to "one service's team" (its assigned people), the second offered only while Teams is on. Posting is a permission, held by Pastoral Staff and Worship Leader by default. No expiry: the author archives it.
- **Order of work:** part A is the roster and availability (Team Parts, Team Profiles, Assignments and replies, Blackout Dates, My schedule) plus the playlist fix below; part B is swaps, announcements and notifications.

Tests (part A): only people with the part can be assigned; nobody on a blackout day; no assignments or replies on a cancelled or past service; a declined assignment stays on the service page; a blackout over a Pending or Accepted assignment is refused, and one over a Declined or cancelled one isn't; blackout days follow the church's time zone.

### Approved after part A (2026-11-23)

The project owner answered the part A open questions.

**Accepted as built:**
- A reply is given once, while Pending.
- A past service's team is frozen: no assignments, replies, removals or swaps.
- Blackout Dates for days already passed are refused.
- Pastoral Staff see the roster and each service's team but don't assign by default. A church may give `teams.add_assignment` to a pastor (or anyone) per user; the Administrator assigns by holding every permission.
- "Save to Spotify" shows after a refused update only when the lineup's songs differ from what the playlist holds.

**Changed: the team is a permission.**
- Only holders of `teams.view_assignment` can have a Team Profile or Blackout Dates. My team parts and the Blackout pages need it (a permission check, never a role name), so Office Staff don't see them.
- `candidates()` leaves out anyone without it, even with a Team Profile from before; they can't be assigned or take a swap.

Tests: Office Staff are refused on My team parts and the Blackout pages; a user with parts but without the permission isn't offered in Assign and can't be assigned; the permission given to one user makes them a candidate.

### Swap Requests (decided 2026-11-23, part B)

- Someone **Pending or Accepted** on a **future service that isn't cancelled** can ask for a swap, and can **withdraw** it while it is open. One open request per assignment.
- **Anyone eligible sees it:** they're on the team (`teams.view_assignment`), have the part, aren't blacked out that day and aren't already on that service.
- **The first eligible person to take it gets the assignment, as Accepted.** No approval. Taking locks the request's row, so if two people press at once only the first gets it; the other is told someone else took it first.
- The **original assignment ends**. The audit trail records who handed over and who took it (the request, and the assignment ended and made).
- The blackout refusal's "ask for a swap" **links** to asking for that swap.

Tests: asking and withdrawing, only while Pending or Accepted on a future open service; who sees it; taking gives an Accepted assignment and ends the original; the audit trail; a second taker is refused, including two at once on two database connections; the blackout link.

### Updating a stored Lineup Playlist (fix, decided 2026-11-23)

Changes the Phase 7 rule that any 403 or 404 makes a new playlist.

- When updating the lineup's stored playlist, a **new playlist is made only** on a **404**, or on a **403 when the connected account isn't the stored playlist's owner**.
- Only when Spotify answers 403, CHORD asks Spotify for the connected account's ID and the playlist's owner, compares them, and **stores neither**. The hard rule on stored Spotify fields doesn't change ([[0010-store-own-playlist-id]]).
- **Any other 403** is treated like a refusal: the lineup stays confirmed and "Save to Spotify" shows.
- If either lookup gets a 429, it fails fast (review F10): nothing waits, and "Save to Spotify" shows.

Tests: a 404 makes a new playlist; a 403 from another owner's playlist makes a new one, on the Church Spotify Account and on the confirmer's own account (private); a 403 on the account's own playlist leaves the lineup confirmed with "Save to Spotify" and makes none; a 429 on a lookup fails fast with "Save to Spotify"; neither account ID is stored.

---

## Adviser comments, 24 Nov (Phase 9A)

The adviser commented on CHORD on 2026-11-24. The project owner approved the plan below the same day, and said more comments or changes may come: treat this section as open to change. Phase 9A comes **before Phase 9**; AGENTS.md records this as an exception to "the theme-based lineup comes first", and Phase 9 is built only if time remains before the final presentation (1–4 Dec 2026).

| # | Adviser comment | Decision | Size |
| - | --------------- | -------- | ---- |
| A1 | A church member role, and the screens it may see | A **Church Member** default role | S |
| A2 | "What if X is no longer the Worship Leader next month?" | Changing a role keeps every record of the past; the admin decides about future assignments | S |
| A3 | User logs or history | Sign-in events in the Audit Trail, and a per-user History page | S–M |
| A4 | Admins add church members' accounts in a batch | Create accounts from the Members list | M |
| A5 | Scheduling for special services such as weddings and funerals | **Occasions** are in scope as their own Module, apart from worship services, with requests from church members and booked times on the calendar ([[0013-occasions-module]], replacing [[0012-occasion-services]]) | L |
| A6 | Printable reports from the church's data (senior citizens, who attended a service, and so on) | A filtered Members report, printable and exported as CSV; per-person attendance **on hold** | M–L |
| A7 | Improve the UI: button locations and wireframes | Wireframes first, for the owner's approval; colours later, from the owner | L |

Not decided yet: what is shown at Progress Check 2 (25 Nov) and what goes in the Progress Report. The owner decides later. Nothing from Phase 9A is merged into `master` before the owner says so.

### A1: Church Member role

- A new default role, **Church Member** (key `church_member`), editable like every role ([[0003-editable-roles]]). Code checks its permissions, never its name.
- It sees: the dashboard, the person's own member record, announcements to everyone, the service schedule and calendar with each service's date, time and theme title, and its own Occasion Requests (A5). It can request an Occasion.
- It doesn't see: lineups (draft or confirmed), song pages, chord sheets, lyrics, suggestions, theme notes, the roster or other people's member records. These stay with the team and the people who plan.
- Accounts created in a batch (A4) get this role by default.
- Its one default permission is `worship.view_worshipservice`; the rest needs none. Requesting an Occasion comes with A5.
- **Only openable Modules are listed** (built with A1, 2026-11-24): the navigation and dashboard list a switched-on Module only for people who can open its main page (Members: `members.view_member`; Worship: `worship.view_worshipservice`; Teams: `teams.view_assignment`; Announcements: anyone). Before, everyone saw every switched-on Module and some got a 403 page. This applies to every role: Office Staff no longer see Teams, and Team Members no longer see Members.
- **The "Spotify account" menu link** shows only to people who can see lineups (`worship.view_lineup`), decided by the owner on 2026-11-24: Church Members (and Office Staff) have nothing to play, and each connection takes one of Spotify's Development Mode slots. The page still works for anyone signed in, as Phase 7 decided.

Tests: a Church Member reaches each allowed page and is refused (403, or 404 where the rules already hide a page) on lineups, song pages, chord sheets, the roster and other members' records.

### A2: A role change keeps history

- Changing a person's roles never deletes or changes what they did before: lineups they confirmed or edited, marks, chord sheets, approvals, Suggestion Feedback, past assignments and Audit Trail entries all stay, under their name. Users are deactivated, never deleted (as today).
- The user's page shows their **role history**, read from the Audit Trail (it already records each change to a user's roles).
- **Leaving the team:** when a role change takes away `teams.view_assignment`, the save shows the person's assignments on future services that aren't cancelled (Pending or Accepted). The admin chooses to **end** them (each becomes an open place for the leader to fill, and the person's open Swap Requests are withdrawn) or to **keep** them. Past assignments are never touched. The choice is in the Audit Trail.

How it was built (2026-11-24):
- The role history and the warning are on the user's edit page (users have no other page), for people who may change users (`accounts.change_user`). The history lists every change to Roles or Active from the Audit Trail, newest first, with who made it.
- Saving a change that takes someone off the team first shows the list and the choice; nothing is saved until the admin chooses. The Audit Trail records the choice on the user ("Assignments on coming services: Ended (2)" or "Kept (2)"), and each ended assignment is recorded as removed.
- Deactivating someone takes them off the team too, so it shows the same list.
- Accounts doesn't import Teams: Teams registers its check with `apps/accounts/role_changes.py` in `TeamsConfig.ready()`. While Teams is switched off, nothing is listed.
- Not covered: taking `teams.view_assignment` away from a whole role in the permission matrix, or deleting a role. Their coming assignments then stay, as before; the leader removes them by hand.

Tests: after a Worship Leader becomes a Church Member, their past lineups, marks, sheets and assignments still show their name; the role history lists both roles; the warning lists only future, not cancelled, Pending or Accepted assignments; ending them frees the places and withdraws open swaps; keeping them changes nothing; past assignments are never changed.

### A3: User history

- The Audit Trail also records **sign-in, sign-out and failed sign-in** (with the username tried and the time; never the password). These are new actions on `AuditEvent`.
- Each user's page gets a **History** tab: their sign-ins and the changes they made, from the Audit Trail. It needs `audit.view_auditevent`, like the audit log.
- Never recorded: passwords, temporary passwords (A4), Spotify tokens, lyrics or chord sheet text.
- Phase 10's limit on repeated failed sign-ins will read these events.

How it was built (2026-11-24):
- Sign-ins are kept in their own Audit Trail table, `SignInEvent` (`apps/audit`), not as new actions on `AuditEvent`: `AuditEvent` records changes to data, and mixing sign-ins into it would fill the audit log and would add rows to every test that signs someone in. Like the rest of the Audit Trail, it is never edited or removed, and it is read with `audit.view_auditevent`.
- The History page is `/accounts/users/<id>/history/`, linked from the user's edit page for holders of the permission: the latest 50 sign-ins and the latest 50 changes the person made.
- No IP address or device is recorded; Phase 10's limit on failed sign-ins decides whether it needs one.

Tests: signing in, signing out and a failed sign-in are each recorded; no password appears in any event; the History tab shows only that user's events and is refused without the permission.

### A4: Batch accounts from the Members list

- On the Members list, a person who may add users (`accounts.add_user`) and view members ticks members without an account, or uses the list's filter, and presses **Create accounts**, choosing a role (Church Member by default).
- Each account is linked to its Member record (`Member.user`). The username is made from the name and kept unique; the email comes from the Member record when it has one.
- **Temporary passwords** are random, shown once on the result page, and offered as a CSV download from a never-cached page. They are never logged, audited, emailed or stored in plain text. The person must change it at first sign-in.
- Members who already have an account, or are archived, are skipped, and the result says how many and why.
- The Audit Trail records each account created, without its password.

How it was built (2026-11-24):
- "Create accounts" on the Members list opens `/members/accounts/`: current members without an account, filtered by name and status like the list (the first 200), each with a tick box, and the role (Church Member by default). It needs both `members.view_member` and `accounts.add_user`.
- Usernames are "first.last" in lowercase (accents dropped), then "first.last2" and so on. Temporary Passwords are 12 characters without look-alike characters (0/O, 1/l/I).
- The result page shows the passwords once and offers the CSV as a download built into the page itself, so the passwords are never stored on the server, even for a moment. The page is never cached; sending the form again only skips the members who now have an account. Cells a spreadsheet would run as a formula (starting with =, +, - or @) are prefixed with an apostrophe.
- `User.must_change_password`: until the person sets their own password (Change password, or a reset by email), every page except Change password and Sign out sends them to Change password; static files and the church logo still load.
- Sending the passwords by email isn't built; the admin hands them over.

To confirm with the owner: the [[Concept-Brief]] and [[Project-Overview]] say "one church, five users or fewer". Accounts for church members go past that. Spotify's 5-user limit applies only to people who connect Spotify (and the Church Spotify Account), not to CHORD accounts, so the suggested wording is "five Spotify-connected users or fewer".

Tests: accounts are created and linked; the chosen role is given; existing accounts and archived members are skipped with the count; no password appears in the Audit Trail or logs; the CSV page sends no-store headers and works only once; first sign-in forces a password change; only holders of the permission see the button or can post.

### A5: Occasions (special services) ([[0013-occasions-module]])

Special services such as weddings, baptisms and funerals are in scope, apart from worship services. The first design ([[0012-occasion-services]]: an occasion as a Worship Service made from an "occasion" template) was built and then replaced the same day: the owner decided that these are **not worship services** and need their own form and part, with no song lineup or team. Built as the **Occasions** Module ([[Occasions]]).

Decided by the owner on 2026-11-24:
- **Fully separate:** an **Occasion** of a church-edited **Occasion Type** (with a usual length), in its own Module and pages; no theme, lineup, suggestions or team.
- **The pastor (and the Administrator) add occasions directly**, not only through requests.
- **Notifications move out of Teams** into the core `notifications` app, so the requester is told whichever Modules are on.
- **Examples included:** "Wedding", "Baptism" and "Funeral" are seeded as Occasion Types, switched off.
- **Signing in is enough** to request: no Member record is needed.

The rules:
- An Occasion records its type, date and time, length, who it is for, the officiant (a user), the venue, notes, and whether it is cancelled.
- **Occasion Request:** a signed-in person with `occasions.request_occasion` asks for an active type, a date and time that hasn't passed, who it is for, and a note. It is **Pending**, then **Approved** or **Declined** (with a reason); the requester may withdraw it while Pending.
- **Approving is a permission**, `occasions.approve_occasion` (Pastoral Staff by default, and the Administrator). Approving books the Occasion; the approver may change the date and time first.
- **Booked times:** every worship service books its template's usual length, and every Occasion its own length. Adding, moving, requesting or approving an Occasion that overlaps a booking that isn't cancelled is refused, naming the clash only for people who may see it.
- **The calendar** (Worship's) shows Occasions to holders of `occasions.view_occasion` (Pastoral Staff, Worship Leader, Office Staff by default) and only "Booked" to everyone else.
- The requester gets an in-app Notification when the request is approved or declined; approvers see the number of Pending requests on the Requests tab.
- **Not built:** fees, payments, a requirements checklist, church records or certificates ([[Services]] keeps that old design for reference).

How it was built (2026-11-24):
- `apps/occasions`: `OccasionType`, `Occasion`, `OccasionRequest` (its Meta declares `request_occasion` and `approve_occasion`); rules in `rules.py`. The Module requires Worship.
- Worship keeps only `ServiceTemplate.length_minutes` (90 by default) and `WorshipService.ends_at`, and gained `apps/worship/bookings.py`, a registry Occasions joins so the calendar shows its bookings without Worship importing it.
- **"For" is a text field**, not names linked to Members: neither Module depends on Members, and nothing reads the link. It can be added if a report needs it.
- Only Occasions are checked for clashes; scheduling a worship service is not (left as an open question in [[Occasions]]). Bookings take a database lock (`BOOKINGS`), so two at once take turns.
- `Module.view_permission` may now be a tuple, any one of which opens the Module: Occasions opens for people who see occasions and for people who may only request one.

Tests: `apps/occasions/tests/test_occasions.py` and `apps/notifications/tests/test_notifications.py`; the usual length in `apps/worship/tests/test_schedule.py`.

### A6: Reports

- A **Members report**: filters on Membership Status, age group, sex, Household, date joined and Custom Fields; the columns to show; a **print layout** (a print stylesheet, no PDF library) and CSV export. It reuses the Members permissions, and private details follow `members.view_private_details` as everywhere else.
- **Age groups** (for example Children, Youth, Adults, Senior Citizens, with their age ranges) are a church-edited list with neutral defaults, worked out from `Member.birth_date` on the report's date. A member without a birth date is counted as "Age not given".
- **Who attended a service: on hold.** Per-person attendance is still out of scope (AGENTS.md; Phase 8, question 6). Ask the owner before building A6, with the options: optional per-person attendance, off by default, keeping the headcount; or "who served" from Assignments only.
- The existing song usage and attendance reports get the same print layout.

Tests: each filter; age groups on the report's date, and "Age not given"; private details hidden without the permission; the CSV matches the screen; the permissions.

### A7: UI pass

- First, wireframes of the main screens (dashboard, schedule and calendar, service page, lineup, lineup song page, Members list, settings) showing button placement and page layout, for the owner's approval. No template changes before that.
- Then the templates follow the approved wireframes, still Django templates with Bootstrap and HTMX ([[0002-server-rendered-ui]]). Colours and fonts come later, from the owner's instructions.
- It overlaps Phase 10's mobile and accessibility pass; whatever A7 covers is ticked there too.

Tests: the existing view tests keep passing; every action that moved is still permission-checked.

#### The owner's design system (25 Nov)

The owner gave the colours and fonts on 2026-11-25: "Colours and fonts come later, from the owner's instructions" above. Built on branch `ui-design-system` (not merged); the details, file locations and contrast table are in [[Design-System]].

- **Light mode (default):** page `#E6E2E1`; surface `#FFFFFF`; text `#173630`; secondary text `#4A5E59`; border `#D3CDC9`; strong border `#9FA7A2`; primary `#173630` with `#E5C690` text; accent gold `#E5C690` (never as text on white); accent tint `#F3E6C9`; links `#173630`, hover `#0B1F1B`, underlined; chord letters `#7A5A1E`.
- **Dark mode:** page `#060F00`; surface `#0F241F` (cards), `#173630` (raised: navbar, dropdowns, modals); text `#E6E2E1`; headings and accent `#E5C690`; secondary text `#B9C4BF`; border `#2E4A44`; primary `#E5C690` with `#060F00` text; chord letters `#E5C690`.
- **Dark mode follows the device** (`prefers-color-scheme`, through `data-bs-theme`), set by a script in `<head>` so nothing flashes. Since 2026-11-25, at the owner's request, each person may choose instead: Settings › Personal › **Appearance** (Match my device, Light or Dark; `User.theme`, "device" by default), applied by the same script.
- **Fonts:** Raleway (600, 700, 800) for headings, the brand and card titles; Fira Sans Condensed (400 to 700) for the rest; self-hosted with their OFL licences. The chord sheet's chords stay monospace.
- **Icons:** solid (filled) inline SVG partials (search, gear, eye, closed eye, person, play, pause), used only where a screen needs them: the navbar (gear) and the player.
- **Profile letter:** the first letter of the person's name in a gold-on-green circle beside their name.
- **Back links:** every existing "←" link is one shared pill link (44px, chevron).
- **Status colours** stay Bootstrap's, at shades that reach 4.5:1 in both modes.
- **The player card** (wireframes "6 Lineup song page" and "6b Spotify card, no playback"): green in both modes, in three states: full playback (cover, title and artist from the Song, progress, back and forward 10 seconds, play/pause), the embedded player, or "No playback for this song". The cover comes from the SDK in the browser only and is never stored (AGENTS.md). Every Phase 7 playback rule stays: fall back on any SDK failure with no retry, stop on the first 429, the token in script memory only, the 15-second timeout.
- Page layouts don't change in this part; the per-screen wireframe changes are separate A7 work.

How it was built (2026-11-25):
- `static/css/chord.css` sets Bootstrap's variables for both modes; `--bs-body-bg` is the surface and `body` gets the page colour, so cards, inputs, tables and menus are white (dark green in dark mode) without touching their templates. Chosen here, where the owner gave no value: tertiary surface `#F4F1F0` (light) and `#173630` (dark); dark strong border `#6E8A83`.
- **No link to fix a song without a track:** CHORD has no page that links an existing song to a Spotify track ("Find on Spotify" only adds new songs; the song form has no track field), so the card shows only the message.
- **Contrast:** every text pair passes. **The light-mode strong border `#9FA7A2` is 2.46:1 on white**, below the 3:1 that input and button outlines need; it is used as given, for the owner to decide (`#6E8A83`, 3.73:1, would pass).

Tests: `apps/songs/tests/test_design_system.py` (each player state, the safeguards in `player.js`, the theme and fonts on every page, the profile letter, the back link); `test_spotify_playlists.py` (a song without a track now gets the card).

#### The screens follow the approved wireframes (25 Nov)

The owner approved the A7 wireframes on 2026-11-25, in the design system above. Built on branch `ui-design-system` (A7 part 3), one commit per screen. Layout and button placement only: no button changed what it does or who may use it.

**Shared patterns** ([[Design-System]], "Page patterns"): a page header with one primary button and the rest under "More" (`{% page_header %}`, `{% more_menu %}`: an item the person may not use doesn't show, and an empty "More" doesn't show); section tabs with a gold underline (`includes/section_tabs.html`); status pills (`includes/status_pill.html`); cards with a title row; two columns that stack on a phone.

**Design change: the Settings hub.** Settings were spread over the Administration menu and a "Settings" button in each Module. Now there is one hub: a gear in the navbar (it replaces the Administration menu) opens the first settings page the person may open, and every settings page shows a side menu of collapsible categories (General; People and access, until 28 Nov 2026; Members; Worship, in two groups, Services and Songs and suggestions; Teams and occasions; Integrations), with "Category · Group" above its heading. Each app registers its pages in `apps/core/settings_menu.py`; the menu shows only pages of switched-on Modules that the person holds the permission for. The Modules' "Settings" buttons became "<Module> settings" in their "More" menus. No numbered decision: it changes navigation only, and the registry is easy to change back.

**The screens:**
- **Worship schedule and calendar:** Add service; Schedule weeks ahead and Worship settings under More; tabs Schedule, Calendar, Songs, Reports (each only for people who may open it). The schedule has an Upcoming/Past toggle, the search, and the columns When, Service, Theme, Lineup, Team and Open; a draft shows as one only to people who plan, and Team only while Teams is on, for people who may see teams. The calendar has icon buttons for the months, Today and a legend; decision 0013's "Booked" rule is unchanged.
- **Service page:** Edit service as the one button; a five-step bar for people who plan (Theme, Suggestions, Lineup, Confirmed, Playlist); the next step's card first; Team, Details and Headcount on the right. *Replaced by Phase 9C (2026-11-26): four steps and a next-step panel; see "Phase 9C" below.*
- **Lineup:** Confirm lineup on top; Regenerate, Send back and Reopen under More; song rows with only Move up and down, Lock and a menu (Swap, Key and notes, Open the song page, Remove).
- **Lineup song page:** Previous and Next song through the lineup's order (disabled at either end); the chord sheet's controls in one toolbar; the Listen card, Notes for the team and This lineup on the right.
- **Members:** Add member; Import, Export, Create accounts and Members settings under More; tabs People and Households; one filter row; columns Name, Status, Household, Phone (private) and Can sign in. The Email column is gone (no test or decision needed it).
- **Dashboard:** what needs the person now. Each Module adds its items, rows and side cards through `apps/church/dashboard.py`, so Church Setup imports none of them.

**Appearance (the owner's request, 25 Nov):** each person chooses light or dark mode, or to match their device (the default), on Settings › Personal › Appearance (`/accounts/appearance/`; also in the user menu). It is saved on their account (`User.theme`, migration `accounts/0007_user_theme`), applies on every device they sign in on, and isn't audited (a preference, not church data). Personal is the hub's last category, open to everyone signed in, so everyone now has the gear; for a Church Member it opens Appearance.

**Left out, with no data or view behind them (for the owner to decide):**
- The Team column's "N of M places filled" and "Open place" rows: CHORD has no planned places for a service, only assignments (a removed assignment is gone). The column shows "N of M accepted" (accepted of those assigned) instead.
- "Saved by <name>" on the lineup: no field records who saved a lineup. It shows "Saved <date>"; "Edited by" shows as before.
- Print on the lineup song page: there is no print layout yet (A6 work).
- A "More" menu on the service page: no other service action exists (cancelling is on the edit form), so it doesn't show.
- The step bar shows only to people who plan, so the team never sees a draft's state.
- The Members Reports tab: A6 isn't built.

Tests: `apps/core/tests/test_ui_patterns.py`, `test_settings_hub.py`; `apps/worship/tests/test_schedule_screens.py`, `test_service_screen.py`, `test_lineup_screen.py`, `test_lineup_song_screen.py`; `apps/members/tests/test_members_screen.py`; `apps/church/tests/test_dashboard_screen.py`. Each moved action is still refused without its permission, and its menu entry doesn't show.

#### Landing page redesign (UI/UX owner, 26-27 Nov 2026)

Designed as an interactive mockup first, approved by the UI/UX owner on 2026-11-27 **subject to the lead developer's approval** (the A7 rule: no template change before approval), and built on branch `joy-ui-ux-v2`. Details: [[Design-System]], "The landing page".

Approved choices:
- A modern, warm church-website look within the approved palette and fonts; a solid green nav (logo and links left; Sign in and Sign up right).
- **Phase 9C wording:** the hero and How it works describe the four steps (Theme, Praise Team, Song Lineup, Confirm) and that suggestions assist.
- **No "Register your church" on the landing page:** the hero's main button is Explore churches (the Directory), the call to action is Sign up. Registering stays on the sign-in and no-church pages. (Since 27 Nov 2026 its Sign up opens registering: "Sign up is registering a church".)
- **Logo:** the owner's final green and gold artwork, unchanged and transparent, on light grounds; on green grounds its colour-swapped copy (gold letters and circle), also transparent, with no plate (the owner's choice, 2026-11-27). The owner confirms the cross and church in it (shared by most churches, naming none; decision 0001).
- **Photography** as a new asset: CC0 photos from StockSnap and rawpixel, sources and licences in `static/images/landing/SOURCES.md`; the 960 and 1024 px copies for now, replaceable under the same names.
- **Loading intro** once per browser session, with a **0.8 s minimum**: the owner's approved exception to "no deliberate delay" (2026-11-27). No minimum with reduced motion; the page loads underneath; it can never block the page.
- **United in Worship:** public churches that also **finished setup** (no approval step, no database change), **newest first**, **up to 12**, in a carousel. Since Phase 9B the landing page named no church; it now names public ones, as the Directory already does.
- Its own stylesheet, `static/css/landing.css`, so signed-in pages can't change.

Tests: `apps/church/tests/test_landing.py` (`LandingRedesignTests`, `ChurchShowcaseTests`): the Phase 9C steps; the links to sign in, sign up and the Directory, and none to registering; the page's own CSS, script and images exist and load; every image is decorative or labelled; the intro's session flag, minimum, caps and CSS fallback; signed-in pages don't load the landing CSS; only public churches that finished setup, newest first, at most 12; no contact details; the logo fallback; the carousel arrows start hidden.

#### Church directory redesign (UI/UX owner, 27 Nov 2026)

Designed as an interactive mockup first (v2 after the owner's review: no overlay, the search stays in place, "Search results for" with Back to all churches), approved with these choices and built on `joy-ui-ux-v2` ([[Design-System]], "The church directory"):
- **Which churches:** the same rule as the landing showcase: "Show the church publicly" on **and** setup finished (`listed_churches()`). This narrows the Directory, which listed every public church. A Church Homepage still opens for any public church.
- **Sort:** newest first by default; Name A to Z and Z to A.
- **Images:** the church's logo only, else the CHORD fallback; no profile photos, banners or stock images (church administrators will manage profiles and banners later, in the church management area).
- **Signed-in people** get the same public page (Back to Home goes to their dashboard), keeping their account and their own light or dark choice.
- **Search** without reloading: HTMX fetches the results part and the suggestions (`/churches/suggest/`, a new reserved word "suggest"); a plain GET form without JavaScript.

Tests: `apps/church/tests/test_public_pages.py` (`DirectoryTests`, `DirectoryRedesignTests`, `SuggestionTests`): listed churches only, a public church without finished setup left out, search by name and address, sorting, 24 to a page, the HTMX fragment and the full page, the empty search, the logo and its fallback, no contact details, Back to Home, signed-in people keep their account and theme; suggestions listed churches only, from two letters, at most six, names first, the match marked and escaped, and the reserved "suggest".

#### Church profile redesign (UI/UX owner, 27 Nov 2026)

Designed as an interactive mockup first and approved with the owner's rules for public access: the profile is a public website for each listed church, open to everyone without signing in, the same for guests, signed-in people and members; only what is meant to be public; requesting keeps its existing sign-in. Built on `joy-ui-ux-v2` ([[Design-System]], "The church profile"). The owner's choices on the open questions:
- **Upcoming services** stay, at the bottom of the sidebar, only when the church switches them on.
- **Website** shows with the other contact details.
- **No images on announcements** (there is no image field, and no new fields for now).
- **One calendar icon for every service** (no icon field; choosing by a church's own wording would break the core rule).
- **The latest five announcements**, as before.
- The Announcements tab now shows while the Module is on even with none ("No announcements yet"), where the old page left the section out.

Tests: `apps/church/tests/test_public_pages.py` (`HomepageTests`, `ProfileRedesignTests`): the same profile for a visitor, someone from another church and a member, with no sign-in to view and nothing private; the sections in the sidebar and the tabs; contact shown once, with links; Back to Churches and home; the empty Announcements tab only while the Module is on; Read more for long announcements; the sign-in note only for requesting; its own styles, the logo and its fallback.

#### Sign-up page redesign (UI/UX owner, 27 Nov 2026)

Designed as an interactive mockup first and approved by the owner after one round of changes; built on `joy-ui-ux-v2` ([[Design-System]], "The sign-in page"). The owner's choices:
- **A split screen** after the owner's reference: the photo panel left (logo upper left, heading and tagline at the bottom), a compact centred form right with the Sign Up / Sign In toggle above it, one rounded container.
- **The photograph follows the existing rule** (freely licensed, no recognisable faces): the owner's own photo was set aside for "Bearded guitar concert" (Austin Neill, CC0), at least 1600 px wide, the face softened into the stage haze; recorded in `static/images/landing/SOURCES.md`.
- **Input outlines `#6E8A83`** on this page, which pass 3:1 on white ([[Design-System]], "Contrast", noted the light-mode `#9FA7A2` does not).
- **Back to Home uses a new `arrow-left` icon.** The directory and profile pages keep their chevron links for now.
- **A compact password checklist** in place of Django's help list, mirroring the same validators; the server still checks every rule.
- **Wording:** the username hint "Up to 150 letters, digits and @ . + - _", "Confirm password", "Enter the same password again." (`SignUpForm`, so the church registration page's account fields read the same).
- No other sign-in services (CHORD has none).

Tests: `apps/accounts/tests/test_signup_page.py` (`SignUpPageTests`, `SignUpValidationTests`): its own page with every form field once, CSRF and one heading; the photo panel's words and decorative images; the toggle, Sign in and Back to Home links; no other sign-in services; the checklist keeping the help text's id, the show buttons hidden without the script; the approved wording; its own stylesheet, script and photos exist, with their sources; its CSS scoped to `.au` (page transitions aside) and not loaded by the home or password reset pages; mismatched passwords, each of Django's four password rules, a taken username and a missing email shown on the page with what was typed kept (never the passwords); a good account created as before; a POST without the CSRF token refused; signed-in people sent home.

#### Sign-in page redesign (UI/UX owner, 27 Nov 2026)

Designed as an interactive mockup (normal, loading and invalid-credentials states) and approved by the owner; built on `joy-ui-ux-v2` ([[Design-System]], "The sign-in page"). The owner's choices, with the mockup's recommendations they approved:
- **The sign-up page's split screen, shared:** one layout (`accounts/auth_base.html`), the same photo, logo, words, inputs, buttons and toggle; "Welcome Back", "Sign in to continue to CHORD", Forgot your password? under the password field, the gold Sign In button, "Don't have an account? Sign up".
- **The church registration link reads "Register your church"**, as the sign-up intro already says; "sign in your church" was easy to confuse with Sign In.
- **One card size for both pages** (at least 990 px tall above 720 px, the sign-up form's tallest), so switching never moves the photo.
- **A fade between the two pages** through the browser's page transitions, the photo held still; none with reduced motion, and none in browsers without them (Firefox).
- **A busy button on both pages:** a spinner and "Signing in…" / "Creating account…", disabled while sending so a second press does nothing; no added delay.
- Django's sign-in is unchanged: `LoginView`, `AuthenticationForm`, CSRF, `next` and the redirects, the reset-password link; no new sign-in methods and no model change.

Tests: `apps/accounts/tests/test_signin_page.py` (`SignInPageTests`, `SignInBehaviourTests`): the shared layout, its stylesheet, script and photo; one heading, the words, every field once with `next` and CSRF, the busy button; Django's `autocomplete` values and one show button; the toggle, Sign up, Register your church (not "sign in your church"), Forgot your password? between the password field and the button, Back to Home; no other sign-in services; the reset page still opens; wrong credentials and an inactive account shown in the error box with the username kept and the password never echoed; empty fields' errors under them; a good sign-in goes home, `next` is kept and followed, a `next` to another site is ignored; a POST without the CSRF token refused. `test_sign_in.py` keeps the old checks (its error box assertion now names the new box); `test_signup_page.py` now covers the shared files and the busy words.

#### Authentication pages and the registration wizard (UI/UX owner, 27 Nov 2026)

The owner then approved a second mockup of all three pages (its own conversation; "CHORD Church Registration"), replacing the card version of sign-in and sign-up the same day; built on `joy-ui-ux-v2` ([[Design-System]], "The sign-in page" and "Registering a church"). The owner's choices:
- **Full-page sign-in and sign-up:** the photograph fills the left half edge to edge, the form sits in the middle of the right; no card and no Sign Up / Sign In toggle. Green main buttons, Show / Hide words in password fields, an outlined Back to Home pill.
- **"Sign up" means registering a church.** The sign-in page's Sign up opens Register your church; the personal account stays its own page, "Create your account", for joining a church that already uses CHORD, linked from the wizard and linking back to it.
- **Registering is a four-step wizard** (since the owner's reorder the same day: Church, Profile, Account, Review) with a stepper, a progress bar, a check of each step before the next, and a review with Edit. It is one form, sent once and checked on the server.
- **The name stays the only thing needed; the rest is optional while registering** (address, contact number, email, logo, description, public or not). This amends [[0014-church-platform]] and the Phase 9B rule "Registering a church asks for its name only" (owner's answer, 27 Nov 2026).
- **No banner** for now: the mockup's banner needs a new field and a migration, which the owner left out. No database change.
- **Never a second church from the same page:** each registration page carries a token; the same token sent again by the person who registered goes to that church's setup. The busy button stops a double press first.
- Kept from the card version: the photograph, the password checklist, the busy buttons, the error box, the fade between sign-in and sign-up. First and last name stay optional, as `SignUpForm` has them.

Tests: `apps/church/tests/test_register_wizard.py` (`WizardPageTests`, `WizardRegistrationTests`): the four steps and every field once, multipart, CSRF and the token; the name starts empty (never the model's "My Church"); only the name not marked Optional; Sign in with `next`, Create a personal account, Back to Home and Cancel; a signed-in person sees their own account and Sign out; its stylesheets and scripts, the wizard's before `auth.js`; `register.css` scoped to `.au`; the name alone registers a public church; every optional detail kept, the logo under a random name, Not public kept; a missing name or bad church email opens step 2, an account problem step 1 (the password never sent back), a non-image logo or a long description step 3, nothing created; a chosen logo asked for again after a correction; the same form sent twice, by a visitor or a signed-in person, makes one church and one account; a new page registers another church; someone else's used token never opens that church. `test_platform_accounts.py` now checks that only the name is required; `test_signin_page.py` and `test_signup_page.py` check the full-page wording and links.

#### Sign up is registering a church (owner, 27 Nov 2026)

The owner removed the separate personal sign-up page the same day: church registration is CHORD's sign-up ([[Design-System]], "The sign-in page" and "Registering a church").
- **One sign-up.** The landing page's Sign up (nav, call to action, footer) and the sign-in page's Sign up open Register your church. The person's account is made in its first step (`SignUpForm`, unchanged). There is no second registration page.
- **The old address redirects.** `/accounts/signup/` keeps its name (`accounts:signup`) and sends any request, with its query string, to `/churches/register/`; a form sent to it makes nothing. `SignUpView` and `accounts/signup.html` are gone.
- **Joining an existing church** is the administrator's: Add user, batch accounts from the Members list, and Add an existing account all stay as they were.
- **Requests from outside the church** (Phase 9B rule above): someone with no account can no longer make one just to request an occasion. The owner's plan (27 Nov 2026, to be built later): a request from outside will need no account, with its own form to fill in. Until then only people who already have an account can request from outside.
- This replaces "the personal account stays its own page" in the entry above and the landing page's "No Register your church on the landing page": its Sign up now opens registering.
- Unchanged: the full-page sign-in, the wizard's four steps, its validation, the duplicate-submit token, permissions and authentication.

Tests: `apps/accounts/tests/test_signup_page.py` (`OldSignUpAddressTests`, `AccountStepTests`, `AccountValidationTests`): the old address redirects to registering, with its query string, for visitors and signed-in people, and a form sent to it makes nothing; no page links it or offers a personal account; the account step's fields, checklist, Show buttons and approved wording; mismatched passwords, each of Django's four password rules, a taken username and a missing email shown on step 1 with what was typed kept (never the passwords), nothing made; the CSRF token required. `test_landing.py`: the three Sign up links open registering. `test_register_wizard.py`: no "Create a personal account"; Sign in offered instead.

#### The account step: names, and signing in with an email (owner, 27 Nov 2026)

Asked first, both approved by the owner:
- **First name and Last name side by side, Middle name and Suffix below** (both optional), at every width. First and last name are needed now: with no username of their own, the name is how the account shows.
- **Middle name and Suffix are new optional fields on the account** (`accounts.User.middle_name`, 100 characters; `suffix`, 20; migration `0011_user_middle_name_suffix`), the same lengths as a Member's. They show in the review and on My profile. `get_full_name` is unchanged (first and last name).
- **No username in registration; people sign in with their email.** The email must be no other account's (ignoring case); the username Django still needs is made from it. The sign-in field reads **Email or username**, so older accounts and those an administrator made still sign in with their username. An email two older accounts share signs neither in; they use their usernames.
- Unchanged: administrators' Add user, batch accounts and Add an existing account (by username or email); Django's password rules; CSRF; the redirects.

Tests: `test_signup_page.py`: no username field, the middle name and suffix fields and wording; a used email (any case) and a missing first name refused; the password too like the email refused; the username made from the email, never shared. `test_register_wizard.py`: the full name saved and the new account signing in with its email in another case; first and last name needed (step 1 opens). `test_signin_page.py`: the "Email or username" label and message; an email signs in whatever its case; an email two accounts share signs neither in.

#### The order of the registration steps (owner, 27 Nov 2026)

The owner reordered the wizard, without changing anything inside a step: **1 Church information, 2 Church profile, 3 Account information, 4 Review and confirm**. A correction from the server opens the first step with an error in this order. The review's Edit buttons go to the moved steps. Tests: `test_register_wizard.py` (the order of the stepper and the fields; a church problem opens step 1 before an account problem; the account step is 3, the profile step 2), `test_signup_page.py` (account errors open step 3).

#### The church banner (owner, 27 Nov 2026)

Designed as a mockup with an implementation plan, and approved by the owner with its recommendations ([[Design-System]], "Registering a church" and "The church profile"):
- **A new optional field**, `ChurchProfile.banner` (migration `church/0005_churchprofile_banner`, one added column, no conflict: `0004` was the latest on `master` too). Approved, with the backend changes below, after the owner was told the lead developer works on these forms.
- **Registration step 2:** the banner between the logo and the description, with drag and drop, an immediate wide preview, Replace and Remove, the name, size and pixel size, and the recommended sizes (logo 512 × 512 px, 1:1; banner 1920 × 640 px, 3:1). Checked in the page and again on the server: JPG, PNG or WebP, 5 MB at most.
- **Optimised on the server:** a WebP copy, turned upright, its hidden details (camera, GPS) left out, at most 1920 px wide, never enlarged, cropped or stretched.
- **Public profile:** the banner fills the cover, which takes its 3:1 shape at most 360 px tall; the logo still overlaps it; without one, the green-and-gold cover as before. Directory and showcase cards keep the logo only.
- **Changing it later:** Church settings › Public homepage (Django's upload field: add, replace, or Clear); a replaced or removed file is deleted once the change is saved.
- **Kept:** the step order, layout, colours and fonts; the logo's behaviour. After a correction from the server, the page asks for the banner again (a browser can't keep a chosen file).

Tests: `apps/church/tests/test_banner.py`: the copy is WebP, at most 1920 wide with its shape kept, never enlarged, upright with no hidden details, transparency kept; JPG, PNG and WebP accepted, GIF, PDF and a GIF named `.jpg` refused, more than 5 MB refused; step 2 shows the field between the logo and the description with both recommended sizes and the review cover hook; registering saves `church/banner/<random>.webp` at 1920 × 640; no banner is fine; a bad banner opens step 2 and makes nothing; the banner asked for again after a correction; the public page shows the gradient without a banner, the image with one with the logo still overlapping; directory cards never show it; the Public homepage settings add, replace and clear it, deleting the old files; a bad file is refused there too.

#### Registering goes straight to the dashboard (owner, 27 Nov 2026)

The owner removed the setup wizard after registering: the four registration steps already ask for the church's information.
- **The wizard's four steps were checked first.** Church details, Labels, Modules and Public homepage need nothing registration doesn't ask. The name is the only required value. Website, currency (PHP) and time zone (Church details), the Labels, the Modules (all on that the church may use), and "Show upcoming services" and "Accept requests from outside" (Public homepage) all start from defaults. The church changes them later on the same pages, under Settings.
- **Set up only when the checks pass, not bypassed.** `setup_requirements_met` runs the model's own checks on the new church; only then is it marked `setup_completed`. If they fail, the dashboard still sends its administrator to the wizard, which stays for that case and for the church from before Phase 9B.
- **The time zone comes from the person's device** (a hidden field `register.js` fills in, kept only if CHORD knows the zone); otherwise the default. Currency keeps its default (PHP), as a device can't tell it.
- **The new administrator is signed in and sent to the dashboard**, with a one-time welcome toast ([[Design-System]], "The welcome toast") through Django's messages framework. The same form sent again goes to the dashboard without a second church.
- A set-up, public church can appear in the landing page's showcase, as by the existing rules. Permissions, Modules and the defaults each Module seeds are unchanged.
- Backend changes, no database change: `registration.setup_requirements_met` and `setup_completed` set at registration; the hidden `time_zone` field on `ChurchRegistrationForm`; `RegisterChurchView` redirecting to the dashboard with the welcome message; `base.html` showing the toast.

Tests: `apps/church/tests/test_welcome.py`: signed in and sent to the dashboard, set up; the toast once, right after the navigation bar, never also as an alert, and not after a refresh or a normal sign-in; the device's time zone kept, an unknown or missing one leaving the default; the page sending it; a church that fails the checks still goes through the wizard, without the toast; the same form again goes to the dashboard with one church; a public registered church can be showcased; the script and styles exist. `test_public_settings.py`, `test_platform_accounts.py` and `test_register_wizard.py` expect the dashboard instead of the wizard.

---

#### Dashboard and sidebar redesign (UI/UX owner and lead developer, 27 Nov 2026)

Approved by the UI/UX owner from the interactive mockup on 27 Nov 2026,
with the lead developer's menu layout. Built on branch `joy-ui-ux-v3`.

- **A sidebar on every signed-in page** with a church: deep green, the
  official gold CHORD logo (unchanged, sized only; with no separate emblem
  file, the icon-only sidebar shows the whole logo small), a gold bar on
  the current page. It shrinks to icons from 768 px (the choice is kept in
  the browser; a tablet starts with icons) and is an offcanvas panel on
  phones. Public pages, sign-in and registration keep their own layouts.
- **The menu:** Dashboard; Management (Services: Service Requests, Request
  a Service, My Requests; Bookings: All Bookings, Book a Service); Planning
  (worship services, Calendar, My Schedule, Team Roster, Reports); Songs
  (Song Pool, Find Songs); Members (the church's word: directory,
  Households, Users, Roles and Permissions, Audit Log); Announcements; Settings;
  Sign Out. A link shows only when its Module is switched on and the
  person may open its page; an empty group or category disappears.
  Configuration (Occasion Types, the worship check) stays in Settings.
- **"Services" and "Bookings" are on-screen names** for the Occasions
  Module (the lead developer's naming). Its code, routes, models and data
  keep the name Occasions; the dashboard's reminder reads "service
  requests" (`apps/occasions/dashboard.py`, the owner's approval).
- **The church panel** shows the church's own logo (its initials without
  one) and name, and below it "Church Administration" for its
  administrators, the person's role titles for others, or nothing.
- **No church switcher in the sidebar** (one administrator, one church).
  The account menu keeps the existing switcher for people with more than
  one church and for superusers; switching itself is unchanged until the
  lead developer decides.
- **The figures** (each Module registers them with `register_stat`, for
  people who may open their page, counted for the current church):
  upcoming worship services and confirmed lineups in the next 30 days,
  pending service requests (all, any date), songs in the pool (total);
  smaller: active members (not archived), the person's assignments and
  booked services in the next 30 days. Every figure states its dates.
- **Lineup status:** one bar of the next 30 days' services, confirmed,
  draft and no lineup yet, for people who plan lineups
  (`register_breakdown`); plain CSS, no chart library.
- **Action required, Upcoming, My schedule and Announcements** keep their
  sources and permission rules; **Quick actions** replace "Go to" and list
  only pages the person may open.

Tests: `apps/church/tests/test_app_shell.py` (the shell only on signed-in
pages; the gold logo; the church panel and its role line; no switcher for
one church; the menu by permission and Module; empty categories hidden;
settings pages stay in Settings; the current page marked; the figures,
their dates and their church; figures and quick actions by permission;
the lineup status for planners; a new church's empty states), with
`test_dashboard_screen.py`, `test_views.py` and `test_settings_hub.py`
updated for the new wording and the sidebar's Settings link.

#### No setup wizard; a sidebar that remembers; a leaner dashboard (UI/UX owner, 28 Nov 2026)

- **Nobody is sent through the setup wizard.** Signing in opens the
  dashboard; registering opens it with the welcome toast. An older church
  is marked set up the first time someone who manages it arrives, when
  its saved details pass the same checks registration uses
  (`mark_set_up` in `apps/church/registration.py`, audited). One whose
  details fail them shows a notice on the dashboard linking to Settings ›
  Church details, and stays out of the directory until fixed. Everything
  the wizard asked is in Settings already (Church details, Labels,
  Modules, Public homepage). The wizard's pages still answer at their
  addresses, but nothing links there; removing them is the lead
  developer's call.
- **The sidebar keeps its state between pages:** full or icon-only, which
  categories and groups are open (cookies `chord_sidebar` and
  `chord_sidebar_open`, read by `navigation.py` so the server draws the
  page that way: nothing opens, closes or jumps on load), and where the
  menu was scrolled (session storage, restored before the page shows).
  The category holding the current page always opens; a group starts
  open, a category closed. Pages still load in full: HTMX swapping of the
  content was left out because many pages load their own stylesheets and
  scripts in the head.
- **The dashboard informs; the sidebar navigates.** The only shortcuts
  left ("Create") create a record and have no sidebar link: a worship
  service, an announcement, a member. Each section keeps at most one
  link (Upcoming: View calendar; My schedule; All announcements).
  Upcoming is a list of compact cards (date block left, name, time and
  theme or kind, status, a chevron), each a link to its record; bookings
  have a gold date block and a gold wash. The church name shows only in
  the sidebar's panel (not in the header or the greeting).

Tests: `apps/church/tests/test_app_shell.py` (`SidebarStateTests`), and
updated `test_views.py`, `test_public_settings.py`, `test_welcome.py` and
`test_dashboard_screen.py`.

#### The sidebar replaces the Modules' tab bars (UI/UX owner, 28 Nov 2026)

- **Gone:** the tab bars at the top of the Occasions pages (Occasions,
  Requests, My requests, Settings), Teams (My schedule, Roster, Team
  parts), Worship, Songs and Reports (Schedule, Calendar, Songs, Reports)
  and Members (People, Households), and the Households page's link back
  to the directory. Every destination is in the sidebar, or in Settings
  (Occasion types, Team parts). The templates `worship/includes/nav.html`,
  `occasions/includes/nav.html` and `teams/includes/nav.html` are deleted;
  the Python that builds the old tab lists (`occasions_nav`, `teams_nav`,
  `worship_sections`, `members_sections`) is unused now and left for the
  lead developer to remove.
- **Kept:** tabs that switch something else: between reports, a list's
  filter (upcoming or past, current or archived), and a record's own
  steps.
- **Headings:** each page has one heading named as in the sidebar
  (Bookings, Service requests, My requests, Team roster, Calendar,
  Reports, Households), with a short description only where it helps and
  its own actions beside it (`{% page_header %}`).
- **The waiting count** that the Requests tab carried shows beside
  Service Requests in the sidebar, from the count Occasions already works
  out on every page for approvers.

Tests: `apps/church/tests/test_app_shell.py` (`NoModuleTabsTests`), and
updated `test_members_screen.py`, `apps/teams/tests/test_views.py` and
`test_schedule_screens.py`.

#### Users, roles and the Audit log move under Members (the owner, 28 Nov 2026)

- **Design change:** Users, Roles and Permissions and the Audit Log left
  the Settings hub (its "People and access" category is gone) and are
  links of their own in the sidebar's Members category, after the
  directory and Households. Opening one shows its own page with the
  sidebar marking it, instead of the Settings side menu. They are records
  to manage, not settings.
- They are core, so they stay when the Members Module is switched off;
  each shows only to people with its permission (`accounts.view_user`,
  `accounts.view_role`, `audit.view_auditevent`). A user's add, edit and
  history pages mark Users; the permission matrix marks Roles and
  Permissions.
- Their headings are now each page's `<h1>`, as on other sidebar pages.
  No numbered decision: navigation only, easy to change back.

Tests: `apps/church/tests/test_app_shell.py`
(`test_members_holds_users_roles_and_the_audit_log`,
`test_the_members_links_follow_permissions`) and
`apps/core/tests/test_settings_hub.py`.

#### Simpler church setup and service form (the owner, 28 Nov 2026)

Built on branch `church-setup-simplify`.

- **No sermon series:** the Theme form no longer asks for one, the theme
  card doesn't show it, and the Settings page is gone. A series saved
  before stays in the database, untouched when the theme is edited.
- **The date fills itself in:** a new service's "Date and time" starts at
  the chosen template's next usual day and time
  (`scheduling.suggested_start`): the next matching weekday (today while
  the time is still ahead); with a usual time but no day, today or
  tomorrow; with neither, the next whole hour. Choosing another template
  changes it (`worship/service_form.js`) until the person edits the date.
- **Church details** no longer has Website, Currency or Time zone; the
  public homepage no longer shows a website. Saved values stay; the time
  zone is still taken from the browser when a church registers.
- **No Labels page** (Settings and the setup wizard, now three steps).
  Every church uses the default words; AGENTS.md and
  [[0001-configure-behavior-not-identity]] are amended.
- **The Praise Team under Worship:** on the Modules page Teams shows as
  the Praise Team (the "team" Label), indented under Worship, with its own
  switch (`Module.parent`).
- **The Member Directory is retired** (`settings.RETIRED_MODULES =
  ("members",)`): no church may switch it on, so its sidebar links,
  dashboard count, quick action, settings pages and "My member record"
  disappear, and its pages are 404. It had no records. Its code, tables and
  tests stay (the tests run with the setting emptied); taking "members" out
  of the setting brings it back. Batch accounts from member records go
  with it; Users › Add user still adds people.

Tests: `apps/worship/tests/test_service_date.py`; in
`apps/church/tests/test_views.py` `test_the_praise_team_sits_under_worship`,
`test_switching_the_praise_team_off_keeps_worship`,
`test_no_website_currency_or_time_zone`, `test_there_is_no_labels_page`;
`test_a_retired_module_is_off_for_every_church` (`test_configuration.py`);
`test_no_sermon_series` and `SeriesTests` (`apps/worship/tests/test_schedule.py`).

#### Teams for every church (the owner, 28 Nov 2026)

- **Why:** the Praise Team step was missing for every church registered
  after Phase 9B, because Teams' records weren't kept apart per church and
  the Module was locked for them.
- **Kept apart per church:** Team Parts, Team Profiles (one per person per
  church) and Blackout Dates hold their church; Assignments and Swap
  Requests reach it through their service. Every Teams page reads the
  Current Church's records only (another church's opens as 404), and a
  person on two churches' teams has separate parts and blackout dates in
  each. Teams' `platform_ready` lock is gone.
- **Existing data:** the first church keeps its team; every other church
  gets the neutral starting parts, and Teams is switched on where it had
  been locked (the church never had a switch for it).
- No new numbered decision: it completes [[0014-church-platform]], whose
  note now says so.

Tests: `apps/teams/tests/test_church_teams.py`; the Teams pages are no
longer exempt in `apps/church/tests/test_isolation.py`;
`ModuleAvailabilityTests` (`apps/church/tests/test_platform_accounts.py`).

#### A location picker for the church address (the owner, 28 Nov 2026)

- Under the address at registration and in Church details: **Use my
  current location** (the browser asks the person's permission) and
  **Pick on the map** (click, or drag the pin). OpenStreetMap's Nominatim
  turns the spot into an address that fills the field; the person can
  still edit it.
- **Only the address text is saved** (the owner chose this over storing
  coordinates). The spot goes from the browser to OpenStreetMap only, to
  look up the address; CHORD never sees or stores it.
- **OpenStreetMap's rules:** at most one lookup a second, only when the
  person acts, OpenStreetMap credited on the map. Leaflet is served from
  `static/vendor/leaflet-1.9.4` (checked against the npm registry's
  sha512), like Bootstrap and htmx.
- Without JavaScript the picker stays hidden and the field works as before.
- **The Referer:** OpenStreetMap's tile and Nominatim servers refuse
  browser requests that don't say which site they come from ("Access
  blocked" tiles), and Django's default `Referrer-Policy: same-origin`
  drops the Referer on them. The map and the lookups ask for
  `strict-origin-when-cross-origin`, so OpenStreetMap gets the site's
  origin only, never a page's path; the rest of CHORD keeps `same-origin`.

Tests: `LocationPickerTests` (`apps/church/tests/test_views.py`). Checked
in headless Chrome against the dev server: the current location (a test
position) filled in the address, the map loaded, and clicking the map
changed the address.

#### Date and time as two boxes (the owner, 28 Nov 2026)

- Every date-and-time field (a service's date and rehearsal, booking and
  requesting a service, the public request form) is a date box with a
  calendar icon beside a time box with a clock icon, instead of one
  combined box. A click anywhere in a box opens the browser's picker.
- The browser shows the date in the device's own format (e.g. 11/28/2026);
  matching "Nov 28, 2026" exactly would need a date-picker library.
- A date without a time is refused rather than read as midnight.

Tests: `apps/core/tests/test_moment_input.py`, and
`apps/worship/tests/test_service_date.py`. Screenshots of the new-service
form at desktop and narrow widths.

#### Sign up while requesting a service (the owner, 28 Nov 2026)

- **Design change:** on 27 Nov signing up for CHORD meant registering a
  church. Now a visitor can also make an account while requesting a
  service from a church's public page. Registering a church is unchanged.
- **The flow:** the visitor fills in the request (date and time, who it's
  for, a note) and presses Send. A pop-up asks their first and last name,
  email and a password; a 6-digit code is emailed; the right code makes
  the account, signs them in and sends the request.
- **The account joins that church** with the Church Member role (the
  schedule and announcements; requesting services). It can still request
  services from other churches, without joining them.
- **Only where the church accepts requests from outside**; at a church for
  its own people, a visitor signs in first as before, so nobody joins a
  closed church by asking for a service.
- **An email with an account already** signs in right there and sends the
  request; that account isn't added to the church. This tells a visitor
  that the email has an account, which the owner accepted for the
  convenience.
- **Safeguards:** only a keyed hash of each code is stored; the password
  waits only as Django's hash; codes last 10 minutes, end after 5 wrong
  tries, can be resent after 60 s, and at most 5 go to one address an
  hour. Nothing is made before the code is right.
- **Email delivery** uses Django's email settings: the console by default,
  a real mail server once `DJANGO_EMAIL_*` is set in `.env`.

Tests: `apps/occasions/tests/test_visitor_signup.py`; updated
`RequestThisServiceTests` (`apps/church/tests/test_public_pages.py`).
Walked through the first two steps in headless Chrome on Test Church's
Wedding (no account made).

#### Request links only for people who request (UI/UX owner, 28 Nov 2026)

The sidebar leaves out Request a Service and My Requests for anyone who may
approve service requests (`occasions.approve_occasion`: every
administrator, and any role the church gives that power, such as the
pastoral staff by default). They manage the incoming requests and book
directly. People who may request without approving keep both links. A
permission, not a role name (`AGENTS.md`); the pages, routes and
permissions are unchanged, so the pages still open by their address. Test:
`test_app_shell.py`, `test_people_who_approve_requests_do_not_get_the_request_links`.

#### Signed-in website access and the Church CMS (UI/UX owner, 28 Nov 2026)

Phase 1 of the approved UI/UX implementation (interactive mockup approved
by the UI/UX owner; branch `joy-ui-ux-v3`).

- **The landing page for signed-in people:** `/` stays the dashboard once
  signed in; the landing page is also at `/welcome/` (`landing`), for
  everyone. Signed in, its nav shows an account button (initials) with a
  menu: name and role line, **Dashboard**, **My Church** (only when the
  church's page can be opened: public, or the person manages it) and
  **Sign Out** (POST). Since Phase 2 this is the shared account popover
  ("Personal profile", below). No hero buttons and no "signed in" banner; the
  footer's Sign in and Sign up become Dashboard and My Church.
- **Sidebar:** the CHORD logo opens the landing page (tooltip "Go to
  Homepage"); there is no View Website link. The church panel links to the
  church's page with a small "View page" mark, when that page can be
  opened.
- **Church CMS:** the people who manage the church
  (`church.change_churchprofile`, a permission, not a role name) edit its
  page from the page itself: hover or focus the cover or logo for a camera
  menu (change or remove; logo 512 × 512 px, cover 1920 × 640 px), and
  **Edit profile** opens a modal with a live preview, Church information
  (name, About), Contact (address with the OpenStreetMap location picker,
  phone, email) and Public page (the three switches). It saves through
  `church:profile_edit` (POST `/church/profile/edit/`, `part` = `all`,
  `logo`, `banner`, `logo-remove` or `banner-remove`; anything else 404),
  which always edits the Current Church only, validates with the same two
  Settings forms, records the audit trail, and on errors returns the page
  (400) with the modal reopened. No new fields, no migration; Website,
  Currency and Time zone stay removed. **View as visitor** hides every
  editing tool until Exit preview.
- **Awaiting the lead developer's approval: a private church's own page.** Slice e
  ("Public pages", below) makes a church with "Show the church publicly"
  off 404 to everyone. The CMS lets the people who manage it open their
  own page anyway, with a notice that it isn't public yet, so they can
  build it before going public. Everyone else, its team included, still
  gets 404. If not approved, `church_for_page` goes back to public
  churches only and the editor stays reachable only for public churches.
- Tests: `apps/church/tests/test_church_cms.py`; `test_public_pages.py`
  (`a hidden church` stays 404 for its team member).
- The landing page's third pillar reads **Your modules / Switch on what
  you use** (was "Your wording / Set by your church", untrue since Labels
  stopped being editable on 28 Nov 2026).

#### Personal profile (UI/UX Phase 2; revised 28 Nov 2026)

**The lead developer rejected personal profile pictures and bios (28 Nov
2026).** The UI/UX owner revised Phase 2 to fit: no new fields on
`accounts.User` and no migration. Out of the design for good: personal
profile picture upload, About Me or bio, a personal banner, a camera
overlay on personal avatars, and the picture and bio fields with their
migrations. Don't add them back without the lead developer's agreement.
The church's logo and cover (the Church CMS, above) are a separate
feature and stay as they are.

What Phase 2 builds instead, kept professional for a church management
system rather than a social profile:

- **One account popover** for every signed-in page
  (`templates/includes/account_popover.html`, `static/css/account.css`,
  `static/js/account_menu.js`): in the app header it replaces the old
  dropdown (initials and name); on the landing page and church pages it
  replaces Phase 1's menu (initials only, on the green bar). A compact card
  with the **initials avatar** (first and last name, else the username's
  first letter: `User.initials`), the **full name** (first, middle, last,
  suffix: `User.display_name`), the **role line** (as in the sidebar) and the
  **church**; then **Edit Profile**, the church switcher (only with more than
  one church), the person's own links (app: My schedule, My requests at any
  church, Spotify account, Churches; public: Dashboard, My Church),
  **Appearance** (a Light, Dark, Device switch: the page changes at once
  with a short cross-fade, the thumb slides, and the choice saves in the
  background to `accounts:appearance`; without JavaScript each choice is a
  form button that returns to the page), **Account Settings** and
  **Sign Out**. Edit Profile is a text-only button (no icon). It slides in, closes on a click
  outside, Escape, Tab or choosing an item, and arrow keys, Home and End move
  through it.
- **Edit Profile** is a native dialog with a live preview of the initials
  and full name and four fields only: first name and last name (required),
  middle name and suffix (optional). It posts to `accounts:profile_edit`
  (`/accounts/profile/edit/`, `PersonalInfoForm`), which changes only the
  person's own name fields, tidies extra spaces and records the audit trail
  (Middle name and Suffix now recorded too). The modal saves in the
  background (JSON), updates the name and initials on the page and shows a
  toast; errors show under each field; closing with unsaved changes asks
  first. Without JavaScript it posts normally and returns to the page
  (`next`, same site only); errors show on an "Edit profile" page. On phones
  it opens as a bottom sheet.
- **Account Settings** is the old "My profile" page, renamed, with links to
  Change password and Appearance, and now in the Settings hub as
  **Personal › Account** (before Appearance), so a person without church
  settings gets Account settings from the gear.
- **The official CHORD logo goes home everywhere** (UI/UX owner, 28 Nov
  2026): signed in, to the landing page at `/welcome/` (never the
  dashboard), still signed in; a guest, to the landing page at `/`. One
  template tag, `{% homepage_url %}` (`apps/church/templatetags/church.py`),
  for the sidebar, the landing page's nav, the church directory, the church
  page, the sign-in pages and the registration wizard, each with a "Go to
  Homepage" tooltip (`chord-home-tip` in `chord.css`; the sidebar keeps its
  own). The landing page's footer logo still goes back to the top, and church
  logos keep their own links. The landing page now follows a signed-in
  person's own Appearance choice; a guest's follows the device.
- Tests: `apps/accounts/tests/test_account_popover.py`.

#### Remaining UI/UX tasks (28 Nov 2026)

The full plan, phase by phase, is [[UI-UX-Master-Plan]]; motion follows
[[Animation-Plan]]. The simplified Phase 2 supersedes the original personal
profile plan: personal profile pictures, bios and banners are rejected.

1. Lead developer's approval of the private-church preview (above).
   Whatever the answer, everyone else keeps getting 404.
2. Phase 2: the simplified personal profile (above): done, approved by
   the UI/UX owner and committed on `joy-ui-ux-v3`.
3. Phases 3 to 11 in the order of [[UI-UX-Master-Plan]]: Shared UI
   Components; Management, Services and Bookings; Worship Planning, Song
   Recommendations and Lineup Builder; Songs, Song Pool, Find Songs, Chord
   Viewer, Chord Editor and Rehearsal; Calendar and Scheduling; Members and
   Teams; Announcements and Notifications; Settings and Reports; the final
   consistency, responsiveness, accessibility and animation audit. Each is
   committed on its own and pushed to `origin/joy-ui-ux-v3`; the UI/UX
   owner reviews the whole site at the end. Phases 3 to 7 are done.

## Phase 9B: Church Platform ([[0014-church-platform]])

Approved by the owner on 2026-11-25. The full design is [[Phase-9B-Plan]];
these are the rules every slice keeps, and the tests that prove them.

### Rules

- **The core rule holds.** Registering a church needs only its name
  (since 27 Nov 2026 the person may also give its details and public
  profile while registering, all optional: "Authentication pages and the
  registration wizard").
  No denomination, tradition or religion field in any new model, form,
  seed row or page; `test_denomination_free.py` covers the new forms.
- **Permissions come only from the Current Church.** `ChurchRoleBackend`
  returns the permissions of the user's roles in their Membership in the
  Current Church, and nothing else: not `user.groups`, not permissions
  granted straight to a user. With no Current Church, a user holds no
  permissions. Active superusers hold every permission (Django's own
  rule) and may switch into any church.
- **The Current Church** is kept in the session and checked on every
  request against an active Membership; without a valid choice it is the
  person's first membership (oldest first).
- **Every scoped query goes through the church.** Root models carry a
  `church` foreign key; children are reached through their parent.
  `for_church(church)` and `get_in_church()` are the only ways views read
  scoped records. A record from another church gives **404**, never 403.
- **The church is never taken from a form.** New records get it from
  `request.church`. Every ModelChoiceField on a scoped model lists only the
  Current Church's rows.
- **Code without a request** (the worker, notifications, approvers) works
  through each row's own church and `users_with_perm(church, perm)`.
- **Global on purpose:** `User`, `SpotifyConnection`, `SpotifyLimit` (the
  shared 429 block, one for every church), `SignInEvent`. The worker stays
  one process with one advisory lock.
- **LRCLIB lyrics are shared as a cache** (owner, question 1): a church
  adding a track whose lyrics another church already fetched copies them
  instead of asking LRCLIB. Lyrics are never shown across churches;
  analysis, tags and chord sheets stay per church.
- **Members and Teams are locked** for every church without
  `members_teams_unlocked` (only the migrated first church has it); they
  show as "Not available yet". This branches on a church setting, not on
  which church it is.
- **Public pages** (Directory, Church Homepage) show only what the church
  chose to publish: name, logo, contact details, About, Public
  announcements, Occasion Types offered publicly and, if switched on,
  upcoming services as date, time and kind. Never lineups, songs, chord
  sheets, lyrics, members or teams.
- **Requests from outside the church** (owner, question 2): a church
  setting, "Accept requests from people outside the church", on by
  default. Any signed-in account may then request an Occasion Type the
  church offers publicly; the overlap check and approval are as in A5.
  (Since 27 Nov 2026 there is no personal sign-up; the owner plans a
  request form that needs no account, to be built later: "Sign up is
  registering a church".)
- **Nothing is lost in the migration.** The first church keeps every row;
  every existing user, active or not, gets a Membership there with exactly
  the roles in their `user.groups`, which is left in place so the
  migration can be reversed.
- **A church manages an account only when it is the church's alone**
  (slice c, must-do 1): username, names, email, Active and password; its
  roles there are always the church's to change.
- **Sign-in history of shared accounts** (owner, 2026-11-26, option a):
  sign-ins belong to the account, not to a church. A church sees an
  account's sign-ins only when the account belongs to that church alone and
  isn't a superuser's: the same test as editing the account and setting its
  password (`memberships.may_manage_account`). For any other account, the
  user's History page in that church still lists every change the person
  made in that church, from its own Audit Trail, but its Sign-ins section
  reads "Shared account: sign-ins not shown", and no sign-in rows are read.
- **Nothing public until the church chooses** (owner, 2026-11-26): the
  church from before 9B starts with "Show the church publicly" off, every
  Occasion Type starts not offered publicly (existing and seeded), "Show
  upcoming services" starts off, and "Accept requests from people outside
  the church" starts on. A newly registered church is public from the
  start, as the plan said, unless the person chooses Not public while
  registering (27 Nov 2026).
- **About** is plain text: stored as typed (trimmed), shown escaped with
  its line breaks (`church/includes/about.html`).
- **The logo** is an image only (Pillow, PNG, JPEG, GIF or WebP), 2 MB at
  most, saved as `church/<random>.<ext>` in the public media folder, so
  its address names neither the file chosen nor any private folder.

### Tests

- Every test from before 9B still passes after slice a, before any
  scoping.
- The backend: permissions follow the Current Church; a user with roles in
  Church A holds none of them while working in Church B; switching to a
  church without a Membership is refused; `user.groups` grants nothing.
- The migration (`MigrationExecutor`): back to before 9B, build data,
  forward again; every row has the first church, row counts are unchanged,
  and each user's Membership roles equal their old groups.
- Isolation: a user in Church A gets 404 on every detail, edit and action
  page for Church B's records, found automatically from the URL patterns
  that take an object ID; Church B's rows are missing from every list and
  every form's choices.
- `seed_church` gives a new church its own default roles, theme tags,
  template, settings rows and switched-off Occasion Types, and leaves the
  other churches unchanged.
- The worker and notifications use each row's church: analysis uses that
  church's tags and trusted artists, and only that church's approvers are
  notified.
- Sign-in history: an account of this church alone shows its sign-ins;
  an account also in another church shows the changes made here but no
  sign-ins, which aren't read; a superuser's account shows none
  (`apps/church/tests/test_public_settings.py`).
- Public pages: anonymous visitors, people from other churches and members
  see only the published fields; a request from outside the church is
  refused when the church turns the setting off
  (`apps/church/tests/test_public_pages.py`).

### Public pages (slice e, owner, 2026-11-26)

- A church with "Show the church publicly" off has no public page: it is
  absent from the Directory, and its homepage and request addresses are
  404 to everyone; unknown addresses too.
- Only Public announcements to everyone that aren't archived; only
  active Occasion Types offered publicly (any other is 404 on its request
  address); upcoming services, if switched on, only as date, time and
  kind; no request buttons, and 404 request addresses, while Occasions is
  off.
- Request this service: a visitor signs in and returns to the same form
  (a safe `next` only); someone outside the church only while it accepts
  requests from outside; the usual overlap check; the church's approvers
  are notified; anyone outside the church reads others' bookings only as
  "Booked", worship services included.
- My requests: one's own requests at every church; withdraw one's own
  Pending ones only.

---

## Phase 9C: guided service planning (owner, 2026-11-26)

The owner found planning a new service had extra steps and no guidance.
Top priority (AGENTS.md). It replaces the A7 five-step bar (Theme,
Suggestions, Lineup, Confirmed, Playlist) described above.

### The owner's choices (2026-11-26)

- **Four steps:** Theme, then the Praise Team (who serves that day), then
  Song Lineup (suggestions, the lineup and the playlist as one step), then
  Confirm (a quick rundown of what will be confirmed).
- **Guidance is a next-step panel** on the service page, every time, not a
  one-time tour: what to do next and one button for it, until the lineup is
  confirmed. Each step in the bar is a link.
- **The team step is guided but can be skipped:** the panel suggests
  assigning the team, with "Skip for now" to Song Lineup. Confirm's rundown
  warns when nobody is assigned. It never blocks the songs.
- **The playlist is previewed during Song Lineup and saved on Confirm,** as
  today (Phase 7): saving earlier would show a draft on a public Church
  Spotify Account playlist, against "the team sees a lineup only once it
  is confirmed".

### Rules

- **The steps follow the church's settings.** The team step shows only
  while Teams is switched on (otherwise there are three steps). Its name is
  a new church Label, `team` (default "Praise Team"); Song Lineup is "Song
  <lineup Label>" (just the Label when it already says "song").
- **A step is done** when: Theme, a theme is posted; Praise Team, at least
  one person is assigned and hasn't declined; Song Lineup, a lineup with
  at least one song exists; Confirm, the lineup is confirmed.
- **The current step** is the first one not done, except the team step,
  which stops being current once songs are being chosen (a search ran or a
  lineup exists) or the roster is closed (a cancelled or past service).
- **Next-step panel:** only for people who plan, never on a cancelled
  service. It names the next step, says why, and gives one button when the
  person may do it ("Post the theme", "Assign the <team>", "Choose the
  songs", "Review and confirm"); otherwise it says who it waits for. Once
  confirmed, it says the team can see the lineup and links to it.
- **Each step links to its page:** Theme to the theme form (or the theme
  card for people who can't change it); Praise Team to the assign page (or
  the team card); Song Lineup to the lineup page; Confirm to the rundown,
  once a lineup exists.
- **Song Lineup page** (`worship:lineup`): for people who may suggest
  songs it opens before a lineup exists and shows the suggestions panel
  (Find songs, the progress, the ranked songs and "Save these songs as the
  <lineup>"; *replaced the same day by "The lineup comes first" below:
  the slots first, the suggestions beside them*). Once the lineup exists
  it shows the lineup review as before, and a **Playlist** card: which
  songs have a Spotify track and where the playlist will be saved on
  confirmation. Its one primary button is "Continue to confirm". The
  service page no longer shows the suggestions.
- **Confirm rundown** (`worship:lineup_confirm`, GET): the service's date,
  time and rehearsal; the theme; the team with replies (while Teams is on
  and the person may see it); the songs in order with slot, key and chord
  sheet; warnings (nobody assigned, places declined or still pending,
  empty slots, songs without a chord sheet or without a key, Worship Check
  warnings); and where the playlist will be saved, or why it won't be.
  Warnings never block confirming. The Confirm button shows to people who
  may confirm (`lineups.may_confirm`); confirming (POST, unchanged rules)
  returns to the service page.
- **Assigning in one go:** after assigning someone, the assign page stays
  open, showing the team so far; "Done" returns to the service page.
- **The pastor assigns the team by default:** the owner's steps have the
  pastor assign the team, so Pastoral Staff now also holds
  `teams.add_assignment` and `teams.delete_assignment` by default (Worship
  Leader keeps them). A church can take them away in its roles; the panel
  then says the step waits for someone else.
- **Unchanged:** who may do what, the pastor's lock, sending back,
  reopening, and saving the playlist on confirmation. Team members never
  see the step bar, the panel, suggestions or a draft; they keep the
  service page and the confirmed lineup as before.

### Sermon PDF (owner, 2026-11-26)

The owner asked for the pastor to attach the sermon as a PDF, to use it,
and for suggestions to match the theme better from it, since it is what
will be preached.

- **On the theme form:** an optional "<sermon Label> PDF", up to 15 MB.
  Only a real PDF is accepted (a `.pdf` name and the `%PDF-` header); a
  damaged or password-locked one is refused with a reason.
- **Private:** stored in private storage (`worship/sermons/<random>/`),
  never public. Only people who plan (`worship.change_theme` or
  `worship.change_lineup`, who also see the notes) see the link and open
  it, in the browser; the team never does (403). Another church's PDF is a
  404. Replacing or clearing it deletes the old file.
- **Its text is read once, when attached** (pypdf; at most 200 pages and
  200,000 characters), and kept on the theme (`document_text`), so the
  search worker never opens PDFs. A scanned PDF has no text: it is kept,
  and the pastor is told suggestions use the title, passage and notes.
  The audit trail records the file's name, never its text; nothing of it
  is logged. It is the church's own theme text, so the models may read it
  (AGENTS.md); it never leaves the installation.
- **Matching reads all of the theme** (`apps/worship/reading.py`): the
  embedding model reads at most 256 tokens and would cut a long text off,
  so a theme longer than 150 words is read in passages of 150 words (at
  most 24, spread from start to end). A short theme is read whole, as
  before. This also helps long typed notes.
- **Each part has its own share** (owner, 2026-11-26, after seeing that a
  10-page PDF outweighed short notes about 90 to 1): the heading (title
  and scripture reference) is half of the theme's vector, and the body's
  parts (the notes, the passage's Bible text, the PDF's text) share the
  other half equally, whatever their length; an empty part leaves its
  share to the others. Theme Tags average each part's passages, then the
  parts. Search phrases are drawn from the heading and each part in equal
  numbers, then ranked against the theme's vector. The owner accepted the
  trade-off: a one-line note counts as much as the whole sermon.
  Tests: `test_sermon_pdf.py`, `EqualSharesTests`.
- The "add notes" hint doesn't show when the PDF has text.

Tests: `apps/worship/tests/test_sermon_pdf.py`: attaching reads the text
and keeps the file private; only planners open it; non-PDFs, damaged and
oversized files are refused; a scanned PDF is kept with a warning;
replacing or clearing deletes the old file; saving without a file keeps
the text; the audit trail holds the name only; no text longer than a
passage reaches the model, and the end of a long sermon does; tags and
phrases come from the PDF; a run reads it. `test_isolation.py` covers
another church's PDF.

### Main scripture from a stored Bible (owner, 2026-11-26)

The owner asked for a Bible stored in CHORD, so the Main scripture field
suggests passages as the pastor types. Owner's choices: references and
the text of a public-domain translation; the deuterocanonical books as a
church setting.

- **The Bible:** the World English Bible (public domain; eBible.org's
  2020 stable text), kept exactly as published in
  `apps/worship/bible/data/web.json.gz`, with its source in the folder's
  README. Copyrighted translations (NIV, ESV and the like) can't be
  bundled.
- **Which books:** the 66 books shared by every church's Bible always.
  **Bible settings** (Settings, Worship, Services, Bible;
  `BibleSettings.include_deuterocanon`, off by default; permission
  `worship.change_biblesettings`, held by Pastoral Staff) adds the 15
  deuterocanonical books of the World English Bible. Church practice is a
  setting, never a denomination (decision 0001).
- **Browsing** (owner, 2026-11-27): clicking the field opens the list.
  Empty, it lists every book in order with its chapter count; picking a
  book lists all its chapters with their verse counts; picking a chapter
  lists **Whole chapter** first, then every verse with its first words.
  The list scrolls; it stays open while browsing.
- **Typing:** the field suggests books (by name or abbreviation: "jn",
  "1 cor", "I Corinthians", "ps"), then chapters, then verses, all that
  match; only numbers after a name that fits several books ("jo 3") are
  kept to 8, each book's best match first. Arrow keys, Enter and a click
  pick one (an ARIA combobox: `worship/scripture.js`). Any text is still
  accepted ("Various passages"); "John 3:" left mid-browse saves as
  "John 3".
- **The passage** shows under the field as soon as the field names one:
  while typing or browsing (half a reference shows nothing, not "Not
  found"), and when one is picked. Folded ("Read John 3:16"), it shows on
  the theme card for everyone who sees the theme (it is public domain). At
  most 80 verses are shown and read.
- **Song suggestions read it:** the passage's text is kept on the theme
  when it is saved (`Theme.scripture_text`; migration
  `worship/0016_bible` fills it for existing themes) and is part of the
  theme's body, read in passages like the notes and the sermon PDF. A
  setting change applies to a theme the next time it is saved.
- References are written in one style: "Psalm 23" (one psalm), "Psalms
  23-24", "John 3:16-18", "Romans 8:28-9:2".

Tests: `apps/worship/tests/test_bible.py`: every book has its text and no
abbreviation is shared; references are read however they are written,
and what isn't one is refused; the deuterocanonical books follow the
setting; long passages are cut at 80 verses; suggestions for books,
chapters, verses and ranges; the passage text is kept and matched, and
the migration fills it; only people who post themes get suggestions; the
theme card offers the passage to everyone; the setting is audited and
needs its permission.

### The lineup comes first; suggestions assist (owner, 2026-11-26; [[0015-lineup-first-suggestions-assist]])

The owner asked for the pastor to add songs on their own judgement, with
the suggestions as help rather than the main thing. Owner's choices: the
song slots first with the suggestions beside them; songs come from the
church's song pool or from Spotify only (typing or uploading a song of
one's own may come later).

- **Song Lineup page:** the service's slots in order, the lineup's songs
  in them, and each empty slot with **Add a song**. Beside it (below on a
  phone), **Suggested songs**: each ranked song with **Add**, "In the
  lineup" once it is, and **Fill the empty slots with suggestions**.
- **Starting:** the lineup starts, empty, with the first song added
  (`lineups.start`; needs `worship.add_lineup` and `change_lineup`; not
  for a cancelled or past service). If that first song is refused, no
  empty lineup is left behind.
- **Add a song:** search the pool by title or artist, choose the slot (the
  one clicked is chosen), or "Find it on Spotify", which adds the track to
  the pool and comes back to the same page looking for it.
- **Add (a suggestion):** into its own slot when empty, otherwise the
  first empty slot, otherwise at the end. The song keeps the suggestion's
  reasons, and the suggestion is followed as **picked**, a new Suggestion
  Feedback label and a positive like kept.
- **Fill the empty slots:** with no lineup, the suggestions make the whole
  lineup as before ("kept"); with one, only its empty slots are filled and
  every song already there stays (`lineups.fill_from_suggestions`).
- **Unchanged:** review (swap, lock, move, key and notes, remove,
  regenerate around locked songs), confirming, the pastor's lock, and who
  sees a draft. "Save these songs as the lineup" is gone.
- **Pastoral Staff holds `songs.add_song`** by default now, so the pastor
  can bring a song in from Spotify.

Tests: `apps/worship/tests/test_lineup_first.py`: a lineup starts empty
and only once, never for a cancelled service or without permission; a
suggestion goes to its slot or the first empty one, keeps its reasons and
becomes "picked" feedback, while pool songs leave none; filling keeps the
songs already chosen and refuses when every slot is full or there are no
suggestions; the page shows empty slots with Add a song and the
suggestions with Add; the team still gets 404 before confirmation; a
refused first song leaves no lineup; Find on Spotify comes back.

### Tests

- The step bar has four steps with Teams on and three with it off; each
  step links to its page; the current step follows the rules above
  (including the skipped team step).
- The panel shows the right step and button for a new service, after the
  theme, after the team, after a search, for a draft and when confirmed;
  it is absent for the team and on a cancelled service.
- The lineup page opens with the suggestions for a planner before a lineup
  exists and still 404s for a team member; finding songs and saving the
  lineup return to it.
- The rundown lists the service, theme, team, songs and each warning; the
  Confirm button shows only to people who may confirm; confirming returns
  to the service page and still saves the playlist; a team member can't
  open it.
- Assigning returns to the assign page; the team label shows where the
  team is named.

---

## Phase 9: learning to rank

### Keep Spotify data out of training

- Training features may include only: lyrics-based scores (embedding similarity, raw model worship score, tag scores), the church's own data (team knows, usage, season, slot), and feedback labels (kept, swapped, removed).
- Never use as a training feature: the Spotify artist name, title, album, track ID, length, the Trusted Artist bonus, or any score that includes the bonus. Use `worship_model_score`, not the adjusted score. The same holds for the rule for artists not on the Trusted Artists list, which version of a song was kept, and the genre-filter record on a Search Run.

Test: the feature list used for training contains none of the forbidden fields.
