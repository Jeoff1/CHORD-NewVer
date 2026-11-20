---
status: accepted
---

# Chord sheets are transposed on the server, in Python

Chord sheets are stored once, as ChordPro in the song's original key. Every
other way of showing them is worked out on the server, in Python:
- the lineup's service key;
- a musician's personal transpose;
- capo positions;
- Nashville numbers;
- the practise-along view in the recording's key.

Changing the key re-renders the sheet with htmx
([[0002-server-rendered-ui]]). A pasted Ultimate Guitar-style chart is
converted to ChordPro on the server too, and the server checks that the
saved text is valid ChordPro. Decided on 2026-11-19 for Phase 7
([[Design-Decisions]]); the conversion moved to the server on 2026-11-20
(below).

## Considered Options

- **Transposing in the browser with ChordSheetJS**, as the
  [[Concept-Brief]] first suggested ("the page transposes on load"). The
  musical rules would then live in JavaScript, which the project's test
  suite doesn't run, so "the viewer's transposing is tested" couldn't be
  checked by `scripts/check.ps1`. The key shown to the team would also
  depend on code that never passes through the server. Rejected.
- **Both**: the browser for display, the server for anything stored. That
  means two implementations of the same rules, which can drift apart.
  Rejected.
- **ChordSheetJS for the paste conversion only**, in the browser, as first
  decided. ChordSheetJS turned out to be GPL-2.0-only, so on 2026-11-20
  the user chose a small converter in Python instead
  (`apps/songs/chords.py`): no GPL code, one language, and covered by
  `scripts/check.ps1` like the transposer. Rejected.

## Consequences

- CHORD has its own small ChordPro reader and transposer in Python, and
  the normal test suite covers them: sharps and flats, minor keys, capo
  shapes and Nashville numbers.
- Every key change is one small request that returns the re-rendered
  sheet. That is fine at this project's scale: one church, a handful of
  users.
- The converter turns a chords-over-words chart into ChordPro, and the
  person sees the result before saving ("Convert"). The server checks every
  saved text: one that isn't valid ChordPro is refused with a message naming
  the line, so a broken conversion can't be saved.
- Hard to reverse: once the views, templates and tests are built around
  server rendering, moving transposition into the browser would mean
  rewriting all three.
