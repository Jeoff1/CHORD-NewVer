"""Tidy reasons saved before the Phase 6 click-through fixes (2026-11-19).

- Lineup songs no longer store a feel reason: it depends on the slot a song
  is in now, so the lineup works it out when shown. Stored ones ("Its feel
  …") are dropped, so a moved song never shows another slot's reason.
- "Other versions in the pool" now reads "Title, Artist; Title, Artist"
  instead of "Title (Artist), Title (Artist)", whose brackets nested when an
  artist name held brackets of its own. Saved reasons are rewritten, on
  lineup songs and on suggestions.
"""

from django.db import migrations, models

FEEL_PREFIX = "Its feel "
VERSIONS_PREFIX = "Other versions in the pool: "


def _split_top_level(text, separator=", "):
    """Split ``text`` at ``separator`` outside brackets."""
    parts, depth, start, i = [], 0, 0, 0
    while i < len(text):
        char = text[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        elif depth == 0 and text.startswith(separator, i):
            parts.append(text[start:i])
            i += len(separator)
            start = i
            continue
        i += 1
    parts.append(text[start:])
    return parts


def _title_and_artist(entry):
    """("Title", "Artist") from "Title (Artist)", where the artist may hold
    brackets of its own; None when the entry isn't in that form."""
    entry = entry.strip()
    if not entry.endswith(")"):
        return None
    depth = 0
    for i in range(len(entry) - 1, -1, -1):
        if entry[i] == ")":
            depth += 1
        elif entry[i] == "(":
            depth -= 1
            if depth == 0:
                title, artist = entry[:i].strip(), entry[i + 1 : -1].strip()
                return (title, artist) if title and artist else None
    return None


def versions_reason(reason):
    """The versions reason in the new form; any other reason unchanged."""
    if not reason.startswith(VERSIONS_PREFIX) or not reason.endswith(")."):
        return reason
    pairs = [
        _title_and_artist(entry)
        for entry in _split_top_level(reason[len(VERSIONS_PREFIX) : -1])
    ]
    if any(pair is None for pair in pairs):
        return reason
    return VERSIONS_PREFIX + "; ".join(f"{t}, {a}" for t, a in pairs) + "."


def lineup_reasons(reasons):
    return [
        versions_reason(reason)
        for reason in reasons
        if not reason.startswith(FEEL_PREFIX)
    ]


def forwards(apps, schema_editor):
    LineupItem = apps.get_model("worship", "LineupItem")
    Suggestion = apps.get_model("worship", "Suggestion")
    for item in LineupItem.objects.all():
        tidy = lineup_reasons(item.reasons)
        if tidy != item.reasons:
            item.reasons = tidy
            item.save(update_fields=["reasons"])
    for suggestion in Suggestion.objects.all().iterator():
        tidy = [versions_reason(reason) for reason in suggestion.reasons]
        if tidy != suggestion.reasons:
            suggestion.reasons = tidy
            suggestion.save(update_fields=["reasons"])


class Migration(migrations.Migration):
    dependencies = [("worship", "0006_lineups")]

    operations = [
        migrations.AlterField(
            model_name="lineupitem",
            name="reasons",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Why the song was suggested for the theme, copied when "
                "it joined the lineup. The feel reason depends on the slot, so it "
                "is worked out when shown (slot_reason).",
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
