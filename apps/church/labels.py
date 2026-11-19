"""Labels: the church's own words for concepts whose wording differs.

Defaults are neutral. The church's edits are stored in
``ChurchProfile.labels`` as ``{key: {"singular": ..., "plural": ...}}``; a
key without an edit uses its default.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LabelDefinition:
    key: str
    singular: str
    plural: str
    help_text: str


LABEL_DEFINITIONS = (
    LabelDefinition(
        "member",
        "Member",
        "Members",
        "A person who belongs to the church, e.g. Member, Parishioner, Congregant.",
    ),
    LabelDefinition(
        "worship_service",
        "Worship Service",
        "Worship Services",
        "The church's gathering for worship, e.g. Mass, Service, Gathering.",
    ),
    LabelDefinition(
        "sermon",
        "Sermon",
        "Sermons",
        "The talk given at a worship service, e.g. Sermon, Homily, Message.",
    ),
    LabelDefinition(
        "lineup",
        "Lineup",
        "Lineups",
        "The songs chosen for a worship service, e.g. Lineup, Set List, Song List.",
    ),
    LabelDefinition(
        "pastor",
        "Pastor",
        "Pastors",
        "The people with the final say on a lineup, e.g. Pastor, Minister, Elder.",
    ),
)

LABELS_BY_KEY = {label.key: label for label in LABEL_DEFINITIONS}


class Labels:
    """The church's wording, with defaults for keys it hasn't edited."""

    def __init__(self, stored=None):
        self._stored = stored or {}

    def get(self, key, plural=False):
        definition = LABELS_BY_KEY[key]
        form = "plural" if plural else "singular"
        stored = self._stored.get(key, {}).get(form, "").strip()
        return stored or getattr(definition, form)

    def __getitem__(self, key):
        """Template access: ``{{ labels.member }}`` gives the singular."""
        return self.get(key)
