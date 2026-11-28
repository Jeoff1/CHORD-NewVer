"""Phase 9B, slice c (decision 0014): registering churches, accounts of
one's own, adding them to a church, switching church, and the Modules a
church can't use yet."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import get_resolver, reverse
from django.urls.resolvers import URLResolver

from apps.accounts.models import Membership, Role
from apps.audit.models import AuditEvent
from apps.church import seeding
from apps.church.forms import ChurchRegistrationForm
from apps.church.middleware import SESSION_KEY
from apps.church.models import RESERVED_SLUGS, ChurchProfile
from apps.church.modules import ModuleRequiredMixin, is_enabled
from apps.church.registration import register_church
from apps.core.setting_lists import SettingListMixin
from apps.core.testing import (
    TEST_PASSWORD,
    complete_setup,
    first_church,
    make_administrator,
    make_church,
    make_user,
)
from apps.teams.models import TeamPart

REGISTER = reverse("churches:register")
USERS = reverse("accounts:user_list")
ADD_EXISTING = reverse("accounts:user_add_existing")
ACCOUNT = {
    "username": "ruth.ann",
    "first_name": "Ruth",
    "last_name": "Ann",
    "email": "ruth@example.com",
    "password1": "a-Long-pass-8472",
    "password2": "a-Long-pass-8472",
}


def switch_url(church):
    return reverse("church:switch", kwargs={"slug": church.slug})


def join(user, church, *roles):
    membership = Membership.objects.create(user=user, church=church)
    membership.roles.add(*Role.objects.filter(church=church, key__in=roles))
    return membership


class SlugTests(TestCase):
    def test_reserved_words_are_never_a_churchs_slug(self):
        for word in sorted(RESERVED_SLUGS):
            church = ChurchProfile.objects.create(name=word.replace("-", " "))
            with self.subTest(word=word):
                self.assertNotIn(church.slug, RESERVED_SLUGS)
                self.assertEqual(church.slug, f"{word}-church")

    def test_slugs_are_never_shared(self):
        slugs = [ChurchProfile.objects.create(name="Grace").slug for _ in range(3)]
        self.assertEqual(slugs, ["grace", "grace-2", "grace-3"])
        again = [ChurchProfile.objects.create(name="Register").slug for _ in range(2)]
        self.assertEqual(again, ["register-church", "register-church-2"])

    def test_a_name_without_letters_still_gets_a_slug(self):
        self.assertEqual(ChurchProfile.objects.create(name="!!!").slug, "church")


class RegisterChurchTests(TestCase):
    def setUp(self):
        complete_setup()

    def test_only_the_churchs_name_is_needed(self):
        # The details and public profile are optional (owner, 27 Nov 2026).
        form = ChurchRegistrationForm()
        self.assertEqual(
            list(form.fields),
            [
                "name",
                "address",
                "phone",
                "email",
                "logo",
                "banner",
                "about",
                "time_zone",
                "show_in_directory",
            ],
        )
        self.assertEqual(
            [name for name, field in form.fields.items() if field.required], ["name"]
        )
        self.assertFalse(ChurchRegistrationForm({}, prefix="church").is_valid())

    def test_a_visitor_registers_a_church_and_their_account(self):
        response = self.client.post(
            REGISTER, {"church-name": "Grace Chapel", **ACCOUNT}
        )
        church = ChurchProfile.objects.get(name="Grace Chapel")
        self.assertRedirects(
            response,
            reverse("home"),
            fetch_redirect_response=False,
        )
        self.assertEqual(church.slug, "grace-chapel")
        self.assertFalse(church.members_teams_unlocked)
        user = church.memberships.get().user
        self.assertEqual(user.username, "ruth@example.com")
        self.assertEqual([r.key for r in user.roles_in(church)], ["administrator"])
        self.assertEqual(self.client.session[SESSION_KEY], church.pk)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        # Its own defaults; nothing of the other church.
        self.assertEqual(Role.objects.filter(church=church).count(), 6)

    def test_a_signed_in_person_gives_only_the_name(self):
        person = make_user()
        self.client.force_login(person)
        page = self.client.get(REGISTER)
        self.assertNotContains(page, 'name="password1"')
        self.client.post(REGISTER, {"church-name": "Hope Hall"})
        church = ChurchProfile.objects.get(name="Hope Hall")
        self.assertEqual(
            set(person.memberships.values_list("church", flat=True)),
            {first_church().pk, church.pk},
        )
        self.assertEqual(self.client.session[SESSION_KEY], church.pk)

    def test_a_bad_account_creates_nothing(self):
        before = ChurchProfile.objects.count()
        response = self.client.post(
            REGISTER, {"church-name": "Grace Chapel", **ACCOUNT, "password2": "x"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChurchProfile.objects.count(), before)
        self.assertFalse(
            Membership.objects.filter(user__email="ruth@example.com").exists()
        )

    def test_a_failure_midway_leaves_nothing_behind(self):
        def fails(church):
            raise RuntimeError("Seeding broke halfway.")

        counts = {
            "churches": ChurchProfile.objects.count(),
            "roles": Role.objects.count(),
            "memberships": Membership.objects.count(),
            "events": AuditEvent.objects.count(),
        }
        halfway = [*seeding._seeders[:2], fails, *seeding._seeders[2:]]
        form = _signup_form()
        with mock.patch.object(seeding, "_seeders", halfway):
            with self.assertRaisesMessage(RuntimeError, "halfway"):
                register_church("Grace Chapel", account_form=form)
        self.assertFalse(ChurchProfile.objects.filter(name="Grace Chapel").exists())
        self.assertFalse(
            get_user_model().objects.filter(email="ruth@example.com").exists()
        )
        self.assertEqual(
            counts,
            {
                "churches": ChurchProfile.objects.count(),
                "roles": Role.objects.count(),
                "memberships": Membership.objects.count(),
                "events": AuditEvent.objects.count(),
            },
        )


def _signup_form():
    from apps.accounts.forms import SignUpForm

    form = SignUpForm(ACCOUNT)
    assert form.is_valid(), form.errors
    return form


class AddExistingAccountTests(TestCase):
    def setUp(self):
        complete_setup()
        self.admin = make_administrator()
        self.client.force_login(self.admin)
        self.other = make_church("Grace Chapel")
        self.ana = make_user(
            church=False, username="ana.cruz", email="Ana.Cruz@example.com"
        )
        self.team = Role.objects.get(church=first_church(), key="team_member")

    def add(self, account):
        return self.client.post(
            ADD_EXISTING, {"account": account, "roles": [self.team.pk]}
        )

    def test_an_exact_username_adds_them_with_roles(self):
        self.assertRedirects(self.add("ana.cruz"), USERS)
        membership = Membership.objects.get(user=self.ana, church=first_church())
        self.assertEqual(list(membership.roles.all()), [self.team])
        self.assertTrue(
            AuditEvent.objects.filter(
                object_id=str(self.ana.pk), church=first_church()
            ).exists()
        )

    def test_an_exact_email_adds_them_whatever_its_case(self):
        self.assertRedirects(self.add("ana.cruz@EXAMPLE.com"), USERS)
        self.assertTrue(self.ana.memberships.filter(church=first_church()).exists())

    def test_nothing_partial_is_ever_matched(self):
        for partial in ("ana", "ANA.CRUZ", "cruz", "ana.cruz@example", "example.com"):
            with self.subTest(partial=partial):
                response = self.add(partial)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "No account has that username or email.")
        self.assertFalse(self.ana.memberships.exists())

    def test_an_email_two_accounts_share_is_refused(self):
        make_user(church=False, username="ana2", email="ana.cruz@example.com")
        response = self.add("ana.cruz@example.com")
        self.assertContains(response, "More than one account uses that email.")

    def test_someone_already_in_the_church_is_refused(self):
        response = self.add(self.admin.username)
        self.assertContains(response, "already in this church")


class SharedAccountTests(TestCase):
    """Must-do 1: a church never changes the password, username or email of
    an account another church relies on."""

    def setUp(self):
        complete_setup()
        self.admin = make_administrator()
        self.client.force_login(self.admin)
        self.other = make_church("Grace Chapel")
        self.shared = make_user(roles=["team_member"], username="shared.one")
        join(self.shared, self.other, "administrator")
        self.only_here = make_user(roles=["team_member"], username="only.here")

    def edit_url(self, user):
        return reverse("accounts:user_update", kwargs={"pk": user.pk})

    def password_url(self, user):
        return reverse("accounts:user_password", kwargs={"pk": user.pk})

    def test_no_password_for_an_account_of_another_church(self):
        self.assertEqual(
            self.client.get(self.password_url(self.shared)).status_code, 403
        )
        response = self.client.post(
            self.password_url(self.shared),
            {
                "new_password1": "x-Taken-over-8472",
                "new_password2": "x-Taken-over-8472",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.shared.refresh_from_db()
        self.assertTrue(self.shared.check_password(TEST_PASSWORD))
        self.assertNotContains(
            self.client.get(self.edit_url(self.shared)), self.password_url(self.shared)
        )

    def test_its_account_details_stay_as_they_are(self):
        team = Role.objects.get(church=first_church(), key="team_member")
        office = Role.objects.get(church=first_church(), key="office_staff")
        response = self.client.post(
            self.edit_url(self.shared),
            {
                "username": "taken.over",
                "email": "attacker@example.com",
                "first_name": "X",
                "last_name": "Y",
                "is_active": "",
                "roles": [team.pk, office.pk],
            },
        )
        self.assertRedirects(response, USERS)
        self.shared.refresh_from_db()
        self.assertEqual(self.shared.username, "shared.one")
        self.assertNotEqual(self.shared.email, "attacker@example.com")
        self.assertTrue(self.shared.is_active)
        # Its roles in this church are this church's to change.
        self.assertEqual(set(self.shared.roles_in(first_church())), {team, office})

    def test_a_superusers_account_is_never_managed_by_a_church(self):
        boss = make_user(is_superuser=True)
        self.assertEqual(self.client.get(self.password_url(boss)).status_code, 403)

    def test_an_account_of_this_church_only_is_managed_as_before(self):
        self.assertEqual(
            self.client.get(self.password_url(self.only_here)).status_code, 200
        )


class LastAdministratorTests(TestCase):
    def setUp(self):
        complete_setup()
        self.admin = make_administrator()
        self.manager = make_user(perms=["accounts.view_user", "accounts.change_user"])
        self.client.force_login(self.manager)

    def remove(self, user):
        return self.client.post(reverse("accounts:user_remove", kwargs={"pk": user.pk}))

    def test_the_last_administrator_cant_be_removed(self):
        self.remove(self.admin)
        self.assertTrue(self.admin.memberships.filter(church=first_church()).exists())

    def test_with_another_administrator_they_can(self):
        make_administrator()
        self.assertRedirects(self.remove(self.admin), USERS)
        self.assertFalse(self.admin.memberships.exists())
        event = AuditEvent.objects.filter(object_id=str(self.admin.pk)).latest("pk")
        self.assertEqual(event.changes["Membership"], ["In this church", "Removed"])

    def test_nobody_removes_themselves(self):
        self.client.force_login(self.admin)
        make_administrator()
        self.remove(self.admin)
        self.assertTrue(self.admin.memberships.exists())

    def test_the_rule_is_per_church(self):
        # Church B's only administrator stays, however many Church A has.
        other = complete_setup(make_church("Grace Chapel"))
        only_admin = make_user(church=other, roles=["administrator"])
        join(self.admin, other)
        manager_b = make_user(
            church=other, perms=["accounts.view_user", "accounts.change_user"]
        )
        self.client.force_login(manager_b)
        self.remove(only_admin)
        self.assertTrue(only_admin.memberships.filter(church=other).exists())

    def test_nor_by_removing_their_administrator_role(self):
        self.client.force_login(
            make_user(perms=["accounts.view_user", "accounts.change_user"])
        )
        response = self.client.post(
            reverse("accounts:user_update", kwargs={"pk": self.admin.pk}),
            {
                "username": self.admin.username,
                "email": self.admin.email,
                "is_active": "on",
                "roles": [],
            },
        )
        self.assertContains(response, "only active administrator")


class ChurchSwitcherTests(TestCase):
    def setUp(self):
        self.a = complete_setup()
        self.b = complete_setup(make_church("Grace Chapel"))
        self.person = make_user(roles=["team_member"])
        self.membership_b = join(self.person, self.b, "team_member")
        self.client.force_login(self.person)

    def church_now(self):
        return self.client.get(reverse("home")).context["church"]

    def test_switching_needs_post_and_the_csrf_token(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.person)
        self.assertEqual(strict.get(switch_url(self.b)).status_code, 405)
        self.assertEqual(strict.post(switch_url(self.b)).status_code, 403)
        self.assertEqual(self.church_now(), self.a)

    def test_a_member_switches(self):
        self.assertRedirects(self.client.post(switch_url(self.b)), reverse("home"))
        self.assertEqual(self.church_now(), self.b)
        page = self.client.get(reverse("home"))
        self.assertContains(page, "Working in")

    def test_a_church_they_dont_belong_to_is_refused(self):
        stranger = complete_setup(make_church("Hope Hall"))
        self.assertEqual(self.client.post(switch_url(stranger)).status_code, 404)
        self.assertEqual(self.church_now(), self.a)
        missing = reverse("church:switch", kwargs={"slug": "no-such-church"})
        self.assertEqual(self.client.post(missing).status_code, 404)

    def test_a_removed_membership_drops_the_church_mid_session(self):
        self.client.post(switch_url(self.b))
        self.membership_b.delete()
        self.assertEqual(self.church_now(), self.a)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_a_deactivated_membership_drops_the_church_mid_session(self):
        self.client.post(switch_url(self.b))
        self.membership_b.is_active = False
        self.membership_b.save()
        self.assertEqual(self.church_now(), self.a)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_signing_out_clears_it(self):
        self.client.post(switch_url(self.b))
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.client.force_login(self.person)
        self.assertEqual(self.church_now(), self.a)

    def test_one_church_shows_no_switcher(self):
        self.membership_b.delete()
        self.assertNotContains(self.client.get(reverse("home")), "Working in")

    def test_a_superuser_may_switch_to_any_church(self):
        boss = make_user(is_superuser=True)
        self.client.force_login(boss)
        stranger = complete_setup(make_church("Hope Hall"))
        self.client.post(switch_url(stranger))
        self.assertEqual(self.church_now(), stranger)


def module_urls(namespace):
    """(name, a URL) for every page of ``namespace``, with made-up arguments."""
    resolver = get_resolver().namespace_dict[namespace][1]
    made_up = {
        "public_id": "00000000-0000-4000-8000-000000000000",
        "assignment_id": "00000000-0000-4000-8000-000000000001",
        "pk": 1,
        "key": "x",
        "action": "take",
    }
    for pattern in resolver.url_patterns:
        assert not isinstance(pattern, URLResolver)
        names = pattern.pattern.regex.groupindex
        kwargs = {name: made_up[name] for name in names}
        yield (
            pattern,
            reverse(f"{namespace}:{pattern.name}", kwargs=kwargs or None),
        )


class ModuleAvailabilityTests(TestCase):
    """Teams is kept apart per church since 28 Nov 2026, so every church may
    use it; the Member Directory is retired for every church."""

    def setUp(self):
        self.a = complete_setup()
        self.b = complete_setup(make_church("Grace Chapel"))
        self.admin_b = make_user(church=self.b, roles=["administrator"])

    def test_every_members_and_teams_view_checks_the_module(self):
        for namespace in ("members", "teams"):
            for pattern, _ in module_urls(namespace):
                view = pattern.callback.view_class
                setting_list = pattern.callback.view_initkwargs.get("setting_list")
                module = setting_list.module if setting_list else view.module
                with self.subTest(view=pattern.name):
                    self.assertTrue(
                        issubclass(view, (ModuleRequiredMixin, SettingListMixin))
                    )
                    self.assertEqual(module, namespace)

    def test_every_members_url_is_404_in_every_church(self):
        for admin in (self.admin_b, make_administrator()):
            self.client.force_login(admin)
            for pattern, url in module_urls("members"):
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 404)
                    self.assertEqual(self.client.post(url).status_code, 404)
        with self.settings(RETIRED_MODULES=()):
            self.assertEqual(self.client.get(reverse("members:list")).status_code, 200)

    def test_teams_works_in_a_church_registered_later(self):
        self.client.force_login(self.admin_b)
        self.assertTrue(is_enabled("teams", self.b))
        self.assertEqual(self.client.get(reverse("teams:roster")).status_code, 200)
        parts = self.client.get(reverse("teams:parts_list"))
        self.assertContains(parts, "Vocals")
        self.assertEqual(
            TeamPart.objects.for_church(self.b).count(),
            TeamPart.objects.for_church(self.a).count(),
        )

    def test_every_church_switches_the_praise_team(self):
        for admin, church in ((self.admin_b, self.b), (make_administrator(), self.a)):
            self.client.force_login(admin)
            url = reverse("church:settings", kwargs={"section": "modules"})
            page = self.client.get(url)
            self.assertNotContains(page, "Not available yet")
            self.assertContains(page, 'role="switch"', count=4)
            self.assertNotContains(page, 'value="members"')
            self.client.post(url, {"enabled": ["worship"]})
            church.refresh_from_db()
            self.assertFalse(is_enabled("teams", church))
            self.client.post(url, {"enabled": ["worship", "teams"]})
            church.refresh_from_db()
            self.assertTrue(is_enabled("teams", church))
