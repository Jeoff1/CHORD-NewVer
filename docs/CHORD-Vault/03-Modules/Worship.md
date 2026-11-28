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
- **Theme**: one per service, with title, main scripture and notes. It
  records who posted it. Its optional **Series** is no longer asked for or
  shown (28 Nov 2026); one saved before stays. The notes are shown only
  to people who plan (those who can edit themes or lineups).
- **Series**: the model and its saved rows stay; there is no settings
  page any more.
- **New service form:** "Date and time" starts at the template's next
  usual day and time (`scheduling.suggested_start`), and changes with the
  template until the person edits it (`static/worship/service_form.js`).
- **Screens** (`/worship/`):
  - the schedule: Upcoming and Past, with search over names and themes;
  - a month calendar (`/worship/calendar/?month=YYYY-MM`);
  - a service page with its theme, details and attendance;
  - add and edit a service; post and edit its theme;
  - **Schedule weeks ahead**: adds the chosen template's service on its
    usual day and time for up to 26 weeks, in the church's time zone, and
    skips dates that already have it;
  - settings: Service templates (with their slots).
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

- **Suggestion Settings** (`models/suggestions.py`, one row per church): search
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
     at the end of the repeat window. Past use comes from the confirmed
     lineups of services, not cancelled, that start before this one
     (`ranking.song_usage`, from `usage.py`; Phase 6);
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
     The slot's reason, when one is needed, is kept apart: "Its feel isn't
     known yet; this slot asks for slow", or "Its feel (upbeat) doesn't
     match this slot, which asks for slow, but it fit best";
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
    logged. Only the search worker waits (`may_wait=True`): a wait of up to
    30 s is waited out and the request tried once more; a second 429 or a
    longer wait stops the run. Every web request fails fast instead: one
    request, no wait, no retry (workflow review F10, Phase 7);
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
- **Upcoming services on the homepage** (Phase 9B, `public.py`): when the
  church switches it on, the next five services that aren't cancelled, as
  date, time and kind (the template's name) only.
- **`manage.py seed_hymns --church <slug>`** adds 23 public-domain
  hymns to that church's pool:
  general hymns, eight Christmas carols, four slow hymns and two Easter
  hymns. Every text was first published before 1913, and every author and
  translator died more than 70 years ago. Running it again adds only
  missing ones.
- **Screens**:
  - the **Suggested lineup** panel on the Song Lineup page (the service
    page before Phase 9C; named by the "lineup" Label), only for people
    with `worship.suggest_songs`: "Find songs"
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
  - "Fill the empty slots with suggestions" (before 2026-11-26: "Save
    these songs as the lineup"; decision 0015) copies the run's placed
    songs into the empty slots, in slot order, with their reasons. The lineup is
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

Built in Phase 6, part B (2026-11-19), **feedback, usage and reports**:

- **Suggestion Feedback** (`models/lineups.py`, `feedback.py`): what people
  did with each suggestion placed in a lineup. During review,
  `Lineup.suggestion_outcomes` follows each one:
  - placed by making the lineup or by regenerating: **kept**;
  - an alternative chosen in a swap: **swapped in** (a positive, told
    apart from a top pick that stayed; migration `0009`);
  - replaced by a swap: **swapped**;
  - taken out: **removed**;
  - songs replaced by regenerating are forgotten; songs added from the
    pool were never suggested.

  Confirming saves one row per suggested song, replacing those of an
  earlier confirmation; a song labelled kept or swapped in that is no
  longer in the lineup counts as removed. Each row holds its label, the
  run and its rank, and only the
  features Phase 9 may train on (`SuggestionFeedback.FEATURES`):
  - relevance, the raw match, and the model's worship score (lyrics);
  - familiarity, season, recency, "the team knows it", and the slot's
    feel (the church's data).

  No Spotify field, no Trusted Artist bonus or score with it, no version
  choice, no reasons, no genre-filter record. Migration `0008` starts
  existing lineups with their placed suggestions as kept.
- **Song usage** (`usage.py`): every song in the confirmed lineup of a
  service that isn't cancelled, once per service, with its date in the
  church's time zone. Computed, never stored.
  - `ranking.song_usage(service)` counts the services before it, so
    familiarity (up to 0.4 for five uses) and recent use (the repeat
    window) now count (workflow review F3).
  - The song usage report counts services already held.
- **Reports** (`reports.py`, `/worship/reports/`, "Reports" in the Worship
  section links):
  - **Song usage**: songs from confirmed lineups of services held, most
    used first, with times, last use and every date, for a period (From
    and To). Songs sung again within the repeat window are highlighted:
    used more often than the recent-use window allows. **Download CSV**:
    song, artist, times, last used, dates, and whether sung again within
    the window. No lyrics.
  - **Attendance**: the headcount of each service held that has one, with
    the average, for a period. It doesn't exist (no link, and 404) until a
    headcount has been recorded.
- Tests: `test_usage_and_feedback.py` (feedback labels, replacement,
  regenerate and pool songs, training-data fields; usage and the ranking
  change after confirmation; the usage report matching the confirmed
  lineups, its page, filter, CSV and permissions; attendance shown and
  hidden, and who may see it).

Built in Phase 7, part A (2026-11-20), **chord sheets and keys**
([[Design-Decisions]], Phase 7; [[0009-transposition-on-the-server]]):

- **Chord Sheet** (`apps/songs/models.py`): a song's ChordPro text and the
  key it is written in, and nothing else; pending or approved, who added it
  and who approved it. A song has at most one approved sheet. **Song** gains
  the **recording's key**, entered by a person (Spotify gives none).
- **ChordPro** (`apps/songs/chords.py`), all on the server, in Python:
  - `check()`: directives alone on their line, every `[chord]` closed and
    a real chord, sections opened and closed in order, at least one chord;
    the message names the line;
  - `to_chordpro()`: a chords-over-words chart (as on Ultimate Guitar,
    `[ch]` tags and section names such as `[Chorus]` included) becomes
    ChordPro; ChordPro passes through. ChordSheetJS isn't used: it is
    GPL-2.0-only;
  - `render()`: the sheet in any key. Sharps or flats follow the key shown
    (C and A minor use flats), a slash chord's bass moves with it, and the
    chord's quality stays. A capo shows the shapes played; Nashville
    numbers are in the key heard (in a minor key, 1 is the minor tonic, and
    the viewer notes "Numbers count from the minor key (1 = A minor)").
- **Rules** (`apps/songs/sheets.py`):
  - people with `songs.approve_chordsheet` add or edit a sheet for any
    pool song at any time, approved at once;
  - people with only `songs.add_chordsheet` (team members) may paste one
    for a song in a confirmed lineup that has none: it waits as pending,
    and other team members don't see it;
  - approve and discard need `approve_chordsheet`.

  The audit trail records the song, status and key, never the text.
- **Import a ChordPro file** (added 2026-11-20): on the sheet form, a
  .cho, .chopro, .chordpro, .pro or .txt file up to 200 KB in UTF-8
  (`sheets.read_import`). Its text goes into the box, and its `{key:}` or
  `{k:}` fills the key; the file isn't stored. Rhythm lines such as
  `|D//G|////|` become transposable (`chords.rhythm_line`), and so do
  Worship Together's bracketed ones, `[| D / / G |]`
  (`chords.bracketed_rhythm`); either becomes a comment when unreadable.
  Plain section lines such as "Verse 1" or "Outro" become section labels
  (`chords.section_line`).
- **Chart marks** (`chords.chord_in`, `is_mark`, `keep_unread`):
  - an optional chord such as `(F#m7)` transposes inside its parentheses;
  - N.C., `x2`, `(x2)` and footnote marks stay as written;
  - anything else unreadable in brackets is kept as an annotation
    (`[*text]`, shown without the star in grey italic, never transposed),
    and the form warns, listing the lines. When such a sheet is shown away
    from its own key (another key, a capo or numbers), the viewer notes
    "Some marks were kept as written and aren't transposed.";
  - a stray `]` that closes nothing is removed and listed in the warning
    (`chords.drop_stray_brackets`);
  - only broken ChordPro, such as an unclosed `[`, stops a save.
- **Find chords**: links to searches on Ultimate Guitar, Worship Together
  and the web, opened in a new tab. Nothing is fetched.
- **Screens**:
  - the song page's **Chord sheet** card (sheet, pending sheets with
    Approve and Discard, add or edit, Find chords) and the sheet form
    (Convert, then Save or Send for approval);
  - a **lineup song page** (`/worship/services/<id>/lineup/songs/<n>/`)
    with the sheet in the service key, opened from each song in the
    lineup. Team members see it only once the lineup is confirmed.
- **The viewer** (`apps/songs/viewer.py`): key (and ±1 semitone), capo
  0–7 (easy shapes marked), Nashville numbers, and **Practise along** in
  the recording's key (hidden when it isn't set). These are a personal view
  in the query string. Each change re-renders only the sheet with htmx.
- **Counts**: the lineup page and the service page's lineup card show how
  many songs have an approved sheet. A confirmed lineup marks the songs
  that still need one.
- **Key history**: the Key and notes page lists the service keys the song
  had in confirmed lineups of earlier services, most recent first
  (`lineups.key_history`).
- **Lyrics** (workflow review F13): the song page shows full lyrics only
  with `songs.view_lyrics` (Worship Leader and Pastoral Staff); the team
  sees the words in the chord sheet.
- Tests: `apps/songs/tests/test_chords.py` (every key, sharps and flats,
  slash chords, minor keys, capo, Nashville numbers, checking,
  converting), `test_chordsheets.py` (rules, approval, the form, Find
  chords, lyrics, default roles) and `apps/worship/tests/test_lineup_songs.py`
  (the lineup song page, htmx, practise-along, pending sheets, counts, key
  history).

Built in Phase 7, part B (2026-11-22), **the Spotify Connection,
playback and the Lineup Playlist** ([[Design-Decisions]], Phase 7):

- **Spotify Connection** (`apps/songs/models.py`, rules in
  `apps/songs/connections.py`): one per user, made with the Authorization
  Code flow from **Spotify account** in the user menu
  (`/worship/songs/spotify/`). Anyone signed in may connect their own.
  - The `state` sent to Spotify is kept in the session and checked once on
    the way back; a state the session never sent connects nothing.
  - Scopes: `streaming`, `user-read-email`, `user-read-private`,
    `user-modify-playback-state`, `playlist-modify-private`.
  - The player's token page gives each person only their own token, by
    POST only, with no-store headers.
  - The access and refresh tokens are stored encrypted with Fernet
    (`SPOTIFY_TOKEN_KEY`); nothing else from the account is stored. They
    never appear in pages, logs or the audit trail (which records only
    "Spotify account: Connected / Not connected"), and `UserTokens` leaves
    them out of its `repr`.
  - An access token is refreshed when under a minute is left, or once when
    Spotify refuses it (`call_with_token`). A refresh Spotify no longer
    accepts, or tokens the key can't read, remove the connection, and the
    person connects again. Disconnecting deletes it.
- **`SpotifyClient`** gains the user calls, all under the same
  safeguards: `authorize_url`, `exchange_code`, `refresh_user_token`,
  `create_playlist` (`POST /me/playlists`, private or public) and
  `replace_playlist_items` (`PUT /playlists/{id}/items`, up to 100), the
  endpoints of Spotify's February 2026 Web API.
- **Playback** on the lineup song page (`songs/includes/player.html`,
  `playback_context`):
  - it is a green **"Listen" card** in both colour modes since Phase 9A,
    A7 part 2 ([[Design-System]]): full playback, the embedded player, or
    "No playback for this song" when the song has no Spotify track;
  - a connected account gets the **Web Playback SDK** (`static/songs/player.js`):
    the song's title and artist (CHORD's own), a cover from the SDK (shown
    in the browser only, never stored), a progress bar with the time, back
    and forward 10 seconds and a gold play/pause button. The script asks
    `/worship/songs/spotify/player-token/` (POST, never cached) for the
    person's own access token, which stays in its memory; the refresh token
    never leaves the server;
  - whenever the SDK can't be used (no Premium, an unsupported browser, a
    refused or missing token, a 429 from Spotify or from the token page, or
    no "ready" within 15 s), it shows a short message and falls back to
    Spotify's **embedded player** inside the same card, with no automatic
    retry;
  - without a connection the embedded player shows at once, with a link to
    connect. **Open in Spotify** always shows. A song without a Spotify
    track ID gets the card with "No playback for this song" and no link to
    fix it (no page links an existing song to a track yet).
- **Church Spotify Account** (`ChurchSpotifyAccount`, at most one per church;
  [[0011-church-spotify-account]]): an optional church setting on the
  **Spotify** tab of church settings (`/worship/songs/spotify/church/`),
  shown while the Worship module is on. People with
  `church.change_churchprofile` connect it (scopes `playlist-modify-public`
  and `playlist-modify-private`, through the same callback) and disconnect
  it. Its tokens are encrypted like personal ones; the audit trail records
  only "Church Spotify account: Connected / Not connected" on the Church
  Profile. It is never used for playback.
- **Lineup Playlist** (`apps/worship/playlists.py`; `Lineup` keeps the
  playlist ID, whether it is on the church account, its personal owner,
  the track IDs saved and when; [[0010-store-own-playlist-id]]):
  - confirming saves the lineup at once as its own playlist, named with
    the service name and date ("Sunday Church – Nov 29"): on the Church
    Spotify Account as a **public** playlist when one is connected,
    whoever confirms; otherwise as a **private** playlist on the account of
    the person who confirmed it (the worship leader, or the pastor when the
    pastor confirms). Songs not on Spotify are left out, and the message
    says how many;
  - saving never stops the confirmation. With no connection, during a
    block, or on a 429, nothing waits: the lineup stays confirmed and the
    lineup page shows **Save to Spotify** (a link to connect first when
    the person has no connection);
  - Save to Spotify (`worship.change_lineup` or `finalize_lineup`) saves
    on the church account when connected (no personal connection needed),
    otherwise on the pressing person's account. Saving again on the same
    account (the church's, or the same person's) updates that lineup's
    playlist; other services' playlists are never touched. A stored
    playlist is made again only on a 404, or on a 403 when the connected
    account doesn't own it: only then, `_is_gone` asks Spotify for both
    account IDs (`SpotifyClient.playlist_owner_id`, `current_user_id`),
    compares them and stores neither. Any other 403 is a refusal (the
    lineup stays confirmed with Save to Spotify), and a 429 on a lookup
    fails fast (Phase 8 fix, 2026-11-23). The playlist ID is
    kept as soon as it exists, so a 429 on the next call doesn't make a
    second playlist on the next try;
  - an unusable church account (refused, revoked or a 429) leaves the
    lineup confirmed with Save to Spotify; a revoked one is removed and
    the message asks for it to be connected again in church settings;
  - after a change to a confirmed lineup's songs, or once a church account
    is connected for a lineup whose playlist is personal, the page offers
    Save to Spotify again. A church playlist's "Open the playlist" link
    shows to everyone who sees the confirmed lineup; a personal one's
    line shows only to people who may save, and its link only to its
    owner.
- **Find on Spotify** now fails fast on a 429 (F10).
- Tests: `apps/songs/tests/test_spotify_connection.py` (encryption,
  connecting, the state check, refusals, 429 while connecting, refresh,
  revoked and unreadable tokens, the player's token, access, no tokens in
  logs), `apps/worship/tests/test_spotify_playlists.py` (saving on
  confirmation, the pastor's account, no connection, 429, a block, a
  playlist kept across a 429, songs left out, Save to Spotify, updating,
  someone else's playlist, refusals, playback and its fallbacks),
  `apps/worship/tests/test_church_spotify.py` (the church account: public
  playlists, the team's link, updating, two services, reopening, a gone
  playlist, 429, refusal, revoked, who may manage it, its scopes and
  encryption, the settings tab, never for playback) and
  `apps/songs/tests/test_spotify_limits.py` (web requests fail fast; the
  worker's single wait).

Built in Phase 9A, A5 (2026-11-24), **booked time** for [[Occasions]]
([[0013-occasions-module]]):

- Every Service Template has a **usual length** (`length_minutes`, 15
  minutes to a day; 90 by default, and a template saved without one keeps
  it), shown in the templates list. A service books the time from its
  start for that long (`WorshipService.ends_at`), shown on its page as
  "Booked".
- **Other bookings on the calendar** (`bookings.py`): a Module built on
  Worship registers a source in its `AppConfig.ready()`; the calendar
  shows what each source returns, with a link, or as "Booked" without one.
  Occasions is the only source. Worship never imports it.
- Scheduling a worship service isn't checked for clashes; Occasions checks
  its own bookings against worship services.
- Tests: `apps/worship/tests/test_schedule.py` (`BookedTimeTests`, and the
  length in `test_create_with_slots`); the calendar with occasions in
  `apps/occasions/tests/test_occasions.py`.

Phase 9A, A7 part 3 (2026-11-25), **the screens follow the approved
wireframes** ([[Design-Decisions]], A7):

- **Schedule and calendar:** a shared header (Add service; Schedule weeks
  ahead and Worship settings under More) and tabs Schedule, Calendar,
  Songs, Reports (`templatetags/worship_ui.py`). The schedule's Lineup
  column shows Draft only to people who plan; its Team column ("N of M
  accepted") only while Teams is on, for people who may see teams.
- **Service page:** replaced by Phase 9C (below).
- **Lineup:** the rest under More; song rows with Move, Lock and a "More
  for this song" menu. Since Phase 9C the one button is "Continue to
  confirm".
- **Lineup song page:** Previous and Next song, "song N of M", the sheet's
  one toolbar (Service key, My key, Capo), and the Listen card, Notes for
  the team and This lineup on the right. A song with no service key is
  shown in the sheet's own key, labelled "Sheet's key".
- **Settings:** in the Settings hub's Worship category (Services; Songs
  and suggestions), from `views/base.py`, `SETTINGS_PAGES` and
  `SETTINGS_GROUPS`.
- **Dashboard:** `dashboard.py` adds draft lineups, services with no
  theme, chord sheets waiting and the coming services.
- Tests: `apps/worship/tests/test_schedule_screens.py`,
  `test_service_screen.py`, `test_lineup_screen.py`,
  `test_lineup_song_screen.py`.

Phase 9C (2026-11-26), **guided service planning** ([[Design-Decisions]],
"Phase 9C"; the [[Glossary]]'s Planning Steps):

- **Planning Steps** (`planning.py`, `planning_context`): Theme, the
  church's team (the `team` Label, default "Praise Team"; only while Teams
  is on), Song Lineup ("Song <lineup Label>") and Confirm, each a link to
  its page (`includes/planning_steps.html`). The team step is suggested,
  never required: it stops being the next step once a search ran or a
  lineup exists, or when the roster is closed.
- **Service page:** the step bar and the **next-step panel**
  (`includes/next_step.html`) for people who plan, never on a cancelled
  service; then the theme card and the lineup card (which shows the
  Spotify playlist line once confirmed). Suggestions are no longer here.
- **Song Lineup page** (`views/lineups.py`, `LineupView`,
  `lineup_detail.html`): opens before a lineup exists for people with
  `worship.suggest_songs` (the suggestions panel), and still 404s for the
  team until a lineup is confirmed. With a lineup: the review, a playlist
  preview (`includes/playlist_preview.html`: which songs have a track,
  where the playlist will be saved, Listen links) and the folded
  suggestions. "Find songs" and the one-click corrections return here.
  **Empty-pool pop-up** (`includes/pool_empty_modal.html`, a Bootstrap
  modal over the page, never part of it): for people with
  `worship.suggest_songs`, when `suggesting.pool_is_empty(church)` (no
  song passed the worship check and none is waiting for lyrics or
  analysis; a new church starts this way), no run is in progress and
  planning isn't closed. It says suggestions and Add a song need the pool
  filled by Find songs (Spotify), with a **Find songs** button once the
  theme is posted, **Post the theme** before that, or why Spotify isn't
  available. It opens once per browser session per church
  (`sessionStorage`).
- **Confirm rundown** (`ConfirmView` GET, `lineup_confirm.html`): the
  service, theme, team, songs and warnings (`rundown_warnings`), with
  Confirm for people who may confirm; confirming returns to the service
  page.
- **Sermon PDF** (`Theme.document`, private storage;
  `Theme.document_text`; `sermons.py` checks and reads it; the theme form
  and `ThemeDocumentView`, `worship:theme_document`, for people who plan):
  the theme card links it with the number of words read. Suggestions read
  the whole theme in passages (`reading.py`: `theme_vector`, `tag_texts`;
  `phrases.search_phrases(theme_vector=...)`), so a long sermon or long
  notes aren't cut off by the model's 256-token limit. The title and
  reference are half of the match; the notes, the passage's text and the
  PDF share the other half equally (`reading.parts`), in tags and search
  phrases too.
- **Main scripture from a stored Bible** (`bible/`: the World English
  Bible in `bible/data/web.json.gz`, book names and abbreviations,
  `parse`, `suggest`, `passage_text`): the theme form's `ScriptureInput`
  (an ARIA combobox, `static/worship/scripture.js`) asks
  `worship:scripture_suggest` and shows `worship:scripture_passage`.
  Clicking the field browses: every book, a book's chapters (values end
  in ":", marked `data-more`), a chapter's verses with Whole chapter
  first; the passage shows while typing or browsing (`live=1`: nothing for
  half a reference) and when one is picked. `ThemeForm.clean_scripture`
  drops a trailing ":". The theme card folds the passage ("Read John
  3:16"). `Theme.save` keeps the
  passage's text in `scripture_text`, part of the theme's body for
  suggestions. **Bible settings** (`BibleSettings`,
  `worship:bible_settings`) include the deuterocanonical books.
- **The lineup comes first** ([[0015-lineup-first-suggestions-assist]]):
  `LineupView` shows the template's slots with the songs in them and an
  empty row per open slot (`slot_rows`), with the suggestions beside it
  (`includes/suggestions.html`, each song's Add in
  `includes/suggestion_add.html`). Rules in `lineups.py`: `start`,
  `add_suggestion` (feedback **picked**), `fill_from_suggestions`;
  `add_from_pool` and `addable_songs` work before a lineup exists. Views:
  `AddSongView` (pool, or Find on Spotify with `next`), `AddSuggestionView`
  (`worship:lineup_add_suggestion`), `LineupCreateView` (fills the empty
  slots).
- Church settings used: the Teams Module switch; Bible settings (the
  deuterocanonical books); the `team`, `lineup`, `pastor` and `sermon`
  Labels.
- Tests: `apps/worship/tests/test_planning_steps.py`, `test_sermon_pdf.py`,
  `test_bible.py`, `test_lineup_first.py`,
  and the updated
  `test_service_screen.py`, `test_lineup_screen.py`, `test_lineup_views.py`,
  `test_suggestion_views.py`.

### Screens (UI/UX Phase 5, 28 Nov 2026)

`static/css/planning.css` (loaded by `base.html`), from
[[UI-UX-Master-Plan]] §11:

- **Planning stepper** (`includes/planning_steps.html`): raised step cards,
  a thread between them on wide screens (green once done), the done check
  pops in, the current step's mark rings twice, the step of the page shown
  carries a gold underline; whole steps stay links.
- **Next-step panel**: a flag (or a check when done) and a gold wash.
- **Worship services** (`service_list.html`): Upcoming and Past as a
  segmented control (the same GET buttons with `aria-pressed`), date tiles,
  rows that open the service from anywhere (`data-href`), empty states.
- **Theme card**: the title in Raleway, the scripture as a gold pill with a
  book icon.
- **Song Lineup** (`lineup_detail.html`): a Songs heading with the count,
  row anchors (`#item-<pk>`, highlighted when targeted), locked rows marked
  with a gold edge, dashed empty slots, an empty state. Lineup on the left,
  suggestions on the right (decision 0015).
- **Suggestions** (`includes/suggestions.html`): while a run works, a
  music waveform, "Finding songs for your worship theme…" and three
  skeleton songs above the worker's own progress bar; results as numbered
  cards that stagger in, with the slot, title, artist and reasons; a song
  already chosen gets a green card and the "In the lineup" pill with a
  popping check.
- **Rundowns** (lineup card on the service page, Confirm): numbered song
  rows.
- Tests: `apps/worship/tests/test_planning_screens.py`.

### Songs, chord sheets and rehearsal screens (UI/UX Phase 6, 28 Nov 2026)

From [[UI-UX-Master-Plan]] §12 (`planning.css`, "Songs"):

- **Song pool** (`songs/song_list.html`): the five filters fold into a
  Filters panel (open while one is chosen, the same GET fields); rows with
  a branded tile (no album art is stored), title and artist, the worship
  check as a status pill (`songs/includes/check_badge.html`), feel, theme
  tags as chips, Knows it or New as pills; whole rows open the song; empty
  states (Find on Spotify for people who may add).
- **Find on Spotify** (`songs/spotify_search.html`): a large rounded search
  box, results as rows with tile, title, artist and album, Add (busy while
  sent) or In the pool; an empty state.
- **Song page** (`songs/song_detail.html`): a header with a large tile;
  tags as chips with their score.
- **Chord sheet viewer** (`songs/includes/chord_sheet.html`): a 72-character
  reading width, larger text, chorus blocks with a gold edge and wash, the
  toolbar sticks under the header while reading, the sheet dims while htmx
  re-renders it; no other motion.
- **Editor** (`songs/chordsheet_form.html`): a tall monospace text area.
  Discarding a pending sheet asks first.
- **Rehearsal** (`worship/lineup_song.html`): the lineup order as numbered
  rows with the current song highlighted.
- Tests: `apps/songs/tests/test_song_screens.py`.

### Calendar (UI/UX Phase 7, 28 Nov 2026)

`worship/calendar.html`: the month title in Raleway with previous, next
and Today; a legend with swatches and words; a month grid (`.chord-cal`)
whose today is a filled circle, days outside the month dimmed, events as
chips (services green, occasions gold with a gold edge, hidden bookings
dashed and labelled "Booked", cancelled struck through), each lifting on
hover; the month fades in. Same data, links and visibility rules.

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
| `worship.view_song_usage`                    | The song usage report and its CSV (Worship Leader, Pastoral Staff) |
| `worship.record_attendance`                  | Also the attendance report, once a headcount exists |
| `songs.view_chordsheet`                      | Seeing approved chord sheets             |
| `songs.add_chordsheet`                       | Pasting a sheet; pending without approve |
| `songs.approve_chordsheet`                   | Adding and editing sheets approved at once; approving and discarding pending ones |
| `songs.view_lyrics`                          | Full lyrics on the song page (review F13) |
| `worship.change_lineup` or `worship.finalize_lineup` | Save to Spotify; seeing a personal playlist's line |
| `church.change_churchprofile`                | Connecting and disconnecting the Church Spotify Account |
| (signed in)                                  | Connecting one's own Spotify account; playback |

Default roles ([[Accounts]]):
- **Pastoral Staff** schedule services, post themes, record headcounts and
  manage templates and series; they see songs, theme tags and seasons, ask
  for song suggestions, review and confirm lineups, and hold the final say
  (`finalize_lineup`).
- **Worship Leader** sees the schedule, manages the song pool, theme tags,
  trusted artists, the worship check, seasons and suggestion settings, asks
  for song suggestions and corrects them in one click, and makes, reviews
  and confirms lineups.
- **Team Member** sees the schedule, confirmed lineups and their chord
  sheets, and pastes missing sheets for approval; never suggestions,
  drafts or full lyrics. Worship Leader and Pastoral Staff also hold the
  chord sheet permissions, including approving, and `view_lyrics`.
- **Office Staff** see the schedule and record headcounts.

## Church settings this module depends on

- Service Templates and their Song Slots, and each one's usual length
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
- The Church Spotify Account (optional; church settings, Spotify tab)
- Installation settings in `.env`: `SPOTIFY_CLIENT_ID`,
  `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_TOKEN_KEY` (encrypts users' Spotify
  tokens; without it nobody can connect), `SPOTIFY_REDIRECT_URI`
  (optional), `ML_ENGINE`, `ML_MODELS_DIR`, `LRCLIB_USER_AGENT`

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
