=== INTENDED WORKFLOW ===

Updated 2026-11-19 with the decisions in [[Design-Decisions]]. Where this
spec and Design-Decisions.md disagree, Design-Decisions.md wins (AGENTS.md
sets the order).

ROLES
- Pastor: schedules services, posts the theme (title, scripture, sermon notes),
  can review, edit, confirm, reopen and send back a lineup. The pastor's
  decision is final. That is the permission worship.finalize_lineup, held by
  the pastoral role by default (and by the Administrator, like every
  permission), never a check on a role name
  ([[0008-final-say-permission]]). Below, "the pastor" means anyone who
  holds it. The church's "pastor" Label (default "Pastor") names the role in
  the app.
- Worship leader: generates the suggested lineup, swaps/locks/reorders/re-keys
  songs, confirms the lineup, adds chord sheets, approves chord sheets pasted
  by team members.
- Team member: sees a lineup only after it is confirmed; plays songs, reads
  chord sheets; may paste a missing chord sheet for a song in a confirmed
  lineup, which waits for approval by the worship leader or the pastor.
- Admin: users, roles and settings. The Administrator role can't be deleted
  and always holds every permission. Spotify has one connection per user:
  each user connects their own Spotify account (for playback, and the
  worship leader's for saving playlists). The app's own Spotify credentials
  are set in .env when CHORD is installed.
- Office staff (optional): keeps the member directory up to date.

SONG SELECTION (core module)
1. Pastor posts a theme for a service.
2. System turns the theme into several search phrases.
3. System searches all of Spotify (max 10 results per request, so it paginates
   with an offset; retries without a genre filter if a filtered search is empty),
   following the Spotify safeguards below.
4. System removes duplicates and karaoke, instrumental and backing-track
   versions. A live version is dropped only when the plain version is also in
   the results; a song released only as a live recording is kept.
5. System fetches lyrics from LRCLIB (one request at a time) and caches them.
   Songs already in the pool skip this. Songs with no lyrics are set aside.
6. A classifier reads the lyrics, drops non-worship songs and suggests theme
   tags. Its raw worship score is stored in its own field and depends only on
   the lyrics. The optional Trusted Artist bonus is a church rule applied after
   the model and stored separately; the artist name never reaches the model.
   The pass mark (default 0.5) is a church setting. An optional church rule,
   off by default, makes artists not on the Trusted Artists list need a
   stricter mark or a person's review; it too is applied after the model and
   is never model input or training data.
7. Every accepted song in the pool is ranked, not only the songs this run
   found: embedding similarity between theme and lyrics on a fixed scale
   (labelled closely, fairly well, a little, or doesn't match well), plus
   familiarity (past usage from confirmed lineups), season fit, and a penalty
   for recent use. Versions of one song are grouped and one is kept (the team
   knows it, then reviewed, then a Trusted Artist, then the best scored); the
   pool keeps every version.
8. Top songs are placed in service slots (opener, praise, worship, response),
   with feel as a preference: a song of another feel loses a little score for
   each step between upbeat, mid-tempo and slow. A lineup never holds two
   songs with the same title. Feel is left unset when the analysis isn't sure;
   an unset feel costs half a step, so it never beats a known close match.
9. Each suggestion stores a reason it was picked. Suggestions are shown only
   to people with the suggest-songs permission (worship leader and pastor by
   default), never to team members. From the suggestions, the leader can set
   a song's feel or mark it "not a worship song" in one click. A theme
   without notes gets a hint to add them; notes are not required.
10. Leader reviews; leader or pastor confirms; pastor's decision wins. A
    lineup is a draft or confirmed; there is no other state.
    - The pastor's edits to a draft don't lock the leader out.
    - The pastor's lock starts when the pastor confirms a lineup, or edits one
      that is already confirmed. While it holds, the leader can't change the
      lineup. It lasts until the pastor reopens the lineup.
    - If the leader confirms and the pastor edits afterwards, the lineup stays
      confirmed and is marked "Edited by <pastor Label> (<person's name>)"
      with the time, shown to everyone who can see the lineup. Once team
      assignments exist, the assigned team members are also notified in the
      app.
    - A reopened lineup counts as unconfirmed: it is a draft again, and the
      pastor's lock is lifted. Team members can't see it; they see a note that
      the lineup is being revised, until it is confirmed again.
    - Only the pastor can send a lineup back. It returns to draft with a note
      for the leader. It is not a separate state: sending back a confirmed
      lineup reopens it.
11. Every keep/swap/remove is logged as feedback for future learning-to-rank.
    Training uses only lyrics-based scores (embedding similarity, the raw model
    worship score, tag scores), the church's own data (team knows it, usage,
    season, slot) and feedback labels.

CHORDS AND PLAYBACK
- Chord sheets are required for songs in a confirmed lineup, and allowed at any
  time: the worship leader can add one to any song in the pool ahead of time.
- A song with no sheet shows a "Find chords" action; the leader or pastor pastes
  a chart (e.g. from Worship Together or Ultimate Guitar), the app converts it
  to ChordPro (e.g. with ChordSheetJS), and it is saved for reuse and approved
  at once.
- A team member's paste is saved as pending. Other team members can't see it
  until the worship leader or the pastor approves it.
- Only the original ChordPro text and original key are stored. The service key
  is stored on the lineup item; transposition happens when the page loads.
- Playback is Spotify only: Web Playback SDK for connected Premium users (max 5
  users in Development Mode), embed player otherwise. No audio is stored. If an
  SDK call gets a 429, the player shows a short message and falls back to the
  embed player or an "Open in Spotify" link, without retrying.
- On confirmation, the lineup is saved automatically as a Spotify playlist on
  the worship leader's account. If the leader has no Spotify connection or
  Spotify returns a 429, this is skipped and a "Save to Spotify" button lets
  them try again later.

SPOTIFY SAFEGUARDS (every server-side Spotify call: search, tracks, playlists)
- Stop on the first 429: make no Spotify call until Retry-After has passed.
- Save a "Spotify blocked until" time that every process (the worker and web
  requests) checks before each Spotify call.
- After waiting, retry a request at most once; if it fails again, give up and
  mark the search run as failed.
- A Retry-After over one hour counts as a quota lockout.
- On QUOTA_EXCEEDED, pause all Spotify calls, tell the worship leader, and rank
  only the songs already in the pool.
- Run one search worker only, enforced by a PostgreSQL advisory lock taken at
  startup, so a second worker refuses to start. This also keeps LRCLIB to one
  request at a time.
- Never fetch a track already in the pool. No search-as-you-type.
- Record the number of Spotify calls on each search run, and every 429 with
  its reason and Retry-After.

HARD RULES (must not be violated)
- Spotify data (titles, artists, IDs, metadata), and any score adjusted by it
  such as the Trusted Artist bonus, is never used as ML model input or training
  data. The model uses only LRCLIB lyrics, the church's theme text, and tags.
- Lyrics never come from Spotify or unofficial Spotify lyric endpoints.
- No scraping of Ultimate Guitar or use of its private/mobile API.
- No Spotify Recommendations, Audio Features or Audio Analysis endpoints.
- Spotify data stored is limited to: track ID, title, artist, album, length.
- Spotify access and refresh tokens are stored encrypted (Fernet, with the key
  in .env) and never shown or logged.
- A lineup is not visible to team members before it is confirmed. A reopened
  lineup counts as unconfirmed.

EXPECTED DATABASE TABLES
User, Spotify connection (one per user), Service, Theme, Assignment,
Search run, Song, Song tag, Song embedding, Lineup, Lineup item,
Suggestion feedback, Chord sheet, Song usage, Announcement, Attendance.

Some are stored as fields rather than tables of their own, or not stored:
- Song embedding: stored as Song.embedding (JSON), with Song.analysed_with
  naming the engine that made it.
- Song tag: ThemeTag, linked by Song.tags; each tag's score is stored in
  Song.tag_scores (JSON).
- Attendance: a headcount per service, stored as WorshipService.attendance.
  There is no per-person attendance.
- Song usage: computed from confirmed lineups when needed, not stored. The
  song usage report highlights songs used more often than the recent-use
  window allows (the repeat window in Suggestion Settings); there is no
  separate overused-songs report.

To review the code against this spec, use [[Review-Prompt]].
