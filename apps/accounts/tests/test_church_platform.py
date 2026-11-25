"""Phase 9B, slice a (decision 0014): roles and permissions belong to a
church, and people work in a Current Church."""

from django.contrib.auth.models import Permission
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.forms import RoleForm
from apps.accounts.models import Membership, Role
from apps.accounts.roles import DEFAULT_ROLES, administrators, users_with_perm
from apps.church.middleware import SESSION_KEY, CurrentChurchMiddleware
from apps.core.testing import first_church, make_administrator, make_church, make_user
from apps.occasions.models import OccasionType
from apps.songs.models import ThemeTag, WorshipCheckSettings
from apps.worship.models import ServiceTemplate, SuggestionSettings

CHANGE_PROFILE = "church.change_churchprofile"


def working_in(user, church):
    """``user`` as a request in ``church`` would see them."""
    user = type(user).objects.get(pk=user.pk)
    user.current_church = church
    return user


class PermissionsFollowTheCurrentChurchTests(TestCase):
    def setUp(self):
        self.first = first_church()
        self.other = make_church("Grace Chapel")

    def test_roles_in_one_church_give_nothing_in_another(self):
        user = make_administrator()
        self.assertTrue(working_in(user, self.first).has_perm(CHANGE_PROFILE))
        self.assertFalse(working_in(user, self.other).has_perm(CHANGE_PROFILE))

    def test_each_church_gives_its_own_roles(self):
        user = make_user(roles=["team_member"])
        Membership.objects.create(user=user, church=self.other).roles.add(
            Role.objects.get(church=self.other, key="administrator")
        )
        self.assertFalse(working_in(user, self.first).has_perm(CHANGE_PROFILE))
        self.assertTrue(working_in(user, self.other).has_perm(CHANGE_PROFILE))

    def test_no_current_church_means_no_permissions(self):
        self.assertFalse(
            working_in(make_administrator(), None).has_perm(CHANGE_PROFILE)
        )

    def test_an_inactive_membership_gives_nothing(self):
        user = make_administrator()
        user.memberships.update(is_active=False)
        self.assertFalse(working_in(user, self.first).has_perm(CHANGE_PROFILE))

    def test_groups_and_direct_permissions_give_nothing(self):
        user = make_user()
        user.groups.add(Role.objects.get(church=self.first, key="administrator"))
        user.user_permissions.add(
            Permission.objects.get(codename="change_churchprofile")
        )
        self.assertFalse(working_in(user, self.first).has_perm(CHANGE_PROFILE))

    def test_a_superuser_holds_everything_everywhere(self):
        boss = make_user(is_superuser=True, church=False)
        self.assertTrue(working_in(boss, self.other).has_perm(CHANGE_PROFILE))

    def test_users_with_perm_looks_in_one_church(self):
        here = make_administrator()
        there = make_user(church=self.other, roles=["administrator"])
        self.assertEqual(list(users_with_perm(self.first, CHANGE_PROFILE)), [here])
        self.assertEqual(list(users_with_perm(self.other, CHANGE_PROFILE)), [there])

    def test_administrators_are_per_church(self):
        here = make_administrator()
        there = make_user(church=self.other, roles=["administrator"])
        self.assertIn(here, administrators(self.first))
        self.assertNotIn(there, administrators(self.first))
        self.assertIn(there, administrators(self.other))


class CurrentChurchMiddlewareTests(TestCase):
    def setUp(self):
        self.first = first_church()
        self.other = make_church("Grace Chapel")

    def church_for(self, user, chosen=None):
        seen = {}

        def view(request):
            seen["church"] = request.church
            seen["user_church"] = getattr(request.user, "current_church", None)
            return HttpResponse()

        request = RequestFactory().get("/")
        request.user = user
        request.session = {SESSION_KEY: chosen.pk} if chosen else {}
        CurrentChurchMiddleware(view)(request)
        return seen["church"], seen["user_church"]

    def test_the_first_membership_by_default(self):
        user = make_user(church=self.other)
        Membership.objects.create(user=user, church=self.first)
        self.assertEqual(self.church_for(user), (self.other, self.other))

    def test_the_chosen_church_when_a_member_there(self):
        user = make_user()
        Membership.objects.create(user=user, church=self.other)
        self.assertEqual(self.church_for(user, self.other)[0], self.other)

    def test_a_church_without_membership_cant_be_chosen(self):
        user = make_user()
        self.assertEqual(self.church_for(user, self.other)[0], self.first)

    def test_an_inactive_membership_cant_be_chosen(self):
        user = make_user()
        Membership.objects.create(user=user, church=self.other, is_active=False)
        self.assertEqual(self.church_for(user, self.other)[0], self.first)

    def test_a_superuser_may_choose_any_church(self):
        boss = make_user(is_superuser=True, church=False)
        self.assertEqual(self.church_for(boss, self.other)[0], self.other)


class SeedChurchTests(TestCase):
    def test_a_new_church_gets_its_own_defaults(self):
        first_roles = Role.objects.filter(church=first_church()).count()
        church = make_church("Grace Chapel")
        roles = Role.objects.filter(church=church)
        self.assertEqual(
            sorted(roles.values_list("key", flat=True)),
            sorted(key for key, _, _ in DEFAULT_ROLES),
        )
        self.assertEqual(
            set(
                roles.get(key="church_member").permissions.values_list(
                    "codename", flat=True
                )
            ),
            {"view_worshipservice", "request_occasion"},
        )
        self.assertTrue(roles.get(key="administrator").permissions.exists())
        self.assertEqual(ThemeTag.objects.filter(church=church).count(), 30)
        template = ServiceTemplate.objects.get(church=church)
        self.assertEqual(template.slots.count(), 4)
        types = OccasionType.objects.filter(church=church)
        self.assertEqual(types.count(), 3)
        self.assertFalse(types.filter(is_active=True).exists())
        self.assertTrue(SuggestionSettings.objects.filter(church=church).exists())
        self.assertTrue(WorshipCheckSettings.objects.filter(church=church).exists())
        # The first church is left as it was.
        self.assertEqual(
            Role.objects.filter(church=first_church()).count(), first_roles
        )


class NamesArePerChurchTests(TestCase):
    def setUp(self):
        self.first = first_church()
        self.other = make_church("Grace Chapel")

    def test_two_churches_may_use_the_same_names(self):
        self.assertTrue(
            ThemeTag.objects.filter(church=self.other, name="Grace").exists()
        )
        self.assertTrue(
            ThemeTag.objects.filter(church=self.first, name="Grace").exists()
        )
        self.assertEqual(Role.objects.filter(title="Administrator").count(), 2)

    def test_a_repeated_list_name_is_a_form_error(self):
        from django.forms import modelform_factory

        form_class = modelform_factory(ThemeTag, fields=["name", "sort_order"])
        form = form_class(
            {"name": "Grace", "sort_order": 0},
            instance=ThemeTag(church=self.other),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("An item with this name already exists.", str(form.errors))

    def test_a_repeated_role_name_is_a_form_error_only_in_the_same_church(self):
        taken = RoleForm({"title": "Ushers"}, church=self.first)
        self.assertTrue(taken.is_valid())
        taken.save()
        again = RoleForm({"title": "ushers"}, church=self.first)
        self.assertFalse(again.is_valid())
        self.assertTrue(RoleForm({"title": "Ushers"}, church=self.other).is_valid())


class AccountsPagesShowOneChurchTests(TestCase):
    def setUp(self):
        self.other = make_church("Grace Chapel")
        self.client.force_login(make_administrator())

    def test_only_this_churchs_roles(self):
        theirs = Role.objects.get(church=self.other, key="team_member")
        response = self.client.get(reverse("accounts:role_list"))
        self.assertNotIn(theirs, response.context["object_list"])
        url = reverse("accounts:role_update", kwargs={"pk": theirs.pk})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_only_this_churchs_users(self):
        outsider = make_user(church=self.other, username="outsider")
        response = self.client.get(reverse("accounts:user_list"))
        self.assertNotContains(response, "outsider")
        for name in ("accounts:user_update", "accounts:user_password"):
            url = reverse(name, kwargs={"pk": outsider.pk})
            self.assertEqual(self.client.get(url).status_code, 404, name)

    def test_adding_a_user_makes_a_membership_here(self):
        role = Role.objects.get(church=first_church(), key="team_member")
        self.client.post(
            reverse("accounts:user_create"),
            {
                "username": "newbie",
                "password1": "a-Long-pass-8472",
                "password2": "a-Long-pass-8472",
                "roles": [role.pk],
            },
        )
        membership = Membership.objects.get(user__username="newbie")
        self.assertEqual(membership.church, first_church())
        self.assertEqual(list(membership.roles.all()), [role])


class NoChurchTests(TestCase):
    """A signed-in person with no active Membership (decision 0014)."""

    def test_church_pages_say_so_and_own_account_pages_open(self):
        self.client.force_login(make_user(church=False))
        for url in (reverse("home"), reverse("worship:home")):
            response = self.client.get(url)
            self.assertTemplateUsed(response, "church/no_church.html")
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)

    def test_an_inactive_membership_counts_as_none(self):
        user = make_user()
        user.memberships.update(is_active=False)
        self.client.force_login(user)
        response = self.client.get(reverse("home"))
        self.assertTemplateUsed(response, "church/no_church.html")
