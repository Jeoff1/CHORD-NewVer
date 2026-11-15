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

**Starter Catalog**:
Neutral sample Service Types the church may copy and then edit.
_Avoid_: preset, template, tradition

**Denomination**:
A church's religious body. CHORD never records or uses it; see
[[0001-configure-behavior-not-identity]].
_Avoid_: Tradition, religion

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
