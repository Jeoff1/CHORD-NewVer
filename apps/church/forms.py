"""Forms for the three Church Profile sections: details, Labels and Modules.

All three take ``instance`` (the Church Profile) and have ``save()``, so the
settings pages and the setup wizard share one view.
"""

from django import forms

from .context_processors import module_entries
from .labels import LABEL_DEFINITIONS
from .models import ChurchProfile
from .modules import MODULE_CHOICES, MODULES, MODULES_BY_CODE


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
        self.fields["enabled"].initial = [
            m.code for m in MODULES if m.code not in instance.disabled_modules
        ]

    def rows(self):
        """(module entry in the church's words, is switched on) per Module."""
        checked = set(self["enabled"].value() or [])
        everything_on = ChurchProfile(labels=self.instance.labels)
        return [(e, e.code in checked) for e in module_entries(everything_on)]

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
}
SECTION_ORDER = list(SECTIONS)
