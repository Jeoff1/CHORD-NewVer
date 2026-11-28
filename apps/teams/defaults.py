"""Neutral starting Team Parts for a new church (28 Nov 2026, decision
0014): the same parts the first church got from migration 0002. The church
renames them, switches them off or adds its own."""

PARTS = [
    "Vocals",
    "Acoustic guitar",
    "Electric guitar",
    "Bass",
    "Keys",
    "Drums",
]


def seed(church):
    from .models import TeamPart

    for order, name in enumerate(PARTS, start=1):
        TeamPart.objects.get_or_create(
            church=church, name=name, defaults={"sort_order": order * 10}
        )
