"""Custom fields: extra fields a church defines for its records.

A Module subclasses ``CustomFieldDefinition`` for the records it extends (for
example ``members.MemberField``), keeps the values in a ``custom_data``
JSONField on the record, and uses ``CustomFieldsFormMixin`` on the record's
form. Values are stored by the field's ``key``, which never changes after
the field is created, so renaming a field keeps its data. See decision 0004.
"""

import datetime
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.text import slugify

from .models import TimeStampedModel
from .storage import StoredFile, private_storage, random_upload_name

MAX_FILE_BYTES = 10 * 1024 * 1024
FILE_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "doc", "docx", "xls", "xlsx", "txt"]
YES, NO = "yes", "no"


def validate_file_size(file):
    if file.size > MAX_FILE_BYTES:
        raise ValidationError("Files must be 10 MB or smaller.")


class FieldType(models.TextChoices):
    TEXT = "text", "Short text"
    LONG_TEXT = "long_text", "Long text"
    NUMBER = "number", "Number"
    DATE = "date", "Date"
    CHOICE = "choice", "Choice from a list"
    YES_NO = "yes_no", "Yes or no"
    FILE = "file", "File"


class CustomFieldDefinition(TimeStampedModel):
    label = models.CharField(max_length=100)
    key = models.SlugField(max_length=60, editable=False)
    field_type = models.CharField(
        "Type", max_length=16, choices=FieldType.choices, default=FieldType.TEXT
    )
    choices = models.TextField(
        blank=True, help_text="For “Choice from a list”: one choice per line."
    )
    help_text = models.CharField(
        max_length=250, blank=True, help_text="Shown under the field on forms."
    )
    required = models.BooleanField(default=False)
    is_private = models.BooleanField(
        "Private",
        default=False,
        help_text="Only people allowed to see private details can see or edit it.",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0, help_text="Lower numbers come first."
    )
    is_active = models.BooleanField(
        "Active",
        default=True,
        help_text="Inactive fields are hidden; values already entered are kept.",
    )

    class Meta:
        abstract = True
        ordering = ["sort_order", "label"]
        default_permissions = ("add", "change", "view")

    def __str__(self):
        return self.label

    def sibling_definitions(self):
        """Definitions whose keys must differ from this one's."""
        return type(self).objects.all()

    def clean(self):
        super().clean()
        if self.field_type == FieldType.CHOICE and not self.choice_list():
            raise ValidationError({"choices": "Add at least one choice."})

    def save(self, *args, **kwargs):
        if not self.key:
            base = slugify(self.label).replace("-", "_")[:50] or "field"
            taken = set(self.sibling_definitions().values_list("key", flat=True))
            key, n = base, 2
            while key in taken:
                key, n = f"{base}_{n}", n + 1
            self.key = key
        super().save(*args, **kwargs)

    # --- values ------------------------------------------------------------

    @property
    def form_name(self):
        return f"cf_{self.key}"

    def choice_list(self):
        return [line.strip() for line in self.choices.splitlines() if line.strip()]

    def form_field(self, stored=None):
        """A form field for this definition, showing the stored value."""
        common = {
            "label": self.label,
            "required": self.required,
            "help_text": self.help_text,
        }
        kind = self.field_type
        if kind == FieldType.LONG_TEXT:
            field = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), **common)
        elif kind == FieldType.NUMBER:
            field = forms.DecimalField(max_digits=18, decimal_places=4, **common)
        elif kind == FieldType.DATE:
            field = forms.DateField(
                widget=forms.DateInput(attrs={"type": "date"}), **common
            )
        elif kind == FieldType.CHOICE:
            options = self.choice_list()
            if stored and stored not in options:
                options.append(stored)  # keep a value whose choice was removed
            field = forms.ChoiceField(
                choices=[("", "—")] + [(o, o) for o in options], **common
            )
        elif kind == FieldType.YES_NO:
            field = forms.ChoiceField(
                choices=[("", "—"), (YES, "Yes"), (NO, "No")], **common
            )
        elif kind == FieldType.FILE:
            field = forms.FileField(
                widget=forms.ClearableFileInput,
                validators=[
                    FileExtensionValidator(FILE_EXTENSIONS),
                    validate_file_size,
                ],
                **common,
            )
        else:
            field = forms.CharField(max_length=250, **common)
        field.initial = self.to_initial(stored)
        return field

    def to_initial(self, stored):
        if stored in (None, ""):
            return None
        if self.field_type == FieldType.DATE:
            return datetime.date.fromisoformat(stored)
        if self.field_type == FieldType.NUMBER:
            return Decimal(stored)
        if self.field_type == FieldType.YES_NO:
            return YES if stored else NO
        if self.field_type == FieldType.FILE:
            return StoredFile(stored)
        return stored

    def to_storage(self, value, current=None, upload_folder="custom_fields"):
        """The JSON value to store for a cleaned form value."""
        kind = self.field_type
        if kind == FieldType.FILE:
            if value is False:  # "clear" ticked
                _delete_file(current)
                return None
            if value is None or isinstance(value, StoredFile):
                return current
            _delete_file(current)
            return private_storage.save(
                random_upload_name(upload_folder, value.name), value
            )
        if value in (None, ""):
            return None
        if kind == FieldType.DATE:
            return value.isoformat()
        if kind == FieldType.NUMBER:
            return format(value.normalize(), "f")
        if kind == FieldType.YES_NO:
            return value == YES
        return value

    def parse_text(self, text):
        """The JSON value for plain text (from a CSV import); raises
        ValidationError when the text doesn't fit the type."""
        text = (text or "").strip()
        if not text:
            if self.required:
                raise ValidationError(f"{self.label} is required.")
            return None
        kind = self.field_type
        if kind == FieldType.NUMBER:
            try:
                return format(Decimal(text.replace(",", "")).normalize(), "f")
            except InvalidOperation:
                raise ValidationError(f"{self.label}: “{text}” isn't a number.")
        if kind == FieldType.DATE:
            return parse_date(text, self.label).isoformat()
        if kind == FieldType.YES_NO:
            lowered = text.lower()
            if lowered in {"yes", "y", "true", "1"}:
                return True
            if lowered in {"no", "n", "false", "0"}:
                return False
            raise ValidationError(f"{self.label}: use Yes or No.")
        if kind == FieldType.CHOICE:
            for option in self.choice_list():
                if option.lower() == text.lower():
                    return option
            raise ValidationError(f"{self.label}: “{text}” isn't one of the choices.")
        if kind == FieldType.FILE:
            raise ValidationError(f"{self.label}: files can't be imported.")
        return text

    def display(self, stored):
        """The stored value as text for detail pages, exports and the audit
        trail."""
        if stored in (None, ""):
            return ""
        if self.field_type == FieldType.YES_NO:
            return "Yes" if stored else "No"
        if self.field_type == FieldType.FILE:
            return stored.rsplit("/", 1)[-1]
        if self.field_type == FieldType.DATE:
            return format_date(datetime.date.fromisoformat(stored))
        return str(stored)


DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y")


def format_date(value):
    """Mar 5, 2024 (the same style as the templates' dates)."""
    return f"{value:%b} {value.day}, {value.year}"


def parse_date(text, label="Date"):
    """Read a date written as 2024-03-31, 03/31/2024 or March 31, 2024."""
    for fmt in DATE_FORMATS:
        try:
            return datetime.datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    raise ValidationError(
        f"{label}: “{text}” isn't a date. Use YYYY-MM-DD or MM/DD/YYYY."
    )


def _delete_file(name):
    if name and private_storage.exists(name):
        private_storage.delete(name)


@dataclass(frozen=True)
class CustomValue:
    definition: CustomFieldDefinition
    stored: object

    @property
    def label(self):
        return self.definition.label

    @property
    def text(self):
        return self.definition.display(self.stored)

    @property
    def is_file(self):
        return self.definition.field_type == FieldType.FILE and bool(self.stored)


def custom_values(definitions, data, *, include_private):
    """Active fields' values for a detail page, in display order."""
    data = data or {}
    return [
        CustomValue(d, data.get(d.key))
        for d in definitions
        if d.is_active and (include_private or not d.is_private)
    ]


class CustomFieldsFormMixin:
    """Adds a ModelForm's church-defined fields and saves their values into
    ``instance.custom_data``.

    Call ``add_custom_fields(definitions, include_private=...)`` in
    ``__init__`` and ``save_custom_fields(upload_folder)`` before saving the
    instance. Private fields left out of the form keep their values.
    """

    def add_custom_fields(self, definitions, *, include_private=True):
        data = self.instance.custom_data or {}
        self.custom_definitions = [
            d
            for d in definitions
            if d.is_active and (include_private or not d.is_private)
        ]
        for definition in self.custom_definitions:
            stored = data.get(definition.key)
            field = definition.form_field(stored)
            if definition.field_type == FieldType.FILE and stored:
                field.initial = StoredFile(stored, self.custom_file_url(definition))
            self.fields[definition.form_name] = field

    def custom_file_url(self, definition):
        """Where the current file of ``definition`` can be opened."""
        return "#"

    def custom_fields(self):
        return [self[d.form_name] for d in self.custom_definitions]

    def save_custom_fields(self, upload_folder):
        data = dict(self.instance.custom_data or {})
        for definition in self.custom_definitions:
            data[definition.key] = definition.to_storage(
                self.cleaned_data.get(definition.form_name),
                current=data.get(definition.key),
                upload_folder=upload_folder,
            )
        self.instance.custom_data = data
