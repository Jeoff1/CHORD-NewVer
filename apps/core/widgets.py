"""Shared form widgets and fields."""

import re

from django import forms
from django.core.exceptions import ValidationError

BOTH = "Enter both a date and a time."
HAS_TIME = re.compile(r"[ T]\d{1,2}:\d{2}")


class MomentInput(forms.SplitDateTimeWidget):
    """A date and a time, side by side, each with its icon (the owner, 28 Nov
    2026): the browser's own date and time pickers, opened by a click
    anywhere in the box (core/moment_input.js).

    It posts ``<name>_0`` (the date) and ``<name>_1`` (the time) and gives
    the field one "YYYY-MM-DD HH:MM" value, so a ``DateTimeField`` reads it
    as before. A post with one combined ``<name>`` value (an older page, a
    script) still works.
    """

    template_name = "core/widgets/moment.html"

    def __init__(self, attrs=None):
        super().__init__(
            attrs=attrs,
            date_attrs={"type": "date"},
            time_attrs={"type": "time"},
            date_format="%Y-%m-%d",
            time_format="%H:%M",
        )

    def decompress(self, value):
        # A value sent back after an error is the combined text.
        if isinstance(value, str):
            date, _, time = value.strip().replace("T", " ").partition(" ")
            return [date or None, time[:5] or None]
        return super().decompress(value)

    def value_from_datadict(self, data, files, name):
        if name in data:
            return data.get(name)
        date, time = super().value_from_datadict(data, files, name)
        date, time = (date or "").strip(), (time or "").strip()
        return f"{date} {time}".strip()

    def value_omitted_from_data(self, data, files, name):
        return name not in data and super().value_omitted_from_data(data, files, name)


class MomentField(forms.DateTimeField):
    """A date and a time from ``MomentInput``. A date alone is refused,
    never read as midnight (Python reads "2031-03-02" as a date and time)."""

    widget = MomentInput
    default_error_messages = {"invalid": BOTH}

    def to_python(self, value):
        if isinstance(value, str) and value.strip() and not HAS_TIME.search(value):
            raise ValidationError(BOTH, code="invalid")
        return super().to_python(value)
