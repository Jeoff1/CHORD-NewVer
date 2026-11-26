---
status: accepted
---

# The lineup comes first; suggestions assist

The pastor or worship leader builds the lineup, slot by slot, choosing
songs on their own judgement or from the theme-based suggestions shown
beside it. Before, a lineup could only start from the suggestions ("Save
these songs as the lineup"), and songs were added by hand only after
that. Decided by the project owner on 2026-11-26 (Phase 9C): "the
suggestion becomes an actual suggestion instead of the main thing".

The theme-based song lineup is still CHORD's main module, and the
suggestion pipeline still serves it: suggestions are found the same way,
each can be added on its own, and "Fill the empty slots with suggestions"
keeps the one-click path.

## Considered Options

- **Keep the suggestions as the starting point**, with a separate "Start
  empty" button. Smaller change, but suggestions stay the main thing,
  which is what the owner asked to change.
- **Let people type a song that isn't on Spotify.** Left for later (owner):
  songs come from the church's song pool or from Spotify, so every song
  has playback and a playlist track. The owner may later want people to
  upload their own songs.

## Consequences

- A lineup can exist with no Search Run behind it; it starts when the
  first song is added.
- **Suggestion Feedback** gains a label, **picked**: a suggestion a person
  added on its own, a positive like kept. Songs added from the pool or
  Spotify still leave no feedback, so learning to rank (Phase 9) has
  fewer labelled songs when people choose by hand.
- Pastoral Staff now holds `songs.add_song` by default, so the pastor can
  bring a new song in from Spotify.
