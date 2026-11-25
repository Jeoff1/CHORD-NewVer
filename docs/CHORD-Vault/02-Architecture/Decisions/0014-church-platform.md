---
status: accepted
---

# One installation serves many churches

CHORD was built for one church per installation. From Phase 9B it is a
**Church Platform**: one installation holds many churches, each with its
own data, roles, settings and Modules, and people can belong to more than
one church. Churches register themselves, and each has a public Church
Homepage. Decided by the project owner on 2026-11-25 (the "Church
Platform" brief, Option B, presentation version); the full design is
[[Phase-9B-Plan]].

The core rule still holds ([[0001-configure-behavior-not-identity]]): a
church registers with its name only, never its denomination, and every
difference between churches stays a setting the church edits.

## How it works

- **Church.** The model keeps its name `ChurchProfile` (no longer a single
  row). It gains a `slug`, `about`, `show_in_directory` and
  `show_upcoming_services`.
- **Membership.** A User is global. A **Membership** links a user to a
  church and holds their roles there. A user has at most one Membership per
  church, and may have none.
- **Roles per church.** `Role` gets a `church`; its shown name is `title`,
  unique per church. Django's `Group.name` stays unique across the
  installation, so it holds a hidden internal name. Each new church gets
  its own copy of the default roles.
- **Permissions per church.** `ChurchRoleBackend` replaces `ModelBackend`:
  a user's permissions are those of their roles in the **Current Church**
  (chosen in the session, checked against their memberships). Every
  existing `has_perm`, `PermissionRequiredMixin` and `perms.*` check keeps
  working, now per church. `user.groups` and permissions granted straight
  to a user are ignored. Code without a request asks
  `users_with_perm(church, perm)`.
- **Scoping.** Root models get a `church` foreign key; their children are
  scoped through the parent. Every scoped query goes through
  `for_church(church)`, a record from another church gives 404, and the
  church on a new record always comes from the request, never a form.
- **URLs.** Staff pages keep their URLs and act on the Current Church. New
  public pages live under `/churches/`.

## Owner's answers (2026-11-25)

1. **LRCLIB lyrics are shared as a cache.** Each church has its own Song
   rows, but when one church adds a track whose lyrics another church
   already fetched, CHORD copies them instead of asking LRCLIB again.
   Lyrics are never shown across churches; analysis, tags and chord
   sheets stay per church.
2. **Requests from outside a church** are a church setting, "Accept
   requests from people outside the church", on by default. Only Occasion
   Types the church marks "offered publicly" can be requested from its
   homepage.
3. **Superusers** (Django admin accounts) may switch into any church and
   act as its administrator, for support. This is Django's own behaviour:
   an active superuser holds every permission.
4. **AGENTS.md** records that Phase 9B comes before the rest of Phase 9A.

## Considered Options

- **A church slug in every staff URL** (`/c/<slug>/worship/...`). Two tabs
  could work in two churches, but every `{% url %}` tag and test would
  change a week before the final presentation. Rejected for now; the
  Current Church lives in the session.
- **A database or schema per church.** Strongest isolation, but needs
  per-church migrations and connection routing. Rejected as too heavy for
  this project's scale.

## Consequences

- Hard to reverse: once several churches hold data, splitting them back
  into separate installations needs an export per church.
- The Current Church is per session, so two tabs share it. A link to
  another church's record gives 404 until the person switches church.
- **Spotify's Development Mode allows 5 users per app across the whole
  platform**, not per church. That is accepted for the presentation and
  recorded as the platform's main scaling limit.
- Some things stay global on purpose: `User`, a person's own
  `SpotifyConnection`, the shared Spotify rate-limit block (`SpotifyLimit`,
  which must cover every church), and `SignInEvent`.
- The **Members and Teams Modules are locked** for every church except the
  first (migrated) one, through the church setting
  `members_teams_unlocked`, until they are scoped. They show as "Not
  available yet".
- Replaces "one church per installation and five users or fewer"
  ([[Project-Overview]], [[Concept-Brief]]); updates
  [[0003-editable-roles]] (roles per church, membership-based backend) and
  [[0011-church-spotify-account]] (one per church). Occasion Requests from
  outside a church extend [[0013-occasions-module]].
