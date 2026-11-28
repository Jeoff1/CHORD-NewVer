from django import forms

from apps.core.people import display_name

from .models import BlackoutDate
from .rostering import usable_parts

DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class PartsForm(forms.Form):
    """A person's Team Profile: the parts they can take."""

    parts = forms.ModelMultipleChoiceField(
        label="Team parts",
        queryset=None,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, church, current=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parts"].queryset = usable_parts(church, current)
        self.initial.setdefault("parts", [part.pk for part in current])


class BlackoutForm(forms.ModelForm):
    class Meta:
        model = BlackoutDate
        fields = ["starts_on", "ends_on", "note"]
        widgets = {"starts_on": DATE_INPUT, "ends_on": DATE_INPUT}
        help_texts = {"note": "Optional; only you see it."}

    def clean(self):
        cleaned = super().clean()
        starts_on, ends_on = cleaned.get("starts_on"), cleaned.get("ends_on")
        if starts_on and ends_on and ends_on < starts_on:
            self.add_error("ends_on", "The last day can't be before the first.")
        return cleaned


class AssignForm(forms.Form):
    """Choose who takes the part, from the people who may."""

    person = forms.ChoiceField(widget=forms.RadioSelect, label="Person")

    def __init__(self, *args, available=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.people = {str(person.pk): person for person in available}
        self.fields["person"].choices = [
            (str(person.pk), display_name(person)) for person in available
        ]

    def clean_person(self):
        return self.people[self.cleaned_data["person"]]


class SwapRequestForm(forms.Form):
    """Nothing to fill in: the page confirms which assignment to hand over."""
