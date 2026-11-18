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
the lyrics and a person corrects it.
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

**Worship Check**:
Whether a Song's lyrics read as a Christian worship song: Not checked,
Worship song, or Not a worship song. The analysis decides it from the
lyrics; a person can correct it. Only worship songs are suggested.
_Avoid_: filter, classification

**Theme Tag**:
A worship theme a Song can be about, such as Grace or Hope, from a
church-edited list. The analysis suggests up to four per Song.
_Avoid_: category, topic, genre (a genre is Spotify's)

**Trusted Artist**:
An artist on the church's list whose Songs pass the Worship Check more
easily. The list starts empty.
_Avoid_: approved artist, whitelist

**Reviewed**:
A Song whose Worship Check, Theme Tags or Feel a person has saved. Later
analysis keeps those and renews only the scores.
_Avoid_: verified, approved

**Lineup**:
The songs chosen for a Worship Service, in order. Churches may rename it
with the "lineup" Label (Set List, Song List). The team sees it only once
it is confirmed.
_Avoid_: setlist, worship plan, playlist (a playlist is on Spotify)
