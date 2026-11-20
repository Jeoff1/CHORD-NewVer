import re

from django import forms
from django.db.models import Q

from apps.core.music import KEY_CHOICES

from .chords import MAX_LENGTH
from .models import Song, ThemeTag, WorshipCheckSettings

SPOTIFY_ID = re.compile(r"^[A-Za-z0-9]{22}$")


class SongForm(forms.ModelForm):
    """A person's corrections to a song's analysis."""

    class Meta:
        model = Song
        fields = ["worship_check", "tags", "feel", "team_knows", "recording_key"]
        widgets = {
            "worship_check": forms.RadioSelect,
            "tags": forms.CheckboxSelectMultiple,
        }
        labels = {"tags": "Theme tags"}
        help_texts = {
            "worship_check": "Only worship songs are suggested for services.",
            "feel": "Song slots ask for a feel, so set the one the team plays.",
            "team_knows": "Songs the team knows rank higher in suggestions.",
            "recording_key": "The key the Spotify recording is in, so musicians "
            "can practise along with it. Spotify doesn't say; leave blank when "
            "you don't know it.",
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


class WorshipCheckSettingsForm(forms.ModelForm):
    class Meta:
        model = WorshipCheckSettings
        fields = ["pass_mark", "unlisted_rule", "unlisted_pass_mark"]
        widgets = {"unlisted_rule": forms.RadioSelect}

    def clean(self):
        cleaned = super().clean()
        mark, stricter = cleaned.get("pass_mark"), cleaned.get("unlisted_pass_mark")
        rule = cleaned.get("unlisted_rule")
        if (
            rule == WorshipCheckSettings.UnlistedRule.STRICTER
            and mark is not None
            and stricter is not None
            and stricter <= mark
        ):
            self.add_error(
                "unlisted_pass_mark", "The stricter mark must be above the pass mark."
            )
        return cleaned


class ChordSheetForm(forms.Form):
    """A chord sheet, typed or pasted: ChordPro, or chords over words as on
    Ultimate Guitar (converted on the server)."""

    key = forms.ChoiceField(
        label="Key it is written in",
        choices=[("", "Take it from the sheet's {key: …} line")] + KEY_CHOICES,
        required=False,
    )
    chordpro = forms.CharField(
        label="Chord sheet",
        max_length=MAX_LENGTH,
        widget=forms.Textarea(
            attrs={"rows": 18, "class": "font-monospace", "spellcheck": "false"}
        ),
        help_text="Paste ChordPro ([G]Amazing [C]grace), or a chart with the "
        "chords on the line above the words. Convert shows the ChordPro before "
        "you save.",
    )
