---
status: built
---

# Members

The church's people directory: everyone the church keeps a record of,
including visitors, with their households. App: `apps/members`. Module code
`members`; the Module's name follows the "member" Label (e.g.
"Parishioners").

## What exists

- **Member** (`models.py`):
  - name (first, middle, last, suffix), sex (optional), birth date, email,
    phone, address;
  - photo (private storage, 5 MB maximum);
  - Membership Status, date joined, household and household role;
  - linked user account (optional, one per account) and notes;
  - Custom Field values (`custom_data`);
  - public UUID in URLs.
  Members are **archived, never deleted**; the archive can be undone.
- **Membership Status**: a church-edited list, with a "counts as active"
  setting.
  - Defaults: Member, Regular Attendee, Visitor (active); Inactive, Moved
    Away, Deceased (not active).
  - New members get the first active status unless another is chosen.
- **Household** with **Household Roles** (a church-edited list; defaults
  Head, Spouse, Child, Other). A role can only be set together with a
  household.
- **Custom Fields** (`MemberField`): short text, long text, number, date,
  choice, yes/no or file. Each can be required and/or private
  ([[0004-custom-field-values-as-json]]).
- **Screens** (`/members/`):
  - **The list:**
    - search, the Current, Archived and All views, and a status filter;
    - add, edit, archive and restore;
    - a detail page showing the household and recent changes (the
      changes are visible to users who can see the audit log).
  - **Own record:** `/members/me/` shows the signed-in person's own
    record, including private details.
  - **Households:** their own list, detail page and edit page.
  - **Settings:** `/members/settings/…` holds Membership Statuses,
    Household Roles and Custom Fields, using the shared church-edited list
    pages.
- **CSV import** (`/members/import/`):
  1. Upload a CSV file. Excel's UTF-8 and Windows encodings both work, up
     to 5,000 rows.
  2. The preview checks every row with the same rules as the add form and
     saves nothing. Problems reported include bad dates, unknown statuses,
     missing names, a household role without a household, and duplicates.
     A row counts as a duplicate when the name and birth date (or name and
     email) match an existing member or an earlier row.
  3. Confirm, and only the rows without problems are imported. Households
     that don't exist yet are created.
  - Rows with problems can be downloaded with a Problems column, fixed,
    and imported again. A blank template file is also available.
- **CSV export** (`/members/export/`) follows the current list filters and
  uses the same columns as the import, so an export can be imported again.
- **Create accounts** (`/members/accounts/`, Phase 9A, A4; rules in
  `accounts.py`): from the list's "Create accounts" button, for holders of
  both `members.view_member` and `accounts.add_user`. Tick current members
  without an account (filtered by name and status, first 200), choose a
  role (Church Member by default), and each gets an account linked to the
  record: username "first.last" (then "first.last2"), the record's email,
  and a 12-character Temporary Password they must change at first sign-in.
  The result page shows the passwords once, with a CSV download built into
  the page, and is never cached; passwords are never stored, logged or
  audited. Members who already have an account, or are archived, are
  skipped with the reason. Each member's row is locked while its account is
  made. The audit trail records the account created and the member's
  linked account.
- **Privacy:** only users with `members.view_private_details` see birth
  date, email, phone, address and private Custom Fields. This applies to
  lists, search, detail pages, forms, imports and exports. Editors without
  it can't see those fields, and saving their edits leaves them unchanged.
- **Files** (photos, Custom Field files) are served only by
  permission-checked views. Files other than photos download as
  attachments.
- Every change is in the audit trail, including Custom Field values,
  archiving and imports.
- Tests: `apps/members/tests/` (list, privacy, own record, archive, files,
  households, settings lists, import and export, batch accounts and the
  first sign-in).

## Permissions

| Permission                       | Allows                                          |
| -------------------------------- | ----------------------------------------------- |
| `members.view_member`            | Seeing the list and records (not private details) |
| `members.view_private_details`   | Birth dates, contacts and private Custom Fields |
| `members.add_member` / `change_member` | Adding, editing, archiving               |
| `members.import_member` / `export_member` | CSV import / export                    |
| `members.*_household`            | Households                                      |
| `members.*_membershipstatus`, `*_relationshiptype`, `*_memberfield` | The settings lists |

Default roles ([[Accounts]]):
- **Office Staff** gets the everyday permissions, including private
  details, import and export, and can view the settings lists.
- **Pastoral Staff** and **Worship Leader** can view members.

### The Members list (Phase 9A, A7 part 3)

Add member is the one primary button; Import from CSV, Export CSV, Create
accounts and Members settings are under **More**, each behind its own
permission. Tabs **People** and **Households**. One filter row: a
labelled search, Status, **Show archived** (the `show` filter) and Filter.
Columns: Name, Status, Household, Phone (with `members.view_private_details`
only) and **Can sign in** (whether the person has an account). The Email
column was dropped. The settings lists are in the Settings hub's Members
category. Tests: `apps/members/tests/test_members_screen.py`.

## Church settings this module depends on

- Membership Statuses
- Household Roles
- Custom Fields
- The "member" Label

## Open questions

- None for now. The [[Concept-Brief]] asks only for a basic directory;
  this Module stays as built, plus what Phase 9A adds (batch accounts;
  member reports next). Team members are user accounts, and a Member record
  can be linked to an account.
- The CSV **export** (older than Phase 9A) doesn't yet guard against cells
  a spreadsheet would run as a formula; the batch accounts CSV does. For
  Phase 10's security review.
