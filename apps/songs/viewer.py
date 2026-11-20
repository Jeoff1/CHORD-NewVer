"""The chord sheet viewer: what a page shows for a sheet, from the choices
in its query string (decision 0009).

- ``key``: the key to show; a personal transpose that nobody else sees.
  Without it, the base key: the lineup's service key, or the sheet's own.
- ``capo``: 0 to 7; the chords become the shapes played.
- ``numbers=1``: Nashville numbers instead of chord names.
- ``practise=1``: the recording's key, so musicians can play along with
  the Spotify track. Offered only when a person has entered that key.

A key change re-renders only the sheet (htmx), on the server.
"""

from urllib.parse import urlencode

from apps.core.music import KEY_CHOICES

from . import chords


def _key(name):
    try:
        return chords.Key.parse(name) if name else None
    except ValueError:
        return None


def sheet_view(sheet, params, *, base_key="", recording_key=""):
    """The template context for showing ``sheet``. ``params`` is the
    request's query string; ``base_key`` the key shown by default."""
    original = chords.Key.parse(sheet.key)
    base = _key(base_key) or original
    recording = _key(recording_key)
    practise = recording is not None and params.get("practise") == "1"
    target = recording if practise else (_key(params.get("key")) or base)
    numbers = params.get("numbers") == "1"
    try:
        capo = int(params.get("capo") or 0)
    except ValueError:
        capo = 0
    rendered = chords.render(
        sheet.chordpro, original, target, capo=capo, numbers=numbers
    )

    def query(**changes):
        values = {
            "key": target.name,
            "capo": rendered.capo or "",
            "numbers": "1" if numbers else "",
        }
        values.update(changes)
        return "?" + urlencode({k: v for k, v in values.items() if v not in ("", None)})

    return {
        "sheet": sheet,
        "rendered": rendered,
        "base_key": base,
        "target": target,
        "is_personal": target != base and not practise,
        "practise": practise,
        "recording_key": recording,
        "key_choices": KEY_CHOICES,
        "capo_options": chords.capo_options(target),
        "up_query": query(key=target.shifted(1).name),
        "down_query": query(key=target.shifted(-1).name),
        "reset_query": query(key=base.name, capo="", numbers=""),
    }
