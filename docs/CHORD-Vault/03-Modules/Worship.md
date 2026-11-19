---
status: in progress
---

# Worship

Planning worship services: the schedule, each service's theme, and (in
later phases) song suggestions, lineups and song pages. Module code
`worship`; apps `apps/worship` (planning) and `apps/songs` (the song pool,
from Phase 4). This is the core of the [[Concept-Brief]].

## What exists

Built in Phase 3 (`apps/worship`):

- **Service Template** (`models/schedule.py`): a church-edited kind of
  service, such as the main weekly service or a youth night.
  - Ordered **Song Slots**, each with a name and an optional feel (upbeat,
    mid-tempo, slow, or any).
  - An optional usual day and start time, given together, which make the
    template schedulable weeks ahead.
  - One neutral template is seeded: "Worship Service" with Opening
    (upbeat), Praise (mid-tempo), Worship (slow) and Response (slow).
  - Templates are switched off, never deleted.
- **Worship Service**: name (the template's name unless given), template,
  date and time, rehearsal time (must be earlier), notes, headcount and a
  cancelled flag. A template can't have two services at the same moment.
  Public UUID in URLs.
- **Theme**: one per service, with title, main scripture, notes and an
  optional **Series**. It records who posted it. The notes are shown only
  to people who plan (those who can edit themes or lineups).
- **Series**: a church-edited list.
- **Screens** (`/worship/`):
  - the schedule: Upcoming and Past, with search over names and themes;
  - a month calendar (`/worship/calendar/?month=YYYY-MM`);
  - a service page with its theme, details and attendance;
  - add and edit a service; post and edit its theme;
  - **Schedule weeks ahead**: adds the chosen template's service on its
    usual day and time for up to 26 weeks, in the church's time zone, and
    skips dates that already have it;
  - settings: Service templates (with their slots) and Series.
- **Rules** are in `scheduling.py` (weekly scheduling, the calendar grid,
  audit fields), and the forms in `forms.py`.
- Every change to services, themes, headcounts and templates is in the
  audit trail.
- Tests: `apps/worship/tests/test_schedule.py`.

Built in Phase 4 (`apps/songs`), the **Song Pool**:

- **Song** (`models.py`): Spotify track ID (unique when given), title,
  artist, album and length; lyrics with their status (not looked up yet,
  found, not found, instrumental, lookup failed); the Worship Check with
  its score; Feel; Theme Tags with each tag's score; the lyrics embedding
  (a JSON list, with the engine that made it); who reviewed it and when;
  and "the team knows it". Public UUID in URLs.
- **Theme Tag**: a church-edited list with keywords. 30 neutral tags are
  seeded (Adoration, Grace, Hope, The Cross, …).
- **Trusted Artist**: a church-edited list, empty at first.
- **Outside services**, all through `apps/core/http.py`:
  - `spotify.py`: the app's own token (Client Credentials), track search
    10 a page with paging up to offset 1000, a `genre:` filter that is
    dropped when it finds nothing, one track by ID, and one retry after an
    expired token. The Spotify safeguards (Phase 5) are below.
  - `lyrics.py`: LRCLIB lookup by title, first artist, album and length,
    then a search by title and artist when it misses (closest length
    wins). One request at a time, 0.35 s apart, named by
    `LRCLIB_USER_AGENT`; a 429's Retry-After is waited out up to twice.
- **ML engine** (`ml/`, [[0006-onnx-runtime-for-song-analysis]]): the ONNX
  engine or the keyword stand-in, chosen by `ML_ENGINE`.
  `manage.py download_models` fetches the models and refuses when the
  disk would keep less than 200 MB free.
- **Analysis** (`analysis.py`), from the lyrics only, with repeated lines
  dropped:
  - the **Model's Worship Score** (`worship_model_score`), from the lyrics
    alone;
  - the **Worship Score** (`worship_score`): the model's score plus 0.25
    for a Trusted Artist, a church rule applied after the model; the
    artist name never reaches the engine. The song page shows the two
    apart;
  - the **Worship Check**, by the church's rules (**Worship Check
    Settings**, Settings → Worship check): the song passes when its worship
    score reaches the **pass mark** (default 0.5). An optional rule, off by
    default, makes artists not on the Trusted Artists list need a stricter
    mark (default 0.9) or wait for a person's review ("Not checked", and
    the song page says why). Changing the rules or the Trusted Artists list
    decides the check again for every song nobody has reviewed, from the
    stored model score, without running a model;
  - up to four Theme Tags scoring 0.5 or more, except for songs that fail
    the check;
  - a Feel guess, left blank unless one feel scores at least 0.5 and beats
    the next by 0.2;
  - the embedding.
  - A Reviewed song keeps its check, tags and feel when analysed again; a
    song whose feel a person set (`feel_reviewed`) keeps its feel.
- **Processing** (`pool.py`): `manage.py process_songs [--limit N]`
  fetches lyrics for songs that need them, then analyses songs whose
  lyrics are new. The model loads only when something needs analysis.
  Lyrics never appear in its output or the audit trail. It refuses to run
  while the search worker runs, which does the same work between runs.
- **Screens** (`/worship/songs/`):
  - the song list, with search and filters (Worship Check, Theme Tag,
    Feel, team, lyrics status);
  - the song page: details, check and score, tags with scores, feel,
    lyrics, and when it was looked up and analysed;
  - Edit: correct the Worship Check, Theme Tags and Feel, and set "the
    team knows it"; saving marks the song Reviewed;
  - Check again: queues a fresh lookup and analysis;
  - Find on Spotify: search when the form is submitted (never as the user
    types) and add a track. A valid track ID is fetched from Spotify again,
    never taken from the form, unless the pool already has it;
  - settings: Theme tags, Trusted artists and Worship check, as tabs
    beside the worship settings.
- Adding, editing and Check again are in the audit trail; machine analysis
  is not.
- Tests: `apps/songs/tests/` (clients, Spotify safeguards, cleanup, ML,
  analysis, pool, commands, views).

Built in Phase 5, **song suggestions** (`apps/worship`, with the
Spotify safeguards in `apps/songs`):

- **Suggestion Settings** (`models/suggestions.py`, one row): search
  genres (default "worship"), phrases per theme (4), pages per phrase (2),
  market, the four ranking weights (theme match 1.0, familiarity 0.2,
  season 0.15, recent use 0.3; recalibrated on 2026-11-18 for the fixed
  relevance scale), the feel mismatch weight (0.15), the repeat window
  (4 weeks) and how many ranked songs a run keeps (20). Edited at
  Settings → Suggestion settings; changes are audited.
- **Season**: a church-edited list with dates (once, or every year, which
  may run over the new year) and the Theme Tags that suit it. None at
  first, so season fit plays no part until the church adds one.
- **Search Run**: one search for a service's songs: status, progress and
  stage, phrases, pages read, songs found, added, analysed and ranked, the
  weights used, Spotify requests and every 429 met, whether Spotify was
  paused so the pool was ranked instead, and each search's phrase, genre
  and whether it ran again without the genre (information only, never used
  in a decision). **Suggestion**: a ranked song of a run, with its rank,
  score and its parts, the raw similarity (`match`), its slot (if placed)
  with the slot's reason, and its reasons.
- **The pipeline** (`suggesting.py`), carried out by the search worker:
  1. the theme's embedding and the Theme Tags it is about;
  2. search phrases: a short title, then KeyBERT-style phrases picked with
     maximal marginal relevance (`phrases.py`);
  3. a Spotify search per phrase and genre, retried without the genre
     when it finds nothing;
  4. cleanup (`apps/songs/cleanup.py`): karaoke, instrumental and backing
     tracks dropped; a live version dropped only when the plain version
     was also found;
  5. lyrics from LRCLIB for songs new to the pool;
  6. analysis of every pool song not yet analysed by the current engine;
  7. ranking of every accepted song in the pool (`ranking.py`):
     `w1·relevance + w2·familiarity + w3·season − w4·recency`. Relevance is
     the cosine of theme and lyrics embeddings on a fixed scale: the
     engine's `similarity_range` (0.20 to 0.60 for all-MiniLM-L6-v2) maps
     to 0 to 1, clipped. Its label is fixed too: "closely" from a cosine of
     0.50, "fairly well" from 0.40, "a little" from 0.30, and "doesn't match
     the theme well" below. Familiarity is 0.6 for "the team knows it" plus
     up to 0.4 for past use; recency falls from 1 on the service's day to 0
     at the end of the repeat window. Past use comes from confirmed lineups
     (Phase 6), so for now only "the team knows it" counts;
  8. versions (`versions.py`): versions of one song (lyrics at least 0.90
     alike with titles that begin the same way, or 0.95 whatever the
     titles) count once. The kept version is the one the team knows, then
     one a person reviewed, then one by a Trusted Artist, then the best
     scored; its reasons name the others. The pool keeps every version;
  9. sequencing (`sequencing.py`): best placement first, feel as a
     preference. A song in a slot of another feel loses the feel mismatch
     weight per step (upbeat, mid-tempo, slow); an unknown feel costs half
     a step, so it never beats a known close match; a slot without a feel
     costs nothing. A lineup never holds two songs with the same title.
     The slot's reason, when one is needed, is kept apart;
  10. reasons, kept on each Suggestion.

  A "Rank the song pool only" run skips stages 2 to 5. A failed outside
  call ends the run with a clear message. `place_again` places a run's
  songs again after a one-click correction.
- **Spotify safeguards** (`apps/songs/spotify.py`, Design-Decisions,
  Phase 5):
  - every Spotify call first checks the shared block: the latest
    **Spotify Limit** row still in force, in the database, so the worker
    and web requests all respect it;
  - a 429 is saved as a Spotify Limit with its reason and Retry-After, and
    logged. A wait of up to 30 s is waited out and the request tried once
    more; a second 429 or a longer wait stops the run;
  - `QUOTA_EXCEEDED`, or a Retry-After over an hour, **pauses** Spotify
    until Retry-After, or for 24 hours when Spotify gives none. A run that
    meets a pause ranks the pool instead, and the service page and Find on
    Spotify say until when;
  - no search-as-you-type; a track already in the pool is never fetched;
  - Spotify requests and 429s are recorded on each Search Run.
- **The search worker** (`manage.py run_worker`,
  [[0007-search-worker]]): claims waiting runs oldest first and carries
  them out, then works through songs that need lyrics or analysis. It
  holds a PostgreSQL advisory lock (`apps/core/locks.py`) while it runs,
  so a second worker, or `process_songs`, refuses to start. Runs left
  "running" by a stopped worker are marked failed when it starts.
- **`manage.py seed_hymns`** adds 23 public-domain hymns to the pool:
  general hymns, eight Christmas carols, four slow hymns and two Easter
  hymns. Every text was first published before 1913, and every author and
  translator died more than 70 years ago. Running it again adds only
  missing ones.
- **Screens**:
  - the service page's **Suggested lineup** panel (named by the "lineup"
    Label), only for people with `worship.suggest_songs`: "Find songs"
    (when Spotify is set up and not paused) and "Rank the song pool only";
    while a run is in progress it shows the stage and reloads itself every
    two seconds (HTMX), and after a few minutes of waiting says how to
    start the worker; then the songs placed in the slots, with their
    reasons, and the other choices. A theme without notes gets a hint to
    add them (notes aren't required). "About this search" (with
    `worship.view_searchrun`) shows the phrases, pages, Spotify requests
    and limits, which searches ran again without the genre, and song
    counts;
  - **one-click corrections** beside each suggested song, for people who
    may also change songs (`songs.change_song`): set its feel (kept when
    the song is analysed again), or mark it "Not a worship song" (it
    counts as Reviewed and leaves the lineup). Both are audited, and the
    lineup is placed again at once (HTMX);
  - settings: Seasons and Suggestion settings, as tabs beside the other
    worship settings.
- Team members never see suggestions: the panel and its URLs need
  `worship.suggest_songs`, which only Worship Leader and Pastoral Staff
  get by default.
- Tests: `apps/worship/tests/` (`test_suggestion_rules.py`: phrases,
  ranking, labels, versions, placement, seasons;
  `test_suggesting.py`, `test_suggestion_views.py`).

Built in Phase 6, part A (2026-11-19), **lineups** ([[Design-Decisions]],
Phase 6; [[0008-final-say-permission]]):

- **Lineup** (`models/lineups.py`, one per service): draft or confirmed,
  the Search Run it came from, who confirmed it and when (kept when it is
  reopened, so the team knows it is being revised), the **pastor's lock**,
  the **Mark** (the latest edit while confirmed: who, when, and whether
  they had the final say), and the send-back note (who and when). **Lineup Item**: song, slot, order, **Service Key** (12 major and
  12 minor keys, `apps/core/music.py`), notes, the theme reasons it was
  suggested for (match, tags, other versions), and a lock on the song. One
  item per song per lineup. The feel reason isn't stored: it depends on
  the slot, so `LineupItem.slot_reason` works it out for the slot the song
  is in now (`sequencing.slot_reason`), after any move, swap, add or
  regenerate.
- **The rules** (`lineups.py`):
  - "Save these songs as the lineup" in the suggestions panel copies the
    run's placed songs, in slot order, with their reasons. The lineup is
    its own copy: one-click corrections, `place_again` and new Worship
    Checks change the run, never the lineup (workflow review F4).
  - Review: **swap** for a ranked alternative from the latest finished run
    (the slot and place stay; the key and notes go); **lock** a song (it
    isn't swapped, moved, removed or regenerated until unlocked);
    **reorder** (two songs trade places and slots, so slots stay in service
    order; an arrow shows only where `lineups.allowed_moves` allows the
    move, and the server refuses the same moves, such as "X can't move
    into a locked song's place"); **remove** (the slot is left empty); **add from the pool**
    (any song except one a person marked "Not a worship song", into an
    empty slot or at the end; a song that failed the Worship Check or was
    never checked shows a warning to the people who plan); **key and
    notes**; **regenerate** from the latest run around the locked songs. A
    lineup never holds two songs with the same base title.
  - Confirmation: the worship leader (`change_lineup`) or anyone with the
    final say (`finalize_lineup`). The pastor's confirmation, or edit to a
    confirmed lineup, puts on the pastor's lock: people without the final
    say can't change it until it is reopened. The pastor's edits to a draft
    don't lock anyone out. An edit to a confirmed lineup marks it with the
    time, shown to everyone who can see it: "Edited by <pastor Label>
    (<name>)" for the pastor, "Changed by <name>" for the leader (who may
    edit only while there is no pastor's lock; no lock follows). Only the
    latest mark shows. Locking or unlocking a song isn't an edit.
  - Reopening (final say only) makes the lineup a draft and lifts the lock
    and the mark. Sending back (final say only, a note required) is the
    same, with the note for the leader; confirming again clears the note.
  - Visibility: people who plan (`change_lineup` or `finalize_lineup`) see
    drafts; team members (`view_lineup`) see a lineup only once it is
    confirmed, and a reopened one only as "being revised"; a draft that was
    never confirmed doesn't exist for them (404).
  - A cancelled or past service gets no suggestions and no new lineup, and
    a cancelled service's lineup can't be confirmed (workflow review F7).
- **Screens**: the lineup page (`/worship/services/<id>/lineup/`), the swap
  page, Add a song (search the pool), Key and notes, and Send back; a
  lineup card on the service page. Every change is in the audit trail
  (status, songs with slots and keys, song notes, the lock, the note).
- Tests: `test_lineup_rules.py` (each rule, F4, F7, the default roles) and
  `test_lineup_views.py` (every role by page and by URL, each review
  action, the mark and its Label, F4 through the one-click corrections, F5
  theme notes, F7, audit, the Module switched off).

## Permissions

| Permission                                   | Allows                                   |
| -------------------------------------------- | ---------------------------------------- |
| `worship.view_worshipservice`                | Seeing the schedule and service pages    |
| `worship.add_worshipservice` / `change_worshipservice` | Scheduling and editing services |
| `worship.change_theme`                       | Posting and editing themes; seeing notes |
| `worship.record_attendance`                  | Recording a headcount                    |
| `worship.*_servicetemplate`, `*_sermonseries` | The settings lists                      |
| `songs.view_song`                            | The song list and song pages             |
| `songs.change_song`                          | Correcting a song; Check again           |
| `songs.add_song`                             | Find on Spotify                          |
| `songs.*_themetag`, `*_trustedartist`        | The song settings lists                  |
| `worship.suggest_songs`                      | The suggestions panel; asking for suggestions |
| `worship.view_searchrun`                     | "About this search" in the panel         |
| `worship.*_season`                           | The Seasons list                         |
| `worship.change_suggestionsettings`          | Suggestion settings                      |
| `songs.change_worshipchecksettings`          | Worship check settings                   |
| `worship.suggest_songs` and `songs.change_song` | One-click corrections in the panel    |
| `worship.view_lineup`                        | Seeing a confirmed lineup                |
| `worship.add_lineup` and `worship.suggest_songs` | Saving the suggestions as the lineup |
| `worship.change_lineup`                      | Seeing drafts; reviewing and confirming; seeing theme notes |
| `worship.finalize_lineup`                    | The final say: the pastor's lock, reopening, sending back (decision 0008) |

Default roles ([[Accounts]]):
- **Pastoral Staff** schedule services, post themes, record headcounts and
  manage templates and series; they see songs, theme tags and seasons, ask
  for song suggestions, review and confirm lineups, and hold the final say
  (`finalize_lineup`).
- **Worship Leader** sees the schedule, manages the song pool, theme tags,
  trusted artists, the worship check, seasons and suggestion settings, asks
  for song suggestions and corrects them in one click, and makes, reviews
  and confirms lineups.
- **Team Member** sees the schedule and confirmed lineups, never
  suggestions or drafts.
- **Office Staff** see the schedule and record headcounts.

## Church settings this module depends on

- Service Templates and their Song Slots
- Series
- Theme Tags and Trusted Artists
- Worship Check Settings: pass mark, the rule for artists not on the
  Trusted Artists list (off by default), the stricter pass mark
- Seasons
- Suggestion Settings: search genres, phrases per theme, pages per
  phrase, market, ranking weights, feel mismatch weight, repeat window,
  ranked songs kept
- The "worship service", "sermon", "lineup" and "pastor" Labels
- Who holds the final say: whichever Roles hold `worship.finalize_lineup`
- The church's time zone (Church Profile)
- Installation settings in `.env`: `SPOTIFY_CLIENT_ID`,
  `SPOTIFY_CLIENT_SECRET`, `ML_ENGINE`, `ML_MODELS_DIR`,
  `LRCLIB_USER_AGENT`

## Open questions

- The Trusted Artist bonus (0.25) is still a constant in `analysis.py`.
- A quota lockout without a Retry-After pauses Spotify for 24 hours, and
  only time ends a pause (there is no "try Spotify now" button, so nobody
  can prolong a lockout). Both are choices to confirm.
- Feel guessed from lyrics is weak (stately hymns come out upbeat); it is
  now left blank when unsure, and people set it in one click. Tempo from
  LRCLIB's timed lyrics is a future experiment ([[Development-Plan]]).
- Theme tags are near-ties: most tags score above 0.9 on worship lyrics.
  A neutral class can't help (the model has only two classes), and the
  options measured on the 23 hymns didn't beat today's rule, which stays
  ([[Design-Decisions]], Phase 5 follow-up). People correct tags.
