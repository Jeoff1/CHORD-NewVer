"""Forms for the Church Profile sections: details, Modules and the public
homepage. Labels keep CHORD's default words: churches no longer edit them
(the owner, 28 Nov 2026).

All of them take ``instance`` (the Church Profile) and have ``save()``, so the
settings pages and the setup wizard share one view.
"""

from dataclasses import replace

from django import forms
from django.core.validators import MaxLengthValidator

from .context_processors import module_entries
from .images import BannerFieldMixin
from .models import TIME_ZONE_CHOICES, ChurchProfile
from .modules import (
    MODULE_CHOICES,
    MODULES,
    MODULES_BY_CODE,
    is_available,
    is_retired,
)

ABOUT_MAX_LENGTH = 2000
TIME_ZONES = {zone for zone, _ in TIME_ZONE_CHOICES}


class ChurchDetailsForm(forms.ModelForm):
    class Meta:
        model = ChurchProfile
        fields = [
            "name",
            "address",
            "phone",
            "email",
            "logo",
        ]
        labels = {"name": "Church name"}
        help_texts = {
            "logo": "512 × 512 px recommended (1:1). PNG, JPEG, GIF or WebP, 2 MB at most."
        }
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}


class ChurchHomepageForm(BannerFieldMixin, forms.ModelForm):
    """What the church shows publicly (Phase 9B). Nothing shows until the
    church switches it on, except what a new church chose at registration.
    The banner (27 Nov 2026) is changed or removed here."""

    class Meta:
        model = ChurchProfile
        fields = [
            "show_in_directory",
            "about",
            "banner",
            "show_upcoming_services",
            "accept_outside_requests",
        ]
        labels = {"banner": "Church banner"}
        widgets = {
            "about": forms.Textarea(attrs={"rows": 5}),
            "banner": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["about"].max_length = ABOUT_MAX_LENGTH
        self.fields["about"].validators.append(MaxLengthValidator(ABOUT_MAX_LENGTH))

    def clean_about(self):
        # Plain text: stored as typed, shown escaped with its line breaks.
        return self.cleaned_data["about"].strip()


class ModulesForm(forms.Form):
    enabled = forms.MultipleChoiceField(
        choices=MODULE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Switched-on modules",
    )

    def __init__(self, *args, instance, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        # A Module the church may not use yet (Phase 9B, §5) can't be
        # switched on: it isn't a choice, so posting it is refused.
        self.available = {m.code for m in MODULES if is_available(m, instance)}
        self.fields["enabled"].choices = [
            (code, name) for code, name in MODULE_CHOICES if code in self.available
        ]
        self.fields["enabled"].initial = [
            m.code
            for m in MODULES
            if m.code in self.available and m.code not in instance.disabled_modules
        ]

    def rows(self):
        """One row per Module no setting retires, in the church's words: the
        entry, whether it is switched on, whether it may be switched on, and
        whether it sits under another Module (Teams, shown as the Praise
        Team, under Worship), right after that Module."""
        checked = set(self["enabled"].value() or [])
        everything_on = ChurchProfile(
            labels=self.instance.labels, members_teams_unlocked=True
        )
        entries = {
            e.code: e
            for e in module_entries(everything_on)
            if not is_retired(MODULES_BY_CODE[e.code])
        }
        team_word = self.instance.label_set.get("team")

        def row(code, nested=False):
            entry = entries[code]
            if nested:
                entry = replace(entry, name=team_word, requires=())
            return {
                "entry": entry,
                "checked": code in checked,
                "available": code in self.available,
                "nested": nested,
            }

        rows = []
        for code in entries:
            if MODULES_BY_CODE[code].parent:
                continue
            rows.append(row(code))
            rows += [
                row(child, nested=True)
                for child in entries
                if MODULES_BY_CODE[child].parent == code
            ]
        return rows

    def save(self):
        enabled = set(self.cleaned_data["enabled"])
        # A retired Module isn't on the page, so its saved choice is kept.
        kept_off = set(self.instance.disabled_modules)
        self.instance.disabled_modules = [
            code
            for code, module in MODULES_BY_CODE.items()
            if (code in kept_off if is_retired(module) else code not in enabled)
        ]
        self.instance.save(update_fields=["disabled_modules", "updated_at"])
        return self.instance


SECTIONS = {
    "details": ("Church details", ChurchDetailsForm),
    "modules": ("Modules", ModulesForm),
    "homepage": ("Public homepage", ChurchHomepageForm),
}
SECTION_ORDER = list(SECTIONS)


class ChurchRegistrationForm(BannerFieldMixin, forms.ModelForm):
    """Register a church (decisions 0001 and 0014): its name, which is all it
    needs, and, if the person likes, the details and public profile they
    could otherwise set later in the settings (owner, 27 Nov 2026). Never
    who the church is, only what it does (decision 0001)."""

    # Hidden: filled in from the person's device (owner, 27 Nov 2026), so the
    # church starts in the right time zone; changed later in Church details.
    time_zone = forms.CharField(required=False, widget=forms.HiddenInput)
    show_in_directory = forms.TypedChoiceField(
        label="Public visibility",
        choices=[("public", "Public"), ("private", "Not public")],
        coerce=lambda value: value == "public",
        empty_value=True,
        required=False,
        initial="public",
        widget=forms.RadioSelect,
    )

    class Meta:
        model = ChurchProfile
        fields = ["name", "address", "phone", "email", "logo", "banner", "about"]
        labels = {
            "name": "Church name",
            "address": "Church address",
            "phone": "Contact number",
            "email": "Church email address",
            "logo": "Church logo",
            "banner": "Church banner",
            "about": "Church description",
        }
        help_texts = {
            "name": "As people know it. You can change it later.",
            "logo": "512 × 512 px recommended (1:1). PNG, JPEG, GIF or WebP, 2 MB at most.",
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "about": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A new church's model default ("My Church") is never offered as its name.
        if not self.is_bound:
            self.initial["name"] = ""
        self.fields["name"].required = True
        self.fields["about"].max_length = ABOUT_MAX_LENGTH
        self.fields["about"].validators.append(MaxLengthValidator(ABOUT_MAX_LENGTH))
        self.fields["about"].widget.attrs["maxlength"] = ABOUT_MAX_LENGTH

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Give the church's name.")
        return name

    def clean_about(self):
        return self.cleaned_data["about"].strip()

    def clean_time_zone(self):
        # The person's device's time zone, sent by register.js; one CHORD
        # doesn't know (or none) leaves the church's default.
        zone = self.cleaned_data.get("time_zone", "").strip()
        return zone if zone in TIME_ZONES else ""

    def details(self):
        """Everything but the name, for ``register_church``."""
        data = {k: v for k, v in self.cleaned_data.items() if k != "name"}
        for optional in ("logo", "banner", "time_zone"):
            if not data.get(optional):
                data.pop(optional, None)
        return data
