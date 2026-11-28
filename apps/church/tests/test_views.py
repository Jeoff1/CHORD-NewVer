import os
import shutil
import tempfile
from io import BytesIO
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.audit.models import AuditEvent
from apps.church.models import ChurchProfile
from apps.core.testing import (
    complete_setup,
    first_church,
    make_administrator,
    make_user,
)

TEMP_MEDIA = tempfile.mkdtemp()


def image_file(name="logo.png", size=(10, 10), noise=False):
    if noise:
        image = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
    else:
        image = Image.new("RGB", size, "white")
    buffer = BytesIO()
    image.save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def details_data(**overrides):
    data = {
        "name": "Grace Community Church",
        "address": "1 Hill Road",
        "phone": "",
        "email": "office@example.com",
        "website": "",
        "currency": "php",
        "time_zone": "Asia/Manila",
    }
    data.update(overrides)
    return data


class DashboardTests(TestCase):
    def test_signing_in_opens_the_dashboard_not_the_setup_wizard(self):
        # No setup wizard any more (owner, 27 Nov 2026): a church whose
        # details pass registration's checks is marked set up on arrival.
        self.client.force_login(make_administrator())
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        first_church().refresh_from_db()
        self.assertTrue(first_church().setup_completed)
        self.assertNotContains(response, "need checking")

    def test_details_that_fail_the_checks_show_a_notice_instead(self):
        with mock.patch(
            "apps.church.registration.setup_requirements_met", return_value=False
        ):
            self.client.force_login(make_administrator())
            response = self.client.get(reverse("home"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "need checking before it can be listed")
            self.assertContains(
                response, reverse("church:settings", kwargs={"section": "details"})
            )
            self.client.force_login(make_user())
            response = self.client.get(reverse("home"))
            self.assertContains(response, "An administrator can fix them in Settings.")
        self.assertFalse(first_church().setup_completed)

    def test_shows_switched_on_modules_only(self):
        complete_setup(disabled_modules=["announcements"])
        self.client.force_login(make_administrator())
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Worship")
        self.assertNotContains(response, "Announcements")
        # Settings sits at the foot of the sidebar (dashboard redesign).
        self.assertContains(response, 'title="Settings"')

    def test_plain_users_gear_opens_their_account_settings(self):
        # Everyone has Settings › Personal (Phase 9A, A7); Account comes first
        # since UI/UX Phase 2.
        complete_setup()
        self.client.force_login(make_user())
        self.assertContains(
            self.client.get(reverse("home")),
            f'href="{reverse("accounts:profile")}" title="Settings"',
        )


class SetupWizardTests(TestCase):
    def setUp(self):
        self.client.force_login(make_administrator())

    def url(self, section):
        return reverse("church:setup", kwargs={"section": section})

    def test_full_wizard(self):
        response = self.client.get(self.url("details"))
        self.assertContains(response, "Step 1 of 3")

        response = self.client.post(self.url("details"), details_data())
        self.assertRedirects(response, self.url("modules"))
        response = self.client.post(self.url("modules"), {"enabled": ["worship"]})
        self.assertRedirects(response, self.url("homepage"))
        response = self.client.post(
            self.url("homepage"),
            {"about": "We meet on Sundays.", "show_in_directory": ""},
        )
        self.assertRedirects(response, reverse("home"))

        profile = first_church()
        self.assertTrue(profile.setup_completed)
        self.assertEqual(profile.name, "Grace Community Church")
        self.assertEqual(
            sorted(profile.disabled_modules), ["announcements", "occasions", "teams"]
        )
        self.assertEqual(profile.about, "We meet on Sundays.")
        self.assertFalse(profile.show_in_directory)
        self.assertEqual(AuditEvent.objects.count(), 3)

    def test_finished_wizard_redirects_to_settings(self):
        complete_setup()
        response = self.client.get(self.url("modules"))
        self.assertRedirects(
            response, reverse("church:settings", kwargs={"section": "modules"})
        )

    def test_unknown_section_is_404(self):
        self.assertEqual(self.client.get(self.url("doctrine")).status_code, 404)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SettingsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        complete_setup()
        self.admin = make_administrator()
        self.client.force_login(self.admin)

    def url(self, section):
        return reverse("church:settings", kwargs={"section": section})

    def test_requires_permission(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(self.url("details")).status_code, 403)

    def test_every_section_renders(self):
        details = self.client.get(self.url("details"))
        self.assertContains(details, 'name="address"')
        modules = self.client.get(self.url("modules"))
        # Worship, the Praise Team, Occasions and Announcements; the retired
        # Member Directory isn't listed.
        self.assertContains(modules, 'role="switch"', count=4)
        self.assertContains(modules, " checked", count=4)
        self.assertContains(modules, "Needs Worship switched on.")

    def test_the_praise_team_sits_under_worship(self):
        # The owner, 28 Nov 2026: Teams shows as the Praise Team under
        # Worship, with its own switch.
        page = self.client.get(self.url("modules")).content.decode()
        worship = page.index('id="module-worship"')
        team = page.index('id="module-teams"')
        occasions = page.index('id="module-occasions"')
        self.assertLess(worship, team)
        self.assertLess(team, occasions)
        row = page[page.rindex("<label", 0, team) : team]
        self.assertIn("chord-module--nested", row)
        self.assertIn(">Praise Team<", page[team : team + 600])
        self.assertNotIn('value="members"', page)

    def test_switching_the_praise_team_off_keeps_worship(self):
        self.client.post(
            self.url("modules"), {"enabled": ["worship", "occasions", "announcements"]}
        )
        self.assertEqual(first_church().disabled_modules, ["teams"])

    def test_settings_home_opens_details(self):
        response = self.client.get(reverse("church:settings_home"))
        self.assertRedirects(response, self.url("details"))

    def test_saving_details_is_audited(self):
        response = self.client.post(self.url("details"), details_data())
        self.assertRedirects(response, self.url("details"))
        event = AuditEvent.objects.get()
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(
            event.changes["Church name"], ["My Church", "Grace Community Church"]
        )
        self.assertNotIn("Time zone", event.changes)

    def test_no_website_currency_or_time_zone(self):
        # The owner, 28 Nov 2026. Saved values are kept; the time zone still
        # comes from the browser when a church registers.
        ChurchProfile.objects.update(website="https://grace.example")
        details = self.client.get(self.url("details"))
        for name in ("website", "currency", "time_zone"):
            self.assertNotContains(details, f'name="{name}"')
        self.client.post(self.url("details"), details_data(currency="PESO"))
        profile = first_church()
        self.assertEqual(profile.name, "Grace Community Church")
        self.assertEqual(profile.currency, "PHP")
        self.assertEqual(profile.website, "https://grace.example")

    def test_logo_upload(self):
        data = details_data(logo=image_file())
        self.client.post(self.url("details"), data)
        profile = first_church()
        # A random name in the public church folder: nothing of the file
        # the person chose, nor any private path (Phase 9B).
        self.assertRegex(profile.logo.name, r"^church/[0-9a-f]{32}\.png$")
        self.assertTrue(profile.logo.url.startswith(settings.MEDIA_URL + "church/"))
        self.assertNotIn("logo", profile.logo.url)
        self.assertNotIn("protected", profile.logo.url)
        self.assertContains(self.client.get(reverse("home")), profile.logo.url)

    def test_logo_over_2_mb_is_rejected(self):
        data = details_data(logo=image_file(size=(1000, 1000), noise=True))
        response = self.client.post(self.url("details"), data)
        self.assertContains(response, "2 MB or smaller")

    def test_there_is_no_labels_page(self):
        # The owner, 28 Nov 2026: CHORD's default words, not the church's.
        self.assertEqual(self.client.get(self.url("labels")).status_code, 404)
        self.assertNotContains(self.client.get(self.url("details")), ">Labels<")

    def test_switching_modules_off_and_on(self):
        self.client.post(self.url("modules"), {"enabled": ["announcements"]})
        profile = first_church()
        self.assertEqual(len(profile.disabled_modules), 3)
        self.assertNotContains(self.client.get(reverse("home")), "Worship")

        everything = ["worship", "teams", "occasions", "announcements"]
        self.client.post(self.url("modules"), {"enabled": everything})
        self.assertEqual(first_church().disabled_modules, [])

    def test_stale_module_codes_do_not_break_the_audit_trail(self):
        ChurchProfile.objects.update(disabled_modules=["giving"])
        self.client.post(self.url("modules"), {"enabled": ["worship"]})
        self.assertEqual(
            sorted(first_church().disabled_modules),
            ["announcements", "occasions", "teams"],
        )


class LocationPickerTests(TestCase):
    """The church address's location picker (the owner, 28 Nov 2026): under
    the address at registration and in Church details, hidden until its
    script runs, and only the address text is posted."""

    def assert_picker_for(self, page, field_id):
        self.assertContains(
            page, f'data-location-picker data-target="{field_id}" hidden'
        )
        self.assertContains(page, "Use my current location")
        self.assertContains(page, "Pick on the map")
        self.assertContains(page, "vendor/leaflet-1.9.4/leaflet.js")
        self.assertContains(page, "church/location_picker.js")
        self.assertContains(page, "CHORD saves just the address text.")

    def test_registration_has_it_under_the_address(self):
        page = self.client.get(reverse("churches:register"))
        self.assert_picker_for(page, "id_church-address")
        content = page.content.decode()
        self.assertLess(
            content.index('name="church-address"'),
            content.index("data-location-picker"),
        )

    def test_church_details_has_it_under_the_address(self):
        complete_setup()
        self.client.force_login(make_administrator())
        page = self.client.get(
            reverse("church:settings", kwargs={"section": "details"})
        )
        self.assert_picker_for(page, "id_address")
        content = page.content.decode()
        address = content.index('name="address"')
        picker = content.index("data-location-picker")
        self.assertLess(address, picker)
        self.assertLess(picker, content.index('name="phone"'))

    def test_no_coordinates_are_saved(self):
        complete_setup()
        self.client.force_login(make_administrator())
        url = reverse("church:settings", kwargs={"section": "details"})
        self.client.post(url, details_data(latitude="14.6", longitude="121.0"))
        profile = first_church()
        self.assertEqual(profile.address, "1 Hill Road")
        self.assertFalse(hasattr(profile, "latitude"))

    def test_the_map_says_which_site_it_comes_from(self):
        # OpenStreetMap refuses tiles and lookups without a Referer, and
        # Django's "Referrer-Policy: same-origin" would drop it: the script
        # asks for the site's origin only (28 Nov 2026).
        from django.contrib.staticfiles import finders

        with open(
            finders.find("church/location_picker.js"), encoding="utf-8"
        ) as script:
            source = script.read()
        self.assertIn('REFERRER = "strict-origin-when-cross-origin"', source)
        self.assertEqual(source.count("referrerPolicy: REFERRER"), 2)
