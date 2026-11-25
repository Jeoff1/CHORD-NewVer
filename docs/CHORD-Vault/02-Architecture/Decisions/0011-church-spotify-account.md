---
status: accepted
---

# An optional Church Spotify Account holds the Lineup Playlists

A church may connect one Spotify account of its own, in church settings
(the Spotify tab), as the **Church Spotify Account**. While it is
connected, every Lineup Playlist is made and updated there, as a **public**
playlist, whoever confirms the lineup or presses "Save to Spotify", and
everyone who can see the confirmed lineup, team members included, gets an
"Open the playlist" link. While it isn't, each playlist goes privately to
the account of the person who saves it, as before. Approved by the project
owner on 2026-11-22, after Phase 7 part B ([[Design-Decisions]], Phase 7).

It follows [[0001-configure-behavior-not-identity]]: whether a church keeps
its playlists on one shared account is church practice, so it is an
optional setting, and the step disappears when unused.

## Considered Options

- **Always the confirmer's own account** (part B as first built). The
  playlist is private, so the team can't open it, and it scatters across
  whoever confirmed each week. Kept only for churches without a church
  account.
- **Always the worship leader's account**, as first written in the
  workflow spec. Ties the playlist to a role and to one person's account,
  and fails when the pastor confirms. Rejected.
- **Using the church account for playback too.** Playback in the browser
  needs the listener's own Premium account and token, and sharing one
  account's token with every browser would expose it. Rejected: the church
  account holds only the playlist scopes.

## Consequences

- Only people who may change church settings (`church.change_churchprofile`,
  the Administrator by default) connect or disconnect it. It asks only for
  `playlist-modify-public` and `playlist-modify-private`, and doesn't need
  Premium. In Spotify's Development Mode it takes one of the app's User
  Management slots.
- Its tokens are stored encrypted like personal ones (Fernet,
  `SPOTIFY_TOKEN_KEY`) and are never shown or logged; the audit trail
  records only connected or not connected.
- With the church account set but unusable (refused, revoked or a 429),
  the lineup still confirms and "Save to Spotify" shows for people who may
  save. A revoked one is removed, and an administrator connects it again.
- Each service's lineup keeps its own playlist ([[0010-store-own-playlist-id]]);
  saving again updates only that lineup's playlist. Once the church account
  is connected, a lineup whose playlist is still on a personal account is
  offered "Save to Spotify" again, which makes its playlist on the church
  account.

## Update (2026-11-25): one per church

Since [[0014-church-platform]], each church has at most one Church Spotify
Account. Every account, across all churches, takes one of the Spotify
app's five Development Mode slots.
