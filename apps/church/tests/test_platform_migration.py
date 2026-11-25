"""Phase 9B (decision 0014): moving to many churches loses nothing.

Migrates back to before Phase 9B, builds data the old way, migrates
forward, and checks that the first church holds every record and every
user's roles.
"""

import datetime

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

BEFORE_9B = [
    ("accounts", "0007_user_theme"),
    ("announcements", "0001_initial"),
    ("audit", "0002_signinevent"),
    ("church", "0002_rescope_modules_and_labels"),
    ("notifications", "0001_initial"),
    ("occasions", "0002_seed_occasion_types"),
    ("songs", "0007_churchspotifyaccount"),
    ("worship", "0012_template_length"),
]

# Records that belong to one church, by model; their counts must not change.
SCOPED = [
    ("accounts", "Role"),
    ("announcements", "Announcement"),
    ("audit", "AuditEvent"),
    ("notifications", "Notification"),
    ("occasions", "OccasionType"),
    ("occasions", "Occasion"),
    ("occasions", "OccasionRequest"),
    ("songs", "Song"),
    ("songs", "ThemeTag"),
    ("songs", "TrustedArtist"),
    ("songs", "WorshipCheckSettings"),
    ("songs", "ChurchSpotifyAccount"),
    ("worship", "ServiceTemplate"),
    ("worship", "SermonSeries"),
    ("worship", "Season"),
    ("worship", "WorshipService"),
    ("worship", "SuggestionSettings"),
]


class ChurchPlatformMigrationTests(TransactionTestCase):
    # The seeded rows (roles, tags, the default template) are put back
    # after this test, for the tests that run after it.
    serialized_rollback = True

    def migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        return MigrationExecutor(connection).loader.project_state(targets).apps

    def build_old_data(self, apps):
        get = apps.get_model
        church = get("church", "ChurchProfile").objects.get_or_create(pk=1)[0]
        roles = {r.key: r for r in get("accounts", "Role").objects.all()}
        User = get("accounts", "User")
        leader = User.objects.create(username="leader")
        leader.groups.add(roles["worship_leader"], roles["team_member"])
        gone = User.objects.create(username="gone", is_active=False)
        gone.groups.add(roles["administrator"])
        User.objects.create(username="no-roles")

        soon = timezone.now() + datetime.timedelta(days=7)
        template = get("worship", "ServiceTemplate").objects.first()
        get("worship", "SermonSeries").objects.create(name="Psalms")
        get("worship", "Season").objects.create(
            name="Harvest",
            starts_on=datetime.date(2026, 9, 1),
            ends_on=datetime.date(2026, 9, 30),
        )
        service = get("worship", "WorshipService").objects.create(
            name="Sunday", template=template, starts_at=soon
        )
        get("worship", "SuggestionSettings").objects.create(pk=1)
        get("songs", "WorshipCheckSettings").objects.create(pk=1)
        get("songs", "Song").objects.create(
            title="Hymn", artist="Choir", spotify_id="t1"
        )
        get("songs", "TrustedArtist").objects.create(name="Choir")
        occasion_type = get("occasions", "OccasionType").objects.first()
        get("occasions", "Occasion").objects.create(
            occasion_type=occasion_type,
            starts_at=soon + datetime.timedelta(days=1),
            occasion_for="A and B",
            length_minutes=90,
        )
        get("occasions", "OccasionRequest").objects.create(
            requester=leader,
            occasion_type=occasion_type,
            starts_at=soon + datetime.timedelta(days=2),
            occasion_for="C",
        )
        get("announcements", "Announcement").objects.create(
            title="Hello", body="Welcome.", author=leader, service=None
        )
        get("notifications", "Notification").objects.create(
            recipient=leader, text="You're on the team."
        )
        get("audit", "AuditEvent").objects.create(
            actor=leader,
            action="created",
            content_type_id=ContentType.objects.get_for_model(
                get("worship", "WorshipService")
            ).pk,
            object_id=str(service.pk),
            object_repr=str(service),
        )
        old_roles = {
            user.username: {g.name for g in user.groups.all()}
            for user in User.objects.all()
        }
        counts = {
            f"{app}.{model}": get(app, model).objects.count() for app, model in SCOPED
        }
        return church.pk, old_roles, counts

    def test_the_first_church_keeps_everything(self):
        old_apps = self.migrate(BEFORE_9B)
        church_pk, old_roles, counts = self.build_old_data(old_apps)

        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        apps = self.migrate(latest)
        get = apps.get_model

        for app, model in SCOPED:
            rows = get(app, model).objects.all()
            self.assertEqual(rows.count(), counts[f"{app}.{model}"], model)
            self.assertFalse(rows.exclude(church_id=church_pk).exists(), model)

        church = get("church", "ChurchProfile").objects.get(pk=church_pk)
        self.assertTrue(church.members_teams_unlocked)
        self.assertTrue(church.slug)
        # Nothing about it is public until its Administrator chooses.
        self.assertFalse(church.show_in_directory)
        self.assertFalse(church.show_upcoming_services)
        self.assertFalse(
            get("occasions", "OccasionType")
            .objects.filter(offered_publicly=True)
            .exists()
        )

        # Every user, active or not, has a Membership there with exactly the
        # roles they held; role names are kept as titles.
        for user in get("accounts", "User").objects.all():
            membership = get("accounts", "Membership").objects.get(user=user)
            self.assertEqual(membership.church_id, church_pk)
            self.assertEqual(
                {role.title for role in membership.roles.all()},
                old_roles[user.username],
                user.username,
            )

        # New rows get fresh ids: the old pk=1 rows didn't block the sequences.
        other = get("church", "ChurchProfile").objects.create(name="New", slug="new")
        get("worship", "SuggestionSettings").objects.create(church=other)
        get("songs", "WorshipCheckSettings").objects.create(church=other)
