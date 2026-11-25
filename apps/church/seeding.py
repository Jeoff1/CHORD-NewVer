"""What every new church starts with (Phase 9B, decision 0014).

The church app is core and never imports the Modules, so each app that
gives a new church its defaults (roles, theme tags, a service template,
settings rows, example Occasion Types) registers a **seeder** here in its
``AppConfig.ready()``. ``seed_church`` runs them all.

The church that existed before Phase 9B got its defaults from data
migrations; seeders give later churches the same starting values.
"""

from django.db import transaction

_seeders = []


def register(seeder):
    """Add ``seeder(church)``. Called once per app, from AppConfig.ready()."""
    if seeder not in _seeders:
        _seeders.append(seeder)


@transaction.atomic
def seed_church(church):
    """Give ``church`` its defaults. Run once, right after creating it."""
    for seeder in _seeders:
        seeder(church)
