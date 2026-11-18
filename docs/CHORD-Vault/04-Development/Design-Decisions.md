# Design decisions and safeguards for CHORD

**For Claude Code:** read this file before starting any development phase. Each section says which phase it applies to. When you start that phase, build what the section describes and add the listed tests. Don't build items for a later phase early.

Sources rank in this order (`AGENTS.md`): the rules in `AGENTS.md`, the numbered decision records, this file, `docs/CHORD-Vault/01-Project/Concept-Brief.md`, `docs/CHORD-Vault/workflow-spec.md`, then `docs/CHORD-Vault/04-Development/Development-Plan.md`. If this file disagrees with the Concept Brief, the spec or the plan, this file wins. Update the lower source to match, and say so in your summary.

These decisions answer the open questions in `docs/workflow-review.md`, section 4.

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

## Phase 6: lineups and confirmation (current)

### The pastor's decision is final (question 9)

- Either the worship leader or the pastor can confirm a lineup.
- If the leader confirms and the pastor later edits it, the lineup stays confirmed. It is marked "Edited by pastor" with the time, and the mark is shown to everyone who can see the lineup. Phase 6 has no notification system; Phase 8 adds notifications (see below).
- Once the pastor has confirmed or edited a lineup, the worship leader cannot change it. The pastor can reopen it, which lets the leader edit again.
- Team members see a lineup only after it is confirmed.

Tests, for every role:
- The leader can confirm.
- The pastor's edit keeps the lineup confirmed and marks it with the time, and everyone who can see the lineup sees the mark.
- The leader is blocked after the pastor confirms or edits.
- Reopening by the pastor unblocks the leader.
- A team member cannot see an unconfirmed lineup, by page or by URL.

### Song usage

- Fill in `ranking.song_usage()` from confirmed lineups, so the familiarity and recent-use parts of ranking start working.

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

---

## Phase 8: team and community

### Attendance (question 6)

Decision: a headcount per service. The existing `WorshipService.attendance` field is enough; no per-person attendance.

### Notifying the team of a pastor's edit

- Once assignments exist, when the pastor edits a confirmed lineup, the team members assigned to that service are notified in the app. No email or SMS.

Test: after the pastor edits a confirmed lineup, each assigned team member has an in-app notification, and nobody else does.

### Administrator role (question 7)

Decision: keep the Administrator role undeletable, with every permission. Update the spec, which calls Admin "optional".

---

## Phase 9: learning to rank

### Keep Spotify data out of training

- Training features may include only: lyrics-based scores (embedding similarity, raw model worship score, tag scores), the church's own data (team knows, usage, season, slot), and feedback labels (kept, swapped, removed).
- Never use as a training feature: the Spotify artist name, title, album, track ID, length, the Trusted Artist bonus, or any score that includes the bonus. Use `worship_model_score`, not the adjusted score. The same holds for the rule for artists not on the Trusted Artists list, which version of a song was kept, and the genre-filter record on a Search Run.

Test: the feature list used for training contains none of the forbidden fields.
