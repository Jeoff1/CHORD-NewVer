"""What a new church's worship schedule starts with (Phase 9B, decision
0014): the same neutral service template the first church got from
migration 0002, and suggestion settings with their defaults."""

TEMPLATE_NAME = "Worship Service"
TEMPLATE_DESCRIPTION = "The church's regular gathering for worship."
SLOTS = [
    # name, feel
    ("Opening", "upbeat"),
    ("Praise", "mid"),
    ("Worship", "slow"),
    ("Response", "slow"),
]


def seed(church):
    from .models import ServiceTemplate, SuggestionSettings, TemplateSlot

    if not ServiceTemplate.objects.filter(church=church).exists():
        template = ServiceTemplate.objects.create(
            church=church,
            name=TEMPLATE_NAME,
            description=TEMPLATE_DESCRIPTION,
            sort_order=10,
        )
        TemplateSlot.objects.bulk_create(
            TemplateSlot(template=template, name=name, feel=feel, position=n * 10)
            for n, (name, feel) in enumerate(SLOTS, start=1)
        )
    SuggestionSettings.load(church)
