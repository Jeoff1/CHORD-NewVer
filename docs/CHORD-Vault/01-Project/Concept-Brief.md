# Concept Brief: Worship Planning System

The brief that sets this project's scope, written 2026-11-16 and updated
2026-11-18 with the decisions agreed since. This note records what it says;
[[0005-worship-planning-scope]] records how CHORD follows it, and where
CHORD departs from its suggestions. Phase-by-phase detail and tests for
these decisions are in [[Design-Decisions]].

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

The vision is the same set of jobs as WorshipTools' Planning, Charts and
Community, but centralized: one app, one login and one database for the
whole team, with theme-based song suggestions as its core.

## Roles

| Role                    | Owns                    | Can do                                                                                                   |
| ----------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------- |
| Pastor (pastoral level) | The service and message | Create and schedule services; post the theme, scripture and notes; review, edit and confirm a lineup. The pastor's decision is final. |
| Worship leader          | The song lineup         | Generate suggestions; swap, lock, reorder and re-key songs; confirm; manage the song library and chord sheets; approve pasted chord sheets; assign musicians. |
| Team member             | Their part on the day   | View confirmed lineups; play tracks; read chord sheets in the service key; transpose a personal view (capo); paste a missing chord sheet for approval; mark availability. |
| Admin                   | The church account      | Manage users and roles, and church settings. The Administrator role can't be deleted. Spotify has one connection per user: each user connects their own account. |
| Office staff (optional) | The member directory    | Keep the member directory up to date: add and edit members and households, import and export them. |

A lineup is visible to the team only once it is confirmed. If the worship
leader and the pastor disagree, the pastor's decision wins: the pastor
edits the lineup directly or sends it back with notes.

- If the worship leader confirms and the pastor edits afterwards, the
  lineup stays confirmed, is marked "Edited by <pastor Label> (<name>)"
  with the time, and the team is notified.
- The pastor's edits to a draft don't lock the worship leader out. The
  pastor's lock starts only when the pastor confirms a lineup, or edits one
  that is already confirmed. The worship leader can't change the lineup
  until the pastor reopens it.
- "Pastor's decision is final" is a permission held by the pastoral role,
  not a check on a role name.

## Core module: theme-based lineup suggestion

There is no manual song upload. Every song the system checks is saved, so
the song pool grows from Spotify with each theme. Spotify supplies the
candidates and the playback; the model reads only LRCLIB lyrics, the
church's theme text and tags.

Stored for each song: Spotify track ID, title, artist, album and length
(never model input); lyrics from LRCLIB (cached); the worship check result
and theme tags (editable); feel (upbeat, mid or slow; guessed, then
corrected once per song); a lyrics embedding; usage history and whether
the team knows it; a ChordPro chord sheet, required once the song is in a
confirmed lineup and allowed earlier.

Pipeline stages:

1. **Theme intake**: title, main scripture, sermon notes.
2. **Search phrases**: key words and short phrases from the theme, each a
   Spotify search with a genre filter such as `genre:worship`; retried
   without the filter when it returns nothing.
3. **Spotify search**: 10 songs per page, a few pages per phrase.
4. **Cleanup**: drop repeats, karaoke, instrumental and backing tracks.
   Drop a live or acoustic version only when the plain version was also
   found; a song released only as a live recording is kept.
5. **Lyrics**: from LRCLIB by title, artist, album and length, one request
   at a time, cached. Songs without lyrics are set aside.
6. **Worship check and tagging**: a zero-shot classifier reads the lyrics,
   drops songs that aren't Christian worship songs, and suggests theme
   tags. An optional list of trusted worship artists adds a bonus, applied
   as a church rule after the model: the model's raw score is stored
   separately, and the artist name never reaches the model.
7. **Ranking**: every accepted song in the pool, not only this run's
   finds, is ranked. Theme and lyrics are compared as embeddings, combined
   with familiarity, season and recent use.
8. **Sequencing**: top songs placed in the service template's slots by
   feel.
9. **Explanation**: each pick says why it was chosen.
10. **Review**: swap, lock, reorder, regenerate; then confirm.
11. **Learning**: every accept, swap and rejection is logged; once enough
    confirmed lineups exist, they train a learning-to-rank model that
    replaces the hand-set weights. Training uses only lyrics-based scores,
    the church's own data and feedback; never Spotify fields, the trusted
    artist bonus, or any score that includes it.

Starting score, with hand-tuned weights:

```
score = w1·relevance + w2·familiarity + w3·season − w4·recency
```

## Playback, chord sheets and keys

- **Playback**: Spotify is the only audio source. Each user can connect a
  Spotify Premium account and play full tracks through the Web Playback
  SDK; anyone else gets the embedded player or an "Open in Spotify" link.
  On confirmation the lineup is saved as a Spotify playlist on the worship
  leader's account. Users' Spotify tokens are stored encrypted, with the key
  in `.env`.
- **Chord sheets**: stored as ChordPro. Only the original ChordPro text and
  key are stored; the server transposes the sheet for each view
  ([[0009-transposition-on-the-server]]), and changing the key re-renders it
  with htmx. ChordSheetJS is used only in the browser, to convert a pasted
  chart to ChordPro.
  A song without a sheet shows a "Find chords" action that opens a search
  on free sources such as Worship Together and Ultimate Guitar. The worship
  leader or pastor pastes the chart, and it is converted to ChordPro on
  paste and approved at once. A team member's paste waits for approval by
  the worship leader or pastor. Each lineup shows how many of its songs
  have chord sheets. There is no automatic import.
- **Keys**: each lineup entry has its own service key. The worship leader
  transposes by semitone or picks a key, and every musician's sheet
  follows. Helpers: the keys the song was sung in before (from confirmed
  lineups, most recent first), a capo position, and a Nashville-number
  view. Spotify audio can't be pitch-shifted, so the recording plays in its
  own key; a practise-along toggle shows the chords in the recording's key
  so musicians can play with it. Spotify gives no key, so a person enters
  the recording's key on the song; without it, the toggle is hidden.
- **Lyrics**: the full lyrics on a song page are for the people who plan;
  team members see the words through the chord sheet.

## Supporting modules

| Module                                | In scope | Covers                                                        |
| ------------------------------------- | -------- | ------------------------------------------------------------- |
| Service scheduling                    | Yes      | Calendar, service templates, recurring schedules              |
| Theme and sermon series               | Yes      | A theme per service, grouped into series                      |
| Team roster and assignments           | Yes      | Who plays what, swap requests, availability and blackout dates |
| Song library                          | Yes      | Songs found on Spotify, lyrics, tags, chord sheets, usage     |
| Announcements                         | Yes      | Notes to the whole team or one service team                   |
| Song usage report                     | Yes      | What was sung and when; overused songs                        |
| Member directory                      | Basic    | Names, contact details, households, team and role; CSV import |
| Attendance                            | Basic    | Headcount per service                                         |
| Leadership appointment and ordination | No       | Too complex for this system's purpose                         |
| Finance, giving, tithes, payroll      | No       | Better served by dedicated software                           |
| Records, requested services           | No       | Outside worship planning                                      |
| Ministries and events                 | No       | Outside worship planning                                      |
| SMS, check-in and follow-up           | No       | Beyond a minimal management system                            |
| Per-person attendance                 | No       | A headcount per service is enough                             |

## Platform constraints

| Constraint                                                                                   | Decision in the brief                                                                 |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Spotify removed Recommendations, Audio Features and Audio Analysis for new apps (Nov 2024)   | Own recommendation pipeline; feel guessed and corrected; key stored per lineup song   |
| Development Mode search returns at most 10 results per request                               | Several search phrases per theme, a few pages each                                    |
| Search matches titles, artists and albums, not lyrics; `genre:` filters sometimes return nothing | Retry without the filter; a lyrics-based worship check drops other songs          |
| Spotify's policy bans feeding Spotify content into ML models                                  | Spotify only decides which songs get checked; the model reads LRCLIB lyrics, theme text and tags. A compliance assumption, not a ruling from Spotify |
| Spotify rate-limits calls in a rolling 30-second window and sets a per-account quota; lockouts can last hours | Stop on the first 429, respect Retry-After across processes, never retry in a loop, pause on `QUOTA_EXCEEDED` and rank the existing pool instead, run one worker |
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
- **Disagreement on a lineup**: the pastor's decision is final.
- **Audio**: Spotify only; no practice-track uploads.
- **Attendance**: a headcount per service.
- **Open**: must the proposal show a trained model, or is the
  embedding-and-rules pipeline, with learning-to-rank planned for later,
  enough?

## Suggested stack (suggestions, not requirements)

React or Next.js; Node.js or FastAPI; a job queue (Celery or BullMQ);
KeyBERT, sentence-transformers, a Hugging Face zero-shot classifier,
scikit-learn or LightGBM; PostgreSQL with pgvector; ChordSheetJS. CHORD
keeps its own stack; see [[0005-worship-planning-scope]] and
[[Technology-Stack]].