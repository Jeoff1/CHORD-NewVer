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
        "ministry",
        "Ministry",
        "Ministries",
        "A group that serves in the church, e.g. Ministry, Group, Organization.",
    ),
    LabelDefinition(
        "officiant",
        "Officiant",
        "Officiants",
        "The person who leads a service, e.g. Priest, Pastor, Minister, Elder.",
    ),
    LabelDefinition(
        "service",
        "Service",
        "Services",
        "Something people request from the church, e.g. Service, Sacrament, Rite.",
    ),
    LabelDefinition(
        "worship_service",
        "Worship Service",
        "Worship Services",
        "The church's regular gathering for worship, e.g. Mass, Service, Gathering.",
    ),
    LabelDefinition(
        "offering",
        "Offering",
        "Offerings",
        "Money given to the church, e.g. Offering, Tithe, Collection, Donation.",
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
