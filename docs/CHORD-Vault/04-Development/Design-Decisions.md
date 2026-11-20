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

- When a lineup is confirmed, it is saved automatically as a Spotify playlist on the worship leader's account.
- If the worship leader has no Spotify connection, or Spotify returns a 429, the playlist is skipped and the lineup page shows a "Save to Spotify" button to try again later. Confirming the lineup never fails because of Spotify.

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
  - **Only what breaks the ChordPro text itself stops a save**: an unclosed bracket, a directive not alone on its line or not closed, a section opened but never closed, or no chord at all.
  - In the viewer, marks kept as written are shown apart from chords (grey italic). When the sheet has such marks and is shown moved from its own key (another key, a capo or Nashville numbers), a short note under the sheet says "Some marks were kept as written and aren't transposed." N.C., repeat and footnote marks are standard chart marks, not kept-as-written ones: they get neither the style nor the note.
- A team member's import follows the same rule as a paste: pending until approved.
- A person still brings in each chart. Nothing is fetched from any site.

Tests (made-up content only): the key read from `{key:}` and from `{k:}`; a file without a key; a wrong extension; a file over 200 KB; a file that isn't UTF-8; other directives kept and the song unchanged; a rhythm line that transposes, and one that becomes a comment; a team member's import staying pending; a bracketed rhythm line with spaces (D to E gives E and A), with none and with `||` bars; an unreadable bracketed line becoming a comment while the sheet saves; "Verse 1" and "Outro" lines showing as section labels; "(F#m7)" transposing with its parentheses; N.C. and x2 kept and not transposed; an unreadable mark such as "[Zz9]" saved as an annotation with the warning; an unclosed bracket still an error; the viewer's note showing only when the sheet has kept marks and is shown away from its own key.

---

## Phase 8: team and community

### Attendance (question 6)

Decision: a headcount per service. The existing `WorshipService.attendance` field is enough; no per-person attendance.

### Notifying the team of a pastor's edit

- Once assignments exist, when the pastor (a holder of `worship.finalize_lineup`) edits a confirmed lineup, the team members assigned to that service are notified in the app. No email or SMS.

Test: after the pastor edits a confirmed lineup, each assigned team member has an in-app notification, and nobody else does.

### Administrator role (question 7)

Decision: keep the Administrator role undeletable, with every permission. Update the spec, which calls Admin "optional".

---

## Phase 9: learning to rank

### Keep Spotify data out of training

- Training features may include only: lyrics-based scores (embedding similarity, raw model worship score, tag scores), the church's own data (team knows, usage, season, slot), and feedback labels (kept, swapped, removed).
- Never use as a training feature: the Spotify artist name, title, album, track ID, length, the Trusted Artist bonus, or any score that includes the bonus. Use `worship_model_score`, not the adjusted score. The same holds for the rule for artists not on the Trusted Artists list, which version of a song was kept, and the genre-filter record on a Search Run.

Test: the feature list used for training contains none of the forbidden fields.
