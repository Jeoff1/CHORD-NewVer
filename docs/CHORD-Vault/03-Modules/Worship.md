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
    dropped when it finds nothing, one track by ID, and a single retry
    after an expired token or a short rate limit.
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
  - the Worship Check passes at 0.5; a Trusted Artist adds 0.25;
  - up to four Theme Tags scoring 0.5 or more, for worship songs only;
  - a Feel guess (mid-tempo when nothing points anywhere);
  - the embedding.
  - A Reviewed song keeps its check, tags and feel when analysed again.
- **Processing** (`pool.py`): `manage.py process_songs [--limit N]`
  fetches lyrics for songs that need them, then analyses songs whose
  lyrics are new. The model loads only when something needs analysis.
  Lyrics never appear in its output or the audit trail.
- **Screens** (`/worship/songs/`):
  - the song list, with search and filters (Worship Check, Theme Tag,
    Feel, team, lyrics status);
  - the song page: details, check and score, tags with scores, feel,
    lyrics, and when it was looked up and analysed;
  - Edit: correct the Worship Check, Theme Tags and Feel, and set "the
    team knows it"; saving marks the song Reviewed;
  - Check again: queues a fresh lookup and analysis;
  - Find on Spotify: search and add a track (a valid track ID is fetched
    from Spotify again, never taken from the form);
  - settings: Theme tags and Trusted artists, as tabs beside the worship
    settings.
- Adding, editing and Check again are in the audit trail; machine analysis
  is not.
- Tests: `apps/songs/tests/` (clients, ML, analysis, pool, views).

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

Default roles ([[Accounts]]):
- **Pastoral Staff** schedule services, post themes, record headcounts and
  manage templates and series; they see songs and theme tags.
- **Worship Leader** sees the schedule and manages the song pool, theme
  tags and trusted artists.
- **Team Member** sees the schedule.
- **Office Staff** see the schedule and record headcounts.

## Church settings this module depends on

- Service Templates and their Song Slots
- Series
- Theme Tags and Trusted Artists
- The "worship service" and "sermon" Labels
- The church's time zone (Church Profile)
- Installation settings in `.env`: `SPOTIFY_CLIENT_ID`,
  `SPOTIFY_CLIENT_SECRET`, `ML_ENGINE`, `ML_MODELS_DIR`,
  `LRCLIB_USER_AGENT`

## Open questions

- The Worship Check threshold and the Trusted Artist bonus are constants
  in `analysis.py`; Phase 5's suggestion settings may make them church
  settings.
- Feel guessed from lyrics is weak (stately hymns come out upbeat); people
  correct it once per song.
