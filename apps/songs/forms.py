import re

from django import forms
from django.db.models import Q

from .models import Song, ThemeTag

SPOTIFY_ID = re.compile(r"^[A-Za-z0-9]{22}$")


class SongForm(forms.ModelForm):
    """A person's corrections to a song's analysis."""

    class Meta:
        model = Song
        fields = ["worship_check", "tags", "feel", "team_knows"]
        widgets = {
            "worship_check": forms.RadioSelect,
            "tags": forms.CheckboxSelectMultiple,
        }
        labels = {"tags": "Theme tags"}
        help_texts = {
            "worship_check": "Only worship songs are suggested for services.",
            "feel": "Song slots ask for a feel, so set the one the team plays.",
            "team_knows": "Songs the team knows rank higher in suggestions.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = list(self.instance.tags.values_list("pk", flat=True))
        self.fields["tags"].queryset = ThemeTag.objects.filter(
            Q(is_active=True) | Q(pk__in=current)
        )
        self.fields["feel"].choices = [
            ("", "Not set"),
            *self.fields["feel"].choices[1:],
        ]


class SpotifyTrackForm(forms.Form):
    spotify_id = forms.RegexField(regex=SPOTIFY_ID)
