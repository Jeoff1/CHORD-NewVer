=== INTENDED WORKFLOW ===

Since 2026-11-25 (Phase 9B, [[0014-church-platform]]): one installation
serves many churches. Everything below happens inside one church, the
person's Current Church; their roles are those of their Membership there.
A church registers itself, needing only its name (its details and public
profile may be given then too, all optional); anyone may create an
account, find a church in the Directory, and request an Occasion Type the
church offers publicly from its Church Homepage.

Updated 2026-11-24 with the adviser's comments ([[Design-Decisions]],
"Adviser comments, 24 Nov"; Phase 9A, planned, not built yet). Where this
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
- Worship leader: generates the suggested lineup and saves it as the lineup,
  swaps/locks/reorders/re-keys songs, confirms the lineup, adds chord sheets,
  approves chord sheets pasted by team members.
- Team member: sees a lineup only after it is confirmed; plays songs, reads
  chord sheets; may paste a missing chord sheet for a song in a confirmed
  lineup, which waits for approval by the worship leader or the pastor.
- Admin: users, roles and settings. The Administrator role can't be deleted
  and always holds every permission. Spotify has one connection per user:
  each user connects their own Spotify account (for playback, and for
  saving playlists when the church has no Church Spotify Account). The
  church may also connect one Church Spotify Account in church settings,
  used only for playlists. The app's own Spotify credentials
  are set in .env when CHORD is installed.
- Office staff (optional): keeps the member directory up to date. Doesn't
  see lineups.
- Church member (Phase 9A): sees the dashboard, their own member record,
  announcements to everyone and the service schedule with theme titles;
  requests occasions and follows their requests. Never sees lineups, song
  pages, chord sheets, lyrics or other members. Accounts made in a batch
  from the Members list get this role by default.
- Changing someone's role (for example, a worship leader who becomes a
  church member) never removes what they did before; when they leave the
  team, the admin ends or keeps their assignments on future services.

People who can change lineups (the leader and the pastor) also see a theme's
sermon notes; team members don't.

PLANNING A SERVICE (Phase 9C, 2026-11-26)
The service page guides the people who plan through four steps, with a
next-step panel naming what to do and one button for it:
  Theme -> Praise Team -> Song Lineup -> Confirm
- Theme: the pastor posts the theme, and may attach the sermon as a PDF
  (private to the people who plan). The Main scripture suggests passages
  from the stored Bible as it is typed and shows the passage. Suggestions
  read all of it: title, passage text, notes and PDF.
- Praise Team (the church's "team" Label; only while Teams is on): assign
  who serves that day. Suggested, never required: "Skip for now" goes on to
  the songs.
- Song Lineup: add the songs you have in mind slot by slot, with the
  suggestions beside them to add one at a time or to fill the empty slots;
  review (swap, lock, reorder, keys), and preview what the Spotify
  playlist will hold, all on one page.
- Confirm: a rundown of the service, theme, team, songs and warnings, then
  Confirm. The playlist is saved on confirmation, as below.
Team members never see the steps, the panel, suggestions or a draft.

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
    - Each lineup song's feel reason is worked out for the slot it is in now.
      Move arrows show only where a move is allowed. People are named by
      their full name (or username) in marks and notes.
    - Since 2026-11-26 the lineup comes first and suggestions assist
      ([[0015-lineup-first-suggestions-assist]]): the leader or the pastor
      adds songs slot by slot from the song pool (or Spotify, through the
      pool), adds suggested songs one at a time, or fills the empty slots
      with suggestions. The lineup keeps its own copy of each song, which
      later corrections to the suggestions never change.
      Review swaps a song for another ranked suggestion, locks, reorders,
      re-keys or removes songs, adds a song from the pool, or regenerates
      around locked songs, from the service's latest finished search. A
      locked song isn't swapped, moved or removed, and no song moves into its
      place. Any pool song can be added unless a person marked it "Not a
      worship song"; one that failed the worship check or was never checked
      shows a small warning in the review. A lineup never holds two songs
      with the same title.
    - A cancelled or past service gets no suggestions and no new lineup. A
      cancelled service's lineup can't be confirmed; a past service's lineup
      can still be edited and confirmed.
    - The pastor's edits to a draft don't lock the leader out.
    - The pastor's lock starts when the pastor confirms a lineup, or edits one
      that is already confirmed. While it holds, the leader can't change the
      lineup. It lasts until the pastor reopens the lineup.
    - If the leader confirms and the pastor edits afterwards, the lineup stays
      confirmed and is marked "Edited by <pastor Label> (<person's name>)"
      with the time, shown to everyone who can see the lineup. The service's
      assigned team is also notified in the app (see TEAMS).
    - If the leader edits a confirmed lineup that isn't under the pastor's
      lock, it stays confirmed and is marked "Changed by <person's name>" with
      the time, shown to everyone who can see it. There is no lock.
    - Only the latest mark shows: a later pastor's edit replaces "Changed by"
      with "Edited by <pastor Label> (<name>)". Locking or unlocking a song
      isn't an edit.
    - A reopened lineup counts as unconfirmed: it is a draft again, and the
      pastor's lock and the mark are cleared. Team members can't see it; they
      see a note that the lineup is being revised, until it is confirmed
      again. A draft that was never confirmed doesn't exist for them (not
      found).
    - Only the pastor can send a lineup back. It returns to draft with a note
      for the leader. It is not a separate state: sending back a confirmed
      lineup reopens it. Confirming again clears the note.
11. Every keep/swap/remove is logged as feedback for future learning-to-rank,
    when the lineup is confirmed. Each suggestion placed in the lineup is
    labelled kept (a top pick that stayed), swapped in (an alternative the
    leader chose in a swap), swapped (replaced by a swap) or removed. Songs
    replaced by regenerating, and songs added from the pool, leave no
    feedback; confirming again replaces it. Training uses only lyrics-based
    scores (embedding similarity, the raw model worship score, tag scores),
    the church's own data (team knows it, usage, season, slot) and feedback
    labels.

CHORDS AND PLAYBACK
- Chord sheets are required for songs in a confirmed lineup, and allowed at any
  time: the worship leader can add one to any song in the pool ahead of time.
- A song with no sheet shows a "Find chords" action; the leader or pastor pastes
  a chart (e.g. from Worship Together or Ultimate Guitar). The server converts
  it to ChordPro (the person sees the result before saving) and checks that the
  saved text is valid ChordPro. It is saved for reuse and approved at once.
- A ChordPro file (.cho, .chopro, .chordpro, .pro or .txt, up to 200 KB, UTF-8)
  can be imported on the chord sheet form instead of pasting: its text goes in
  the box to check, and its {key:} or {k:} line fills the key. The file isn't
  stored, other directives stay in the text, and rhythm lines such as
  |D//G|////| or Worship Together's [| D / / G | / / / / |] transpose (an
  unreadable one becomes a comment, never a save error). Plain section lines
  such as "Verse 1" or "Outro" show as section labels. An optional chord in
  parentheses, such as (F#m7), transposes and keeps its parentheses; N.C.,
  repeat marks (x2) and footnote marks (*) stay as written. Anything else
  unreadable in brackets is kept as written ([*text]) with a warning; the
  viewer shows such marks in grey italic and notes that they weren't
  transposed when the sheet is shown in another key. A stray ] that closes
  nothing is removed and listed in the warning. The sheet is still
  saved: only broken ChordPro (an unclosed bracket or directive) stops a
  save. A person still brings in each chart; nothing is
  fetched from any site.
- A team member's paste (or import) is saved as pending. Other team members can't see it
  until the worship leader or the pastor approves it. A team member may paste
  only for a confirmed lineup song that has no sheet, and has at most one
  pending sheet per song.
- A song has at most one approved sheet. Approving a pending sheet when one is
  already approved is refused; only pending sheets can be discarded. The audit
  trail never holds a sheet's text.
- A sheet being "required" doesn't block confirming: the lineup shows how many
  songs have an approved sheet and marks the ones that still need one.
- Each lineup song has its own page with the sheet in the service key; team
  members open it once the lineup is confirmed.
- Only the original ChordPro text and original key are stored. The service key
  is stored on the lineup item. All transposition runs on the server, in
  Python: the service key, a personal transpose, capo positions and Nashville
  numbers; changing the key re-renders the sheet with htmx
  ([[0009-transposition-on-the-server]]). C major and A minor use flats;
  Nashville numbers in a minor key count from the minor tonic (shown with a
  note) and ignore a capo; capo positions 0 to 7 are offered, with the easy
  shapes marked. A personal transpose lives only in the page address and is
  never saved.
- When choosing a lineup song's service key, the keys that song was sung in
  (its service keys in confirmed lineups) are shown, most recent first.
- A practise-along toggle shows the chords in the recording's key. Spotify
  gives no key, so a person enters the recording's key on the song; without
  it, the toggle is hidden.
- Full lyrics on the song page are shown only to people who plan (Worship
  Leader and Pastoral Staff by default), through a permission. Team members
  see the words through the chord sheet.
- Playback is Spotify only, on the lineup song page: Web Playback SDK for
  connected Premium users (max 5 users in Development Mode), embed player
  otherwise. No audio is stored. Whenever the SDK can't be used, including a
  429, the player shows a short message and falls back to the embed player or
  an "Open in Spotify" link, without retrying. The player gets the person's
  own short-lived access token from a POST-only, never-cached page and keeps
  it only in memory; the refresh token never leaves the server.
- On confirmation, the lineup is saved automatically as its own Spotify
  playlist, named with the service name and date:
  - with a Church Spotify Account connected, on that account, as a public
    playlist, whoever confirms; everyone who can see the confirmed lineup
    gets an "Open the playlist" link;
  - without one, on the confirmer's own account, as a private playlist; only
    the owner gets the link.
  Songs not on Spotify are left out. If there is no usable account or
  Spotify returns a 429, this is skipped at once, without waiting, and a
  "Save to Spotify" button lets people who may save try again later.
  Confirming the same lineup again, or "Save to Spotify", updates that
  lineup's own playlist; other services' playlists are never changed. The
  Church Spotify Account is never used for playback. A stored playlist is
  made again only when Spotify answers 404, or 403 because the connected
  account doesn't own it (checked by asking Spotify, storing neither
  account's ID); any other 403 leaves the lineup confirmed with "Save to
  Spotify".

TEAMS (Teams module; needs Worship)
- The team is a permission: holders of teams.view_assignment (Team Member,
  Worship Leader and Pastoral Staff by default; never a role-name check).
  Only they can have a Team Profile or Blackout Dates, be assigned or take
  a swap. Office Staff don't see these pages.
- Team Parts are a list the church edits (voices and instruments), with
  neutral defaults. A person's Team Profile is just the parts they can take;
  it belongs to their user account, not to a Member record.
- The worship leader assigns people to parts at a service (Pastoral Staff
  see teams but don't assign by default). Only people on the team whose
  Team Profile has that part can be assigned, and nobody on a day they
  blacked out. A cancelled or past service's team is frozen: no new
  assignments, replies, removals or swaps.
- Each assignment has a reply: Pending, Accepted or Declined, given once
  while Pending. A declined assignment stays on the service page for the
  leader to fill.
- Blackout Dates are ranges of whole days in the church's time zone, not
  already passed. A blackout over an existing assignment (Pending or
  Accepted, service not cancelled) is refused; the person declines it, or
  asks for a swap (the message links to it).
- "My schedule" shows a person's assignments with reply and swap buttons,
  the swaps they can take, their parts and their blackout dates.
- Swap Request: someone Pending or Accepted on a future service that isn't
  cancelled asks to be replaced, and may withdraw while it is open. Anyone
  eligible sees it: on the team, has the part, isn't blacked out that day
  and isn't already on that service. No approval: the first to take it gets
  the assignment as Accepted (if two press at once, only the first does),
  and the original assignment ends. The audit trail records who handed over
  and who took it.
- In-app notifications only (no email or SMS) go to the service's assigned
  people whose reply is Pending or Accepted, never to the person who caused
  them, when the pastor edits a confirmed lineup, anyone else edits a
  confirmed lineup, or the lineup is confirmed. A person is also notified
  when they are assigned. Nothing is sent for a cancelled or past service,
  or for a draft. The navigation shows the unread count; opening a
  notification marks it read, and all can be marked read at once.
- Notifications are core (Phase 9A): everyone signed in has them,
  whichever modules are switched on. Teams sends its own only while Teams
  is on; occasion answers are sent whenever Worship is on.

ANNOUNCEMENTS (Announcements module)
- Notes to everyone (everyone signed in) or to one service's team (its
  assigned people who are Pending or Accepted; offered and shown only while
  Teams is on, for a coming service that isn't cancelled). Posting is the
  permission announcements.add_announcement, held by Pastoral Staff and
  Worship Leader by default. No expiry: the author archives an
  announcement, and then nobody sees it.

OCCASIONS (Occasions module; Phase 9A, built 2026-11-24; [[0013-occasions-module]])
- Weddings, baptisms, funerals and the like are not worship services: they
  have their own module, form and list, and no theme, lineup or team.
- The church keeps a list of occasion types (Wedding, Baptism, Funeral,
  ... come as examples, switched off), each with a usual length.
- The pastor adds an occasion directly: its type, date and time, length,
  who it is for, the officiant, the venue and notes. It can be edited or
  cancelled.
- A church member requests one (type, date and start time, who it is for,
  a note). Signing in is enough; no member record is needed. The request
  is Pending, then Approved or Declined (with a reason); the requester may
  withdraw it while Pending.
- Approving is the permission occasions.approve_occasion (Pastoral Staff by
  default, never a role-name check) and books the occasion.
- Occasions share the worship calendar. Every worship service books its
  template's usual length. Adding, moving, requesting or approving an
  occasion that overlaps another booking is refused. People who may see
  occasions see their details; everyone else sees only "Booked".
- The requester is notified in the app. No fees, requirements or records.

ACCOUNTS, HISTORY AND REPORTS (Phase 9A, planned)
- Batch accounts from the Members list: temporary passwords shown once,
  never stored in plain text or logged, changed at first sign-in.
- The Audit Trail also records sign-in, sign-out and failed sign-in, and
  each user's page has a History tab.
- A Members report with filters (status, age group, sex, household, date
  joined, Custom Fields), a print layout and CSV. Age groups are a
  church-edited list. "Who attended a service" is on hold.

SPOTIFY SAFEGUARDS (every server-side Spotify call: search, tracks, playlists)
- Stop on the first 429: make no Spotify call until Retry-After has passed.
- No web request waits on a Retry-After: a Spotify call made during a web
  request fails fast on a 429 (for example, the playlist shows "Save to
  Spotify" instead). Only the search worker may wait out a short one.
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
- Spotify data stored is limited to: track ID, title, artist, album, length,
  and the ID of a playlist CHORD itself created (only to find and update it;
  never model input or training data).
- Spotify access and refresh tokens (personal ones and the Church Spotify
  Account's) are stored encrypted (Fernet, with the key
  in .env) and never shown or logged.
- A lineup is not visible to team members before it is confirmed. A reopened
  lineup counts as unconfirmed.

EXPECTED DATABASE TABLES
User, Spotify connection (one per user), Church Spotify account (at most
one), Service, Theme, Team part, Team profile, Assignment, Blackout date,
Swap request, Notification, Occasion request and Age group (Phase 9A),
Search run, Song, Song tag, Song embedding, Lineup, Lineup item,
Suggestion feedback, Chord sheet, Song usage, Announcement, Attendance.

Some are stored as fields rather than tables of their own, or not stored:
- Song embedding: stored as Song.embedding (JSON), with Song.analysed_with
  naming the engine that made it.
- Song tag: ThemeTag, linked by Song.tags; each tag's score is stored in
  Song.tag_scores (JSON).
- Attendance: a headcount per service, stored as WorshipService.attendance.
  There is no per-person attendance (the adviser's request for it is on
  hold, 2026-11-24).
- Song usage: computed from confirmed lineups when needed, not stored;
  cancelled services never count. Ranking counts every confirmed lineup of a
  service before the one being ranked, even one not held yet; the song
  usage report counts only services already held. The report highlights
  songs sung again sooner than the repeat window (Suggestion Settings), so
  more often than the recent-use window allows; there is no separate
  overused-songs report. The report needs the permission
  worship.view_song_usage (Worship Leader and Pastoral Staff by default).
- Attendance report: the headcount of each service held, for people who may
  record headcounts; it doesn't exist until a headcount has been recorded.

To review the code against this spec, use [[Review-Prompt]].
