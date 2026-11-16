# Concept Brief: Worship Planning System

The brief that sets this project's scope, written 2026-11-16. This note
records what it says; [[0005-worship-planning-scope]] records how CHORD
follows it, and where CHORD departs from its suggestions.

## Overview

The system turns a sermon theme into a ready-to-rehearse worship set:
suggested songs, a listen-along track, a chord sheet, and the right key for
the band.

- The pastor posts the service's theme.
- The system searches Spotify for songs whose lyrics fit the message and
  proposes a lineup that flows well.
- The worship leader adjusts it, and either the worship leader or the
  pastor confirms it.
- The team opens one page per song with the track, the chords and the key
  they will play in.

Around that core sits light church management: service scheduling, team
rosters and song history. Heavy processes stay out.

## Roles

| Role                    | Owns                    | Can do                                                                                                   |
| ----------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------- |
| Pastor (pastoral level) | The service and message | Create and schedule services; post the theme, scripture and notes; review, edit and confirm a lineup. The pastor's decision is final. |
| Worship leader          | The song lineup         | Generate suggestions; swap, lock, reorder and re-key songs; confirm; manage the song library and chord sheets; assign musicians. |
| Team member             | Their part on the day   | View confirmed lineups; play tracks; read chord sheets in the service key; transpose a personal view (capo); mark availability. |
| Admin (optional)        | The church account      | Manage users and roles, church settings, and integrations such as the Spotify connection.                 |

A lineup is visible to the team only once it is confirmed. If the worship
leader and the pastor disagree, the pastor's decision wins: the pastor
edits the lineup directly or sends it back with notes.

## Core module: theme-based lineup suggestion

There is no manual song upload. Every song the system checks is saved, so
the song pool grows from Spotify with each theme. Spotify supplies the
candidates and the playback; the model reads only lyrics and tags from
outside Spotify.

Stored for each song: Spotify track ID, title, artist, album and length
(never model input); lyrics from LRCLIB (cached); the worship check result
and theme tags (editable); feel (upbeat, mid or slow; guessed, then
corrected once per song); a lyrics embedding; usage history and whether
the team knows it; a ChordPro chord sheet, added only once the song is in a
confirmed lineup.

Pipeline stages:

1. **Theme intake**: title, main scripture, sermon notes.
2. **Search phrases**: key words and short phrases from the theme, each a
   Spotify search with a genre filter such as `genre:worship`; retried
   without the filter when it returns nothing.
3. **Spotify search**: 10 songs per page, a few pages per phrase.
4. **Cleanup**: drop repeats, live and acoustic duplicates, karaoke and
   instrumental versions.
5. **Lyrics**: from LRCLIB by title, artist, album and length, one request
   at a time, cached. Songs without lyrics are set aside.
6. **Worship check and tagging**: a zero-shot classifier reads the lyrics,
   drops songs that aren't Christian worship songs, and suggests theme
   tags. An optional list of trusted worship artists adds confidence.
7. **Ranking**: theme and lyrics compared as embeddings, combined with
   familiarity, season and recent use.
8. **Sequencing**: top songs placed in the service template's slots by
   feel.
9. **Explanation**: each pick says why it was chosen.
10. **Review**: swap, lock, reorder, regenerate; then confirm.
11. **Learning**: every accept, swap and rejection is logged; once enough
    confirmed lineups exist, they train a learning-to-rank model that
    replaces the hand-set weights.

Starting score, with hand-tuned weights:

```
score = w1·relevance + w2·familiarity + w3·season − w4·recency
```

## Playback, chord sheets and keys

- **Playback**: Spotify is the only audio source. Each user can connect a
  Spotify Premium account and play full tracks through the Web Playback
  SDK; anyone else gets the embedded player or an "Open in Spotify" link.
  On confirmation the lineup is saved as a Spotify playlist on the worship
  leader's account.
- **Chord sheets**: stored as ChordPro, shown with ChordSheetJS. The
  worship leader types or pastes each sheet; text copied from Ultimate
  Guitar is converted on paste. There is no automatic import.
- **Keys**: each lineup entry has its own service key. The worship leader
  transposes by semitone or picks a key, and every musician's sheet
  follows. Helpers: a key from the lead singer's range, a capo position,
  and a Nashville-number view. Spotify audio can't be pitch-shifted, so the
  recording plays in its original key.

## Supporting modules

| Module                                | In scope | Covers                                                        |
| ------------------------------------- | -------- | ------------------------------------------------------------- |
| Service scheduling                    | Yes      | Calendar, service templates, recurring schedules              |
| Theme and sermon series               | Yes      | A theme per service, grouped into series                      |
| Team roster and assignments           | Yes      | Who plays what, swap requests, availability and blackout dates |
| Song library                          | Yes      | Songs found on Spotify, lyrics, tags, chord sheets, usage     |
| Announcements                         | Yes      | Notes to the whole team or one service team                   |
| Song usage report                     | Yes      | What was sung and when; overused songs                        |
| Member directory                      | Basic    | Names, contact details, ministry and role                     |
| Attendance                            | Basic    | Headcount per service                                         |
| Leadership appointment and ordination | No       | Too complex for this system's purpose                         |
| Finance, tithes, payroll              | No       | Better served by dedicated software                           |

## Platform constraints

| Constraint                                                                                   | Decision in the brief                                                                 |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Spotify removed Recommendations, Audio Features and Audio Analysis for new apps (Nov 2024)   | Own recommendation pipeline; feel guessed and corrected; key stored per lineup song   |
| Development Mode search returns at most 10 results per request                               | Several search phrases per theme, a few pages each                                    |
| Search matches titles, artists and albums, not lyrics; `genre:` filters sometimes return nothing | Retry without the filter; a lyrics-based worship check drops other songs          |
| Spotify's policy bans feeding Spotify content into ML models                                  | Spotify only decides which songs get checked; the model reads LRCLIB lyrics and tags  |
| The Spotify Web API has no lyrics endpoint                                                   | Lyrics from LRCLIB                                                                    |
| LRCLIB rate-limits clients and disallows parallel requests                                   | One lookup at a time, every result cached                                             |
| Development Mode needs a Premium owner and allows 5 users (Feb 2026)                         | Stay in Development Mode; note the limit as a scaling constraint                      |
| Spotify streams can't be modified                                                            | Key changes apply to chord sheets only                                                |
| Ultimate Guitar has no public API                                                            | Chords are pasted by hand and converted to ChordPro                                   |
| Lyrics and chord charts are copyrighted; no CCLI licence                                     | Keep them private to the project's few users; list as a limitation                    |

## Decisions and open question

- **Scope**: a personal project for a Software Engineering proposal; one
  church, five users or fewer.
- **Song source**: all of Spotify, searched per theme, as the adviser
  requested.
- **Language**: English only.
- **Tags**: a zero-shot classifier scores lyrics against a fixed list of
  about 30 worship themes; the worship leader can edit them.
- **CCLI / SongSelect**: none.
- **Open**: must the proposal show a trained model, or is the
  embedding-and-rules pipeline, with learning-to-rank planned for later,
  enough?

## Suggested stack (suggestions, not requirements)

React or Next.js; Node.js or FastAPI; a job queue (Celery or BullMQ);
KeyBERT, sentence-transformers, a Hugging Face zero-shot classifier,
scikit-learn or LightGBM; PostgreSQL with pgvector; ChordSheetJS. CHORD
keeps its own stack; see [[0005-worship-planning-scope]] and
[[Technology-Stack]].
