"""Forms for the Church Profile sections: details, Labels, Modules and the
public homepage.

All of them take ``instance`` (the Church Profile) and have ``save()``, so the
settings pages and the setup wizard share one view.
"""

from django import forms
from django.core.validators import MaxLengthValidator

from .context_processors import module_entries
from .labels import LABEL_DEFINITIONS
from .models import ChurchProfile
from .modules import MODULE_CHOICES, MODULES, MODULES_BY_CODE, is_available

ABOUT_MAX_LENGTH = 2000


class ChurchDetailsForm(forms.ModelForm):
    class Meta:
        model = ChurchProfile
        fields = [
            "name",
            "address",
            "phone",
            "email",
            "website",
            "logo",
            "currency",
            "time_zone",
        ]
        labels = {"name": "Church name"}
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def clean_currency(self):
        return self.cleaned_data["currency"].strip().upper()


class ChurchHomepageForm(forms.ModelForm):
    """What the church shows publicly (Phase 9B). Nothing shows until the
    church switches it on, except what a new church chose at registration."""

    class Meta:
        model = ChurchProfile
        fields = [
            "show_in_directory",
            "about",
            "show_upcoming_services",
            "accept_outside_requests",
        ]
        widgets = {"about": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["about"].max_length = ABOUT_MAX_LENGTH
        self.fields["about"].validators.append(MaxLengthValidator(ABOUT_MAX_LENGTH))

    def clean_about(self):
        # Plain text: stored as typed, shown escaped with its line breaks.
        return self.cleaned_data["about"].strip()


class LabelsForm(forms.Form):
    def __init__(self, *args, instance, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        labels = instance.label_set
        for definition in LABEL_DEFINITIONS:
            self.fields[f"{definition.key}__singular"] = forms.CharField(
                label=f"{definition.singular}: singular",
                initial=labels.get(definition.key),
                max_length=60,
            )
            self.fields[f"{definition.key}__plural"] = forms.CharField(
                label=f"{definition.singular}: plural",
                initial=labels.get(definition.key, plural=True),
                max_length=60,
            )

    def rows(self):
        """(definition, singular field, plural field) for the labels table."""
        return [
            (d, self[f"{d.key}__singular"], self[f"{d.key}__plural"])
            for d in LABEL_DEFINITIONS
        ]

    def save(self):
        data = self.cleaned_data
        self.instance.labels = {
            d.key: {
                "singular": data[f"{d.key}__singular"].strip(),
                "plural": data[f"{d.key}__plural"].strip(),
            }
            for d in LABEL_DEFINITIONS
        }
        self.instance.save(update_fields=["labels", "updated_at"])
        return self.instance


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
        """(module entry in the church's words, is switched on, may be
        switched on) per Module."""
        checked = set(self["enabled"].value() or [])
        everything_on = ChurchProfile(
            labels=self.instance.labels, members_teams_unlocked=True
        )
        return [
            (e, e.code in checked, e.code in self.available)
            for e in module_entries(everything_on)
        ]

    def save(self):
        enabled = set(self.cleaned_data["enabled"])
        self.instance.disabled_modules = [
            code for code in MODULES_BY_CODE if code not in enabled
        ]
        self.instance.save(update_fields=["disabled_modules", "updated_at"])
        return self.instance


SECTIONS = {
    "details": ("Church details", ChurchDetailsForm),
    "labels": ("Labels", LabelsForm),
    "modules": ("Modules", ModulesForm),
    "homepage": ("Public homepage", ChurchHomepageForm),
}
SECTION_ORDER = list(SECTIONS)


class ChurchRegistrationForm(forms.Form):
    """Register a church: its name only (decisions 0001 and 0014).
    Everything else is set up afterwards, as settings."""

    name = forms.CharField(
        label="Church name",
        max_length=200,
        help_text="As people know it. You can change it later.",
    )

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Give the church's name.")
        return name
