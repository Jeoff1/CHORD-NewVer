"""The Members list (Phase 9A, A7, part 3): one primary button, the rest
under More, tabs, one filter row and the columns."""

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.testing import complete_setup, make_administrator, make_member, make_user

LIST = reverse("members:list")
VIEWER = ["members.view_member"]


# The Member Directory is retired (settings.RETIRED_MODULES); its tests
# keep the kept code working, for the day it comes back.
@override_settings(RETIRED_MODULES=())
class MembersScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.ana = make_member(first_name="Ana", phone="0917 000 0001")
        account = make_user()
        self.ben = make_member(first_name="Ben", user=account)

    def test_the_administrator_gets_add_and_every_more_item(self):
        self.client.force_login(make_administrator())
        page = self.client.get(LIST)
        self.assertContains(page, ">Add member</a>")
        self.assertContains(page, ">More</button>")
        for text in (
            "Import from CSV",
            "Export CSV",
            "Create accounts",
            "Members settings",
        ):
            with self.subTest(text):
                self.assertContains(page, text)
        # No tab bar: the sidebar holds the directory and Households.
        self.assertNotContains(page, 'aria-label="Members sections"')
        self.assertContains(page, 'class="chord-sb__sublink is-active"')
        self.assertContains(page, ">Households</a>")

    def test_a_viewer_gets_no_more_menu(self):
        self.client.force_login(make_user(perms=VIEWER))
        page = self.client.get(LIST)
        self.assertNotContains(page, ">More</button>")
        self.assertNotContains(page, "Add member")
        self.assertNotContains(page, ">Households</a>")

    def test_moved_actions_still_need_their_permission(self):
        self.client.force_login(make_user(perms=VIEWER))
        for name in (
            "members:import",
            "members:export",
            "members:accounts",
            "members:status_list",
        ):
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_columns_and_private_details(self):
        self.client.force_login(make_user(perms=VIEWER))
        page = self.client.get(LIST)
        self.assertContains(page, ">Can sign in</th>")
        self.assertNotContains(page, ">Phone</th>")
        self.assertNotContains(page, "0917 000 0001")
        self.assertNotContains(page, ">Email</th>")
        content = page.content.decode()
        ben = content[content.index(">Tester, Ben") :]
        self.assertIn("<td>Yes</td>", ben[:600])
        self.client.force_login(
            make_user(perms=VIEWER + ["members.view_private_details"])
        )
        page = self.client.get(LIST)
        self.assertContains(page, ">Phone</th>")
        self.assertContains(page, "0917 000 0001")
        self.assertContains(page, 'placeholder="Name, phone or email"')

    def test_the_filter_row(self):
        self.ana.archived_at = "2026-01-01T00:00:00Z"
        self.ana.save()
        self.client.force_login(make_user(perms=VIEWER))
        names = lambda **params: [  # noqa: E731
            m.first_name for m in self.client.get(LIST, params).context["object_list"]
        ]
        self.assertEqual(names(), ["Ben"])
        self.assertEqual(sorted(names(show="all")), ["Ana", "Ben"])
        self.assertEqual(names(q="Ben"), ["Ben"])
        page = self.client.get(LIST)
        self.assertContains(page, ">Show archived</label>")
        self.assertContains(page, ">Filter</button>")
