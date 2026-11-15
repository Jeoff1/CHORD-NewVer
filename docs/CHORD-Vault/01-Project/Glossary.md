# CHORD (new version)

A church administration system usable by any Christian church. Churches
configure what they do; the system never asks what denomination they are.

## Language

### The church and its configuration

**Church Profile**:
The single record describing this installation's church: its name, enabled
Modules and Labels.
_Avoid_: tenant, organization

**Module**:
A feature area (Members, Giving, Events, Services, Records, Worship,
Ministries) that ships in every installation and that the church switches on
or off.
_Avoid_: plugin, add-on

**Label**:
The church's own word for a common concept, such as "Priest", "Pastor" or
"Minister" for the person who officiates.
_Avoid_: terminology preset

**Role**:
A named set of permissions the church gives to users, such as Finance or
Records Keeper. The church edits roles; the Administrator role always has
full access.
_Avoid_: user type, position

**Audit Trail**:
The permanent record of who changed what, and when. Entries are never
edited or removed.
_Avoid_: history, log (alone)

**Church-edited List**:
A short list a church defines for itself, such as Membership Statuses or
Household Roles. Entries are switched off rather than deleted.
_Avoid_: lookup table, dropdown values

**Starter Catalog**:
Neutral sample Service Types the church may copy and then edit.
_Avoid_: preset, template, tradition

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

### Services

**Service Type**:
A service the church offers, defined by the church, such as a wedding, burial,
private Mass, child dedication or house blessing.
_Avoid_: sacrament (not every church calls these sacraments), service template

**Service Request**:
One request for a Service Type, going through that Service Type's steps from
request to completion.
_Avoid_: booking, reservation, appointment

**Fee Mode**:
How a Service Type is paid for: no fee, a fixed fee, an optional donation, or
an amount set per request.
_Avoid_: price, stipend (a stipend is one church's word for a fixed fee)

**Requirement**:
Something the requester must provide or complete before a Service Request can
proceed, such as a baptismal certificate or a seminar.
_Avoid_: prerequisite, document
