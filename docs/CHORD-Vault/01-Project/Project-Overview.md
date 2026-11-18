# Project Overview

## Goal

A worship planning system: the person who gives the message posts the
service's theme, the system suggests songs whose lyrics fit it, the
worship leader shapes the lineup, and the team opens one page per song
with the track, the chords and the key. Light church management sits
around that: the service schedule, a member directory, team rosters,
announcements and song history. The full description is the
[[Concept-Brief]].

## Key constraints

- **Generic.** The system never asks for the church's denomination
  (adviser requirement). Churches differ in practice, and those differences
  are settings each church edits, never denomination-specific features. See
  [[0001-configure-behavior-not-identity]].
- **Songs come from Spotify, searched per theme** (adviser request).
  Spotify data is never model input: the models read only lyrics from
  LRCLIB, the church's theme text and the church's own tags.
- **Small scale.** One church per installation and five users or fewer,
  which is also what Spotify's Development Mode allows.
- **Lyrics and chord sheets are copyrighted.** They stay private to the
  installation's users.

## Scope

In: worship services and themes, song suggestions, lineups and their
confirmation, the song pool, chord sheets and keys, Spotify playback,
teams and availability, announcements, song usage and headcounts, and the
member directory.

Out: giving and finance, church records and certificates, requested
services such as weddings, ministries, events, leadership appointment and
ordination, SMS messaging, check-in and follow-up, and per-person
attendance ([[0005-worship-planning-scope]]).

## Relationship to the first CHORD

This is a second option alongside the original CHORD project
(`../CHORD`). The original was built around Tradition presets (Roman
Catholic, Alliance, Iglesia Ni Cristo), which require choosing a
denomination. This version replaces those with per-church settings. The two
projects use separate databases and share no data.
