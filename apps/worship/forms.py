import re

from django import forms
from django.db.models import Q
from django.forms import inlineformset_factory

from apps.songs.models import ThemeTag

from .models import (
    LineupItem,
    Season,
    SermonSeries,
    ServiceTemplate,
    SuggestionSettings,
    TemplateSlot,
    Theme,
    WorshipService,
)
from .scheduling import MAX_WEEKS_AHEAD

MOMENT_FORMAT = "%Y-%m-%dT%H:%M"


def moment_field(**kwargs):
    """A date-and-time field using the browser's own picker."""
    return forms.DateTimeField(
        input_formats=[MOMENT_FORMAT, "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"}, format=MOMENT_FORMAT
        ),
        **kwargs,
    )


class ServiceForm(forms.ModelForm):
    starts_at = moment_field(label="Date and time")
    rehearsal_at = moment_field(label="Rehearsal", required=False)

    class Meta:
        model = WorshipService
        fields = [
            "template",
            "name",
            "starts_at",
            "rehearsal_at",
            "notes",
            "is_cancelled",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
        help_texts = {
            "name": "Leave blank to use the template's name.",
            "is_cancelled": "A cancelled service stays on the schedule, crossed out.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = False
        self.fields["template"].queryset = ServiceTemplate.objects.usable(
            self.instance.template_id
        )
        if not self.instance.pk:
            del self.fields["is_cancelled"]
            templates = list(self.fields["template"].queryset[:2])
            if len(templates) == 1:
                self.initial.setdefault("template", templates[0].pk)

    def clean(self):
        cleaned = super().clean()
        template = cleaned.get("template")
        if not cleaned.get("name") and template:
            cleaned["name"] = template.name
        starts_at, rehearsal_at = cleaned.get("starts_at"), cleaned.get("rehearsal_at")
        if starts_at and rehearsal_at and rehearsal_at > starts_at:
            self.add_error("rehearsal_at", "The rehearsal must be before the service.")
        return cleaned


class ThemeForm(forms.ModelForm):
    class Meta:
        model = Theme
        fields = ["title", "scripture", "series", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 10})}

    def __init__(self, *args, labels, **kwargs):
        super().__init__(*args, **kwargs)
        sermon = labels.get("sermon")
        self.fields["series"].queryset = SermonSeries.objects.usable(
            self.instance.series_id
        )
        self.fields["series"].label = f"{sermon} series"
        self.fields["notes"].label = f"{sermon} notes"


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = WorshipService
        fields = ["attendance"]


class TemplateForm(forms.ModelForm):
    class Meta:
        model = ServiceTemplate
        fields = [
            "name",
            "description",
            "weekday",
            "start_time",
            "length_minutes",
            "sort_order",
            "is_active",
        ]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["length_minutes"].required = False

    def clean_length_minutes(self):
        """Left blank, a template keeps its length (90 minutes when new)."""
        value = self.cleaned_data.get("length_minutes")
        if value is None:
            return self.instance.length_minutes
        return value

    def clean(self):
        cleaned = super().clean()
        if (cleaned.get("weekday") is None) != (cleaned.get("start_time") is None):
            raise forms.ValidationError(
                "Give both the usual day and the usual start time, or neither."
            )
        return cleaned


class SlotForm(forms.ModelForm):
    class Meta:
        model = TemplateSlot
        fields = ["name", "feel", "position"]
        widgets = {"position": forms.NumberInput(attrs={"style": "max-width: 6rem"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["feel"].choices = [
            ("", "Any feel"),
            *self.fields["feel"].choices[1:],
        ]


SlotFormSet = inlineformset_factory(
    ServiceTemplate, TemplateSlot, form=SlotForm, extra=3, can_delete=True
)


class ScheduleAheadForm(forms.Form):
    template = forms.ModelChoiceField(queryset=ServiceTemplate.objects.none())
    weeks = forms.IntegerField(
        min_value=1,
        max_value=MAX_WEEKS_AHEAD,
        initial=8,
        label="How many weeks ahead",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template"].queryset = ServiceTemplate.objects.active().filter(
            weekday__isnull=False, start_time__isnull=False
        )


# --- Song suggestions --------------------------------------------------------


class SuggestionSettingsForm(forms.ModelForm):
    class Meta:
        model = SuggestionSettings
        fields = [
            "search_genres",
            "phrases_per_theme",
            "pages_per_phrase",
            "market",
            "weight_relevance",
            "weight_familiarity",
            "weight_season",
            "weight_recency",
            "weight_feel",
            "repeat_window_weeks",
            "suggestions_kept",
        ]

    def clean_market(self):
        market = self.cleaned_data["market"].strip().upper()
        if market and not re.fullmatch(r"[A-Z]{2}", market):
            raise forms.ValidationError("Use a two-letter country code, such as PH.")
        return market

    def clean_search_genres(self):
        genres = [g.strip() for g in self.cleaned_data["search_genres"].split(",")]
        return ", ".join(g for g in genres if g)


class SeasonForm(forms.ModelForm):
    class Meta:
        model = Season
        fields = [
            "name",
            "starts_on",
            "ends_on",
            "repeats_yearly",
            "tags",
            "description",
            "sort_order",
            "is_active",
        ]
        widgets = {
            "starts_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "ends_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "tags": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = (
            list(self.instance.tags.values_list("pk", flat=True))
            if self.instance.pk
            else []
        )
        self.fields["tags"].queryset = ThemeTag.objects.filter(
            Q(is_active=True) | Q(pk__in=current)
        )

    def clean(self):
        cleaned = super().clean()
        starts, ends = cleaned.get("starts_on"), cleaned.get("ends_on")
        if starts and ends and ends < starts and not cleaned.get("repeats_yearly"):
            self.add_error(
                "ends_on",
                "The season must end on or after its start. A yearly season may "
                "run over the new year.",
            )
        return cleaned


class LineupItemForm(forms.ModelForm):
    """A lineup song's service key and notes."""

    class Meta:
        model = LineupItem
        fields = ["key", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
        help_texts = {"notes": "For the team, e.g. who starts it or a repeat."}


class SendBackForm(forms.Form):
    note = forms.CharField(
        label="Note for the worship leader",
        widget=forms.Textarea(attrs={"rows": 3}),
        max_length=2000,
        help_text="What should change.",
    )
