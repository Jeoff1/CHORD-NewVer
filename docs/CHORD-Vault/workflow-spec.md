=== INTENDED WORKFLOW ===

ROLES
- Pastor: schedules services, posts the theme (title, scripture, sermon notes),
  can review, edit and confirm a lineup. The pastor's decision is final.
- Worship leader: generates the suggested lineup, swaps/locks/reorders/re-keys
  songs, confirms the lineup, adds missing chord sheets.
- Team member: sees a lineup only after it is confirmed; plays songs, reads
  chord sheets; may paste a missing chord sheet for the leader to approve.
- Admin (optional): users, roles, settings, Spotify connection.

SONG SELECTION (core module)
1. Pastor posts a theme for a service.
2. System turns the theme into several search phrases.
3. System searches all of Spotify (max 10 results per request, so it paginates
   with an offset; retries without a genre filter if a filtered search is empty).
4. System removes duplicates, live/karaoke/instrumental versions.
5. System fetches lyrics from LRCLIB (one request at a time) and caches them.
   Songs already in the pool skip this. Songs with no lyrics are set aside.
6. A classifier drops non-worship songs and suggests theme tags.
7. Songs are ranked by embedding similarity between theme and lyrics, plus
   familiarity (past usage), season fit, and a penalty for recent use.
8. Top songs are placed in service slots (opener, praise, worship, response).
9. Each suggestion stores a reason it was picked.
10. Leader reviews; leader or pastor confirms; pastor's decision wins.
11. Every keep/swap/remove is logged as feedback for future learning-to-rank.

CHORDS AND PLAYBACK
- Chord sheets are added only for songs in a confirmed lineup.
- A song with no sheet shows a "Find chords" action; the leader pastes a chart
  (e.g. from Worship Together or Ultimate Guitar), the app converts it to
  ChordPro (e.g. with ChordSheetJS), and it is saved for reuse.
- Only the original ChordPro text and original key are stored. The service key
  is stored on the lineup item; transposition happens when the page loads.
- Playback is Spotify only: Web Playback SDK for connected Premium users (max 5
  users in Development Mode), embed player otherwise. No audio is stored.
- A confirmed lineup can be saved as a Spotify playlist.

HARD RULES (must not be violated)
- Spotify data (titles, artists, IDs, metadata) is never used as ML model input
  or training data. The model uses only LRCLIB lyrics and tags.
- Lyrics never come from Spotify or unofficial Spotify lyric endpoints.
- No scraping of Ultimate Guitar or use of its private/mobile API.
- No Spotify Recommendations, Audio Features or Audio Analysis endpoints.
- Spotify data stored is limited to: track ID, title, artist, album, length.
- Spotify tokens are stored encrypted.
- A lineup is not visible to team members before it is confirmed.

EXPECTED DATABASE TABLES
User, Spotify connection, Service, Theme, Assignment, Search run, Song,
Song tag, Song embedding, Lineup, Lineup item, Suggestion feedback,
Chord sheet, Song usage, Announcement, Attendance.

=== WHAT TO PRODUCE ===

1. A table with columns: Check | Status (Pass / Partial / Fail / Not found) |
   Evidence | What to fix. Cover every role rule, every song-selection step,
   every chords/playback rule, every hard rule, and every expected table.
2. A list of anything in my material that is NOT part of this flow (extra
   features, extra tables, or behaviour that contradicts the flow).
3. The 3 most important fixes, in priority order.
4. A one-line verdict: does it follow the flow, mostly follow it, or not?