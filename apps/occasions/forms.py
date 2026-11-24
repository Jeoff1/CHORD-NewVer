from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.worship.forms import moment_field

from .models import Occasion, OccasionRequest, OccasionType


def officiants(current=None):
    """Active users, plus the one already chosen."""
    return (
        get_user_model()
        .objects.filter(Q(is_active=True) | Q(pk=current))
        .order_by("first_name", "last_name", "username")
    )


class OccasionForm(forms.ModelForm):
    """Add or edit an Occasion directly (Phase 9A, A5)."""

    starts_at = moment_field(label="Date and time")

    class Meta:
        model = Occasion
        fields = [
            "occasion_type",
            "starts_at",
            "length_minutes",
            "occasion_for",
            "officiant",
            "venue",
            "notes",
            "is_cancelled",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["occasion_type"].queryset = OccasionType.objects.usable(
            self.instance.occasion_type_id
        )
        self.fields["occasion_type"].empty_label = None
        self.fields["officiant"].queryset = officiants(self.instance.officiant_id)
        if not self.instance.pk:
            del self.fields["is_cancelled"]

    def clean(self):
        cleaned = super().clean()
        occasion_type = cleaned.get("occasion_type")
        if cleaned.get("length_minutes") is None and occasion_type:
            cleaned["length_minutes"] = occasion_type.length_minutes
            self.instance.length_minutes = occasion_type.length_minutes
        return cleaned


class OccasionRequestForm(forms.ModelForm):
    starts_at = moment_field(label="Preferred date and start time")

    class Meta:
        model = OccasionRequest
        fields = ["occasion_type", "starts_at", "occasion_for", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["occasion_type"].queryset = OccasionType.objects.active()
        self.fields["occasion_type"].empty_label = None
        self.fields[
            "occasion_type"
        ].help_text = "Each takes its usual length on the calendar."


class ApproveForm(forms.Form):
    """What approving sets on the new Occasion; the time may change."""

    starts_at = moment_field(label="Date and start time")
    officiant = forms.ModelChoiceField(queryset=None, required=False)
    venue = forms.CharField(max_length=200, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["officiant"].queryset = officiants()


class DeclineForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        max_length=1000,
        help_text="The person who asked reads this.",
    )
