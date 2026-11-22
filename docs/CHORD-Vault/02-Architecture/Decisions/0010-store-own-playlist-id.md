---
status: accepted
---

# CHORD stores the ID of a playlist it created itself

The hard rule "store only these Spotify fields: track ID, title, artist,
album and length" (AGENTS.md) now also allows **the ID of a playlist CHORD
itself created**. It is kept on the Lineup only to find and update that
Lineup Playlist, and is never model input or a training feature. With it,
the Lineup may also store which account owns the playlist (the Church
Spotify Account, or the user who saved it) and the track IDs it holds.
Approved by the project owner on 2026-11-22, after Phase 7 part B
([[Design-Decisions]], Phase 7).

The reason: without the playlist ID, CHORD can't tell that a lineup
already has a playlist, so every "Save to Spotify", and every confirmation
after a reopen, would make a duplicate playlist on the account.

## Considered Options

- **Store nothing, and make a new playlist each time.** Keeps the rule as
  it was, but fills the account with copies of the same lineup, and CHORD
  can't link to the playlist or tell when the lineup's songs have changed
  since it was saved. Rejected.
- **Find the playlist again by its name** on the account. Needs a listing
  call each time (more Spotify calls under the safeguards), and breaks
  when someone renames the playlist or two services share a name and date.
  Rejected.

## Consequences

- `Lineup` has `spotify_playlist_id`, `spotify_playlist_owner`,
  `spotify_playlist_on_church_account`, `spotify_playlist_tracks` and
  `spotify_playlist_saved_at`. None of them is in Suggestion Feedback or
  any other training data.
- The playlist ID belongs to CHORD's own playlist, not to a song: song
  data from Spotify is still limited to track ID, title, artist, album and
  length.
