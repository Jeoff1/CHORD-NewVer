"""Member rules: audit fields, CSV import and CSV export.

Import and export use the same columns, so an exported file can be edited
and imported again. Import checks every row with ``MemberForm`` (the same
rules as the add-member page) and imports only rows without problems.
"""

import csv
import io
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.core.custom_fields import NO, YES, FieldType, parse_date

from .forms import MemberForm
from .models import Household, Member, MemberField, MembershipStatus, RelationshipType

MAX_IMPORT_ROWS = 5000

# (CSV column, Member attribute). Private columns are left out for users who
# can't see private details.
COLUMNS = [
    ("First name", "first_name"),
    ("Middle name", "middle_name"),
    ("Last name", "last_name"),
    ("Suffix", "suffix"),
    ("Sex", "sex"),
    ("Birth date", "birth_date"),
    ("Email", "email"),
    ("Phone", "phone"),
    ("Address", "address"),
    ("Status", "status"),
    ("Date joined", "joined_on"),
    ("Household", "household"),
    ("Role in household", "relationship"),
    ("Notes", "notes"),
]
SEX_WORDS = {"f": "female", "female": "female", "m": "male", "male": "male"}


# --- Audit -----------------------------------------------------------------


def member_audit_fields():
    fields = {
        "First name": "first_name",
        "Middle name": "middle_name",
        "Last name": "last_name",
        "Suffix": "suffix",
        "Sex": lambda m: m.get_sex_display(),
        "Birth date": "birth_date",
        "Email": "email",
        "Phone": "phone",
        "Address": "address",
        "Photo": "photo",
        "Status": "status",
        "Date joined": "joined_on",
        "Household": "household",
        "Role in household": "relationship",
        "Linked account": "user",
        "Notes": "notes",
        "Archived": lambda m: m.is_archived,
    }
    for definition in MemberField.objects.filter(is_active=True):
        fields[definition.label] = lambda m, d=definition: d.display(
            (m.custom_data or {}).get(d.key)
        )
    return fields


def set_archived(member, archived, actor):
    before = snapshot(member, member_audit_fields())
    member.archived_at = timezone.now() if archived else None
    member.save(update_fields=["archived_at", "updated_at"])
    record_change(
        actor,
        member,
        AuditEvent.Action.CHANGED,
        diff(before, snapshot(member, member_audit_fields())),
    )


# --- Columns -----------------------------------------------------------------


def columns(*, include_private):
    """``(header, getter)`` for every exported or imported column."""
    result = [
        (header, attribute)
        for header, attribute in COLUMNS
        if include_private or attribute not in Member.PRIVATE_FIELDS
    ]
    for definition in MemberField.objects.filter(is_active=True).exclude(
        field_type=FieldType.FILE
    ):
        if include_private or not definition.is_private:
            result.append((definition.label, definition))
    return result


def _cell(member, getter):
    if isinstance(getter, MemberField):
        return getter.display((member.custom_data or {}).get(getter.key))
    if getter == "sex":
        return member.get_sex_display()
    value = getattr(member, getter)
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


# --- Export ------------------------------------------------------------------


def export_csv(members, *, include_private):
    cols = columns(include_private=include_private)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([header for header, _ in cols])
    for member in members.select_related("status", "household", "relationship"):
        writer.writerow([_cell(member, getter) for _, getter in cols])
    return "﻿" + buffer.getvalue()  # BOM so Excel reads UTF-8


def template_csv(*, include_private):
    cols = columns(include_private=include_private)
    return "﻿" + ",".join(f'"{header}"' for header, _ in cols) + "\r\n"


# --- Import ------------------------------------------------------------------


class ImportFileError(Exception):
    """The file as a whole can't be read."""


def read_csv(uploaded_file):
    """Rows of the uploaded CSV as dicts keyed by its own headers."""
    raw = uploaded_file.read()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - cp1252 decodes almost anything
        raise ImportFileError("The file isn't a readable CSV file.")
    reader = csv.DictReader(io.StringIO(text))
    if not any((header or "").strip() for header in reader.fieldnames or []):
        raise ImportFileError("The file is empty.")
    rows = []
    for row in reader:
        if any((value or "").strip() for value in row.values()):
            rows.append({k.strip(): (v or "").strip() for k, v in row.items() if k})
        if len(rows) > MAX_IMPORT_ROWS:
            raise ImportFileError(
                f"The file has more than {MAX_IMPORT_ROWS} rows. Split it into "
                "smaller files."
            )
    if not rows:
        raise ImportFileError("The file has no rows to import.")
    return [header.strip() for header in reader.fieldnames if header], rows


@dataclass
class ImportRow:
    number: int  # line in the file, counting the header as line 1
    values: dict
    problems: list = field(default_factory=list)
    form: MemberForm | None = None
    household_name: str = ""
    relationship: RelationshipType | None = None

    @property
    def ok(self):
        return not self.problems

    @property
    def name(self):
        parts = [self.values.get("First name", ""), self.values.get("Last name", "")]
        return " ".join(part for part in parts if part) or "(no name)"


@dataclass
class ImportCheck:
    rows: list
    ignored_columns: list
    missing_columns: list

    @property
    def ready(self):
        return [row for row in self.rows if row.ok]

    @property
    def with_problems(self):
        return [row for row in self.rows if not row.ok]


def check_import(headers, raw_rows, *, include_private):
    """Validate every row; nothing is saved."""
    cols = columns(include_private=include_private)
    by_header = {header.lower(): (header, getter) for header, getter in cols}
    ignored = [h for h in headers if h.lower() not in by_header]
    present = {h.lower() for h in headers}
    missing = [
        header
        for header in ("First name", "Last name")
        if header.lower() not in present
    ]

    statuses = {s.name.lower(): s for s in MembershipStatus.objects.active()}
    relationships = {r.name.lower(): r for r in RelationshipType.objects.active()}
    default_status = MembershipStatus.default()
    seen = _existing_identities()

    rows = []
    for number, raw in enumerate(raw_rows, start=2):
        values = {}
        for header, value in raw.items():
            if header.lower() in by_header:
                values[by_header[header.lower()][0]] = value
        row = ImportRow(number=number, values=values)
        data = {}
        for header, getter in cols:
            text = values.get(header, "")
            try:
                if isinstance(getter, MemberField):
                    stored = getter.parse_text(text)
                    if stored is not None:
                        data[getter.form_name] = (
                            (YES if stored else NO)
                            if getter.field_type == FieldType.YES_NO
                            else stored
                        )
                elif getter == "sex" and text:
                    if text.lower() not in SEX_WORDS:
                        raise ValidationError("Sex: use Female or Male.")
                    data["sex"] = SEX_WORDS[text.lower()]
                elif getter in ("birth_date", "joined_on") and text:
                    label = "Birth date" if getter == "birth_date" else "Date joined"
                    data[getter] = parse_date(text, label).isoformat()
                elif getter == "status":
                    status = statuses.get(text.lower()) if text else default_status
                    if status is None:
                        raise ValidationError(f"Status: “{text}” isn't in the list.")
                    data["status"] = status.pk
                elif getter == "relationship" and text:
                    row.relationship = relationships.get(text.lower())
                    if row.relationship is None:
                        raise ValidationError(
                            f"Role in household: “{text}” isn't in the list."
                        )
                    if not values.get("Household"):
                        raise ValidationError(
                            "Role in household: give a household as well."
                        )
                elif getter == "household" and text:
                    row.household_name = text  # created on import if new
                elif text:
                    data[getter] = text
            except ValidationError as error:
                row.problems.extend(error.messages)

        form = MemberForm(data=data, can_view_private=include_private, for_import=True)
        if form.is_valid():
            row.form = form
        else:
            for name, errors in form.errors.items():
                label = form.fields[name].label if name in form.fields else ""
                for message in errors:
                    row.problems.append(f"{label}: {message}" if label else message)

        identity = _identity(values)
        if identity and identity in seen:
            row.problems.append(
                "Looks like a duplicate: someone with this name and birth date "
                "or email is already in the list or earlier in the file."
            )
        elif identity:
            seen.add(identity)
        row.problems = list(dict.fromkeys(row.problems))
        rows.append(row)
    return ImportCheck(rows=rows, ignored_columns=ignored, missing_columns=missing)


def _identity(values):
    first = values.get("First name", "").strip().lower()
    last = values.get("Last name", "").strip().lower()
    if not (first and last):
        return None
    birth = values.get("Birth date", "").strip()
    if birth:
        try:
            return (first, last, "born", parse_date(birth).isoformat())
        except ValidationError:
            return None
    email = values.get("Email", "").strip().lower()
    return (first, last, "email", email) if email else None


def _existing_identities():
    identities = set()
    for first, last, birth, email in Member.objects.values_list(
        "first_name", "last_name", "birth_date", "email"
    ):
        first, last = first.lower(), last.lower()
        if birth:
            identities.add((first, last, "born", birth.isoformat()))
        if email:
            identities.add((first, last, "email", email.lower()))
    return identities


@transaction.atomic
def import_members(check, actor):
    """Create a member for every row without problems. Returns the count."""
    households = {h.name.lower(): h for h in Household.objects.all()}
    fields = member_audit_fields()
    created = 0
    for row in check.ready:
        member = row.form.save(commit=False)
        if row.household_name:
            key = row.household_name.lower()
            if key not in households:
                household = Household.objects.create(name=row.household_name)
                households[key] = household
                record_change(
                    actor,
                    household,
                    AuditEvent.Action.CREATED,
                    {"Name": ["", household.name]},
                )
            member.household = households[key]
            member.relationship = row.relationship
        member.save()
        record_change(
            actor, member, AuditEvent.Action.CREATED, diff({}, snapshot(member, fields))
        )
        created += 1
    return created


def problems_csv(check):
    """The rows that weren't imported, with a Problems column to fix them."""
    headers = list(dict.fromkeys(h for row in check.rows for h in row.values))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Line", *headers, "Problems"])
    for row in check.with_problems:
        writer.writerow(
            [
                row.number,
                *(row.values.get(h, "") for h in headers),
                "; ".join(row.problems),
            ]
        )
    return "﻿" + buffer.getvalue()
