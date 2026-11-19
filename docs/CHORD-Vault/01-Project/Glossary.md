# CHORD (new version)

A worship planning system usable by any Christian church. Churches
configure what they do; the system never asks what denomination they are.

## Language

### The church and its configuration

**Church Profile**:
The single record describing this installation's church: its name, enabled
Modules and Labels.
_Avoid_: tenant, organization

**Module**:
A feature area (Members, Worship, Teams, Announcements) that ships in every
installation and that the church switches on or off. A Module can need
another: Teams counts as off while Worship is off.
_Avoid_: plugin, add-on

**Label**:
The church's own word for a common concept, such as "Sermon", "Homily" or
"Message" for the talk given at a service.
_Avoid_: terminology preset

**Role**:
A named set of permissions the church gives to users, such as Worship
Leader or Team Member. The church edits roles; the Administrator role
always has full access.
_Avoid_: user type, position

**Audit Trail**:
The permanent record of who changed what, and when. Entries are never
edited or removed.
_Avoid_: history, log (alone)

**Church-edited List**:
A short list a church defines for itself, such as Membership Statuses,
Series or Theme Tags. Entries are switched off rather than deleted.
_Avoid_: lookup table, dropdown values

**Denomination**:
A church's religious body. CHORD never records or uses it; see
[[0001-configure-behavior-not-identity]].
_Avoid_: Tradition, religion

### People

**Member**:
A person in the church's directory, whatever their Membership Status. A
visitor also has a Member record. Churches may rename it with the "member"
Label.
_Avoid_: contact, person record, parishioner (that's one church's Label)

**Membership Status**:
The church-edited state of a Member, such as Member, Visitor or Moved Away.
Some statuses count as active.
_Avoid_: member type, category

**Household**:
Members who live together, such as a family. Each person in it can have a
Household Role.
_Avoid_: family (not every household is a family)

**Household Role**:
A person's church-edited place in a Household, such as Head, Spouse or
Child.
_Avoid_: relationship type (the code's model name)

**Custom Field**:
A field the church adds to a kind of record, such as "Baptism date" on
every Member. It can be required, and private.
_Avoid_: extra field, user-defined field

**Archive**:
To take a record out of everyday lists without deleting it. Archiving can
be undone.
_Avoid_: delete, remove

### Worship planning

**Worship Service**:
One gathering for worship on one date. Churches may rename it with the
"worship service" Label (Mass, Service, Gathering). The
[[Concept-Brief]] calls it a service.
_Avoid_: event, service (alone, in code and notes)

**Service Template**:
A kind of Worship Service the church holds, such as its main weekly
service or a youth night, with its Song Slots and an optional usual day
and time.
_Avoid_: service type, event type

**Song Slot**:
A place in a Service Template where a song is sung, in order, such as
Opening or Response, with the Feel that suits it.
_Avoid_: position, segment

**Feel**:
How a song moves: upbeat, mid-tempo or slow. The system guesses it from
the lyrics, leaves it unset when it isn't sure, and a person corrects it.
Song Slots prefer songs of their feel but don't require them.
_Avoid_: tempo, energy (Spotify no longer gives either)

**Theme**:
What a Worship Service's message is about: a title, a main scripture and
notes. Song suggestions start from it.
_Avoid_: topic, sermon (the sermon is the talk; the Theme describes it)

**Series**:
A church-edited group of Worship Services whose Themes belong together.
Shown with the "sermon" Label, as in "Sermon series".
_Avoid_: campaign, season (a season is a time of year)

**Song Pool**:
Every song the system has checked, with its lyrics and analysis. It grows
from Spotify with each Theme; there is no typing songs in by hand.
_Avoid_: song database, catalogue

**Song**:
One track in the Song Pool: what Spotify says it is, its lyrics from
LRCLIB, its Worship Check, Theme Tags, Feel, and whether the team knows
it.
_Avoid_: track (Spotify's word for the recording)

**Version**:
One of several Songs in the pool that are the same song: covers and live
recordings, found by alike lyrics and titles. Suggestions show one version
of each song; the pool keeps them all.
_Avoid_: duplicate, cover (alone)

**Worship Check**:
Whether a Song reads as a Christian worship song: Not checked, Worship
song, or Not a worship song. The church's rules decide it from the
Worship Score and the Pass Mark; a person can correct it. Only worship
songs are suggested.
_Avoid_: filter, classification

**Pass Mark**:
The Worship Score a Song needs to pass the Worship Check: a church
setting, 0.5 unless the church changes it. With the church's optional
rule, artists not on the Trusted Artists list need a stricter mark or a
person's review.
_Avoid_: threshold (in UI text), cut-off

**Worship Check Settings**:
The church's one set of Worship Check rules: the Pass Mark and the rule
for artists not on the Trusted Artists list. They apply after the model;
the artist name never reaches it.
_Avoid_: classifier settings

**Model's Worship Score**:
How strongly a Song's lyrics read as worship, from the ML model and the
lyrics alone (`worship_model_score`). Anything model-related, such as
training, uses this score.
_Avoid_: raw score (in UI text), confidence

**Worship Score**:
The Model's Worship Score plus the Trusted Artist bonus, if the Song's
artist is a Trusted Artist. The Worship Check uses it; training never does.
_Avoid_: adjusted score (in UI text)

**Theme Tag**:
A worship theme a Song can be about, such as Grace or Hope, from a
church-edited list. The analysis suggests up to four per Song.
_Avoid_: category, topic, genre (a genre is Spotify's)

**Trusted Artist**:
An artist on the church's list whose Songs pass the Worship Check more
easily: a bonus added to the Worship Score by a church rule after the
model runs. The artist name never reaches the model. The list starts empty.
_Avoid_: approved artist, whitelist

**Reviewed**:
A Song whose Worship Check, Theme Tags or Feel a person has saved. Later
analysis keeps those and renews only the scores.
_Avoid_: verified, approved

**Lineup**:
The songs chosen for a Worship Service, in order. Churches may rename it
with the "lineup" Label (Set List, Song List). A Lineup is a draft or
confirmed; the team sees it only once it is confirmed.
_Avoid_: setlist, worship plan, playlist (a playlist is on Spotify)

**Final Say**:
The permission `worship.finalize_lineup`, held by the Pastoral Staff role
by default (and by the Administrator). Its holders, called "the pastor" in
the rules and named in the app by the church's "pastor" Label, can put on
the Pastor's Lock, reopen a Lineup and send it back. See
[[0008-final-say-permission]].
_Avoid_: pastor override, veto

**Pastor's Lock**:
What stops the worship leader from changing a Lineup, from the moment a
holder of the Final Say confirms it or edits it after it was confirmed,
until a holder reopens it. Reopening makes the Lineup a draft again.
_Avoid_: lock (alone; a lock on a song keeps it in place when the Lineup is
regenerated), freeze

**Send Back**:
Returning a Lineup to draft with a note for the worship leader. Only
holders of the Final Say can do it. It is not a state of its own: sending
back a confirmed Lineup reopens it.
_Avoid_: reject, decline

### Song suggestions

**Search Run**:
One search for a Worship Service's songs, from its Theme to ranked
Suggestions: its progress, what it searched, and what it found.
_Avoid_: job, task, search (alone)

**Suggestion**:
A Song a Search Run ranked for a Worship Service, with its score and the
reasons it was picked. Some are placed in the Song Slots; the rest are
choices for swapping. Suggestions are not a Lineup: team members never
see them.
_Avoid_: recommendation (Spotify's word), pick

**Search Worker**:
The one background process (`manage.py run_worker`) that carries out
Search Runs and fetches and analyses songs between them.
_Avoid_: job queue, Celery, background task

**Season**:
A church-edited time of the year, such as a time of preparation before a
festival, with the Theme Tags that suit it. Songs with those tags rank
higher for Worship Services in it. None are defined at first.
_Avoid_: liturgical season, church year (not every church keeps one)

**Suggestion Settings**:
The church's one set of choices for finding and ranking songs: search
genres, phrases per Theme, pages per phrase, market, the ranking weights,
the repeat window and how many ranked songs a run keeps.
_Avoid_: preferences, configuration

**Spotify Limit**:
A 429 answer from Spotify, kept with its reason and Retry-After. While one
is in force, CHORD doesn't call Spotify. A quota lockout, or a wait over an
hour, **pauses** Spotify: suggestions then rank the Song Pool instead.
_Avoid_: ban, block (alone)
