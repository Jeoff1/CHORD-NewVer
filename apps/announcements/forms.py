from django import forms

from apps.church.models import ChurchProfile

from .models import Announcement
from .services import team_services, teams_on

Audience = Announcement.Audience


class AnnouncementForm(forms.Form):
    title = forms.CharField(max_length=120)
    body = forms.CharField(label="Message", widget=forms.Textarea(attrs={"rows": 5}))
    audience = forms.ChoiceField(
        label="To", choices=Audience.choices, widget=forms.RadioSelect
    )
    service = forms.ModelChoiceField(queryset=None, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault("audience", Audience.EVERYONE)
        word = ChurchProfile.load().label_set.get("worship_service").lower()
        self.fields["audience"].choices = [
            (Audience.EVERYONE, "Everyone signed in"),
            (Audience.SERVICE_TEAM, f"One {word}'s team"),
        ]
        if teams_on():
            self.fields["service"].label = word.capitalize()
            self.fields[
                "service"
            ].help_text = f"For one {word}'s team: its assigned people see it."
            self.fields["service"].queryset = team_services()
        else:
            # "One service's team" is offered only while Teams is on.
            self.fields["audience"].choices = self.fields["audience"].choices[:1]
            del self.fields["service"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("audience") == Audience.SERVICE_TEAM and not cleaned.get(
            "service"
        ):
            self.add_error("service", "Choose whose team it is for.")
        return cleaned
