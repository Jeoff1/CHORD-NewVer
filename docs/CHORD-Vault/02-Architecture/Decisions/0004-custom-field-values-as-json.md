---
status: accepted
---

# Custom Field values stored as JSON on the record

Churches keep different information about people and requests (baptism
date, shirt size, a signed consent form), so they define **Custom Fields**.
Each definition is a row (for example `members.MemberField`), and the values
are stored in a `custom_data` JSONField on the record itself, keyed by the
field's `key`. The key is made from the label when the field is created and
never changes, so renaming a field keeps its data. One shared
implementation (`apps/core/custom_fields.py`) serves Members now and
Services and Records later.

## Considered Options

- **A value table** (one row per record per field): it can be queried and
  indexed field by field, but every read and save needs joins, and each
  Module would need its own value table.
- **Real database columns added per church**: it would need a schema
  change each time a church adds a field.

## Consequences

- Filtering or sorting by a Custom Field means a JSON lookup
  (`custom_data__key`). That's fine at a single church's scale, but it
  isn't indexed.
- Switching a field off hides it but keeps its values. A choice removed
  from a list stays selectable on records that already use it.
- Values of private fields are left out of forms, detail pages and exports
  for users without the Module's private-details permission.
- Files are stored in private storage, and the JSON holds only their
  storage name.
