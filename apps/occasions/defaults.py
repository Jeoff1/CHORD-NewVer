"""Example Occasion Types for a new church, switched off (Phase 9B,
decision 0014): the same examples the first church got from migration
0002. The church switches on the ones it holds, renames them or adds its
own."""

EXAMPLES = [
    # name, usual length in minutes
    ("Wedding", 120),
    ("Baptism", 60),
    ("Funeral", 90),
]
DESCRIPTION = "An example. Switch it on to let people request it."


def seed(church):
    from .models import OccasionType

    for n, (name, length) in enumerate(EXAMPLES, start=1):
        OccasionType.objects.get_or_create(
            church=church,
            name=name,
            defaults={
                "description": DESCRIPTION,
                "length_minutes": length,
                "sort_order": n * 10,
                "is_active": False,
            },
        )
