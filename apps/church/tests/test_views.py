import os
import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.audit.models import AuditEvent
from apps.church.models import ChurchProfile
from apps.core.testing import complete_setup, make_administrator, make_user

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


def labels_data(**overrides):
    data = {
        "member__singular": "Member",
        "member__plural": "Members",
        "worship_service__singular": "Worship Service",
        "worship_service__plural": "Worship Services",
        "sermon__singular": "Homily",
        "sermon__plural": "Homilies",
        "lineup__singular": "Lineup",
        "lineup__plural": "Lineups",
        "pastor__singular": "Pastor",
        "pastor__plural": "Pastors",
    }
    data.update(overrides)
    return data


class DashboardTests(TestCase):
    def test_administrator_is_sent_to_setup_until_it_is_done(self):
        self.client.force_login(make_administrator())
        response = self.client.get(reverse("home"))
        self.assertRedirects(
            response, reverse("church:setup", kwargs={"section": "details"})
        )

    def test_other_users_see_a_notice_while_setup_is_unfinished(self):
        self.client.force_login(make_user())
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Church setup isn't finished yet")

    def test_shows_switched_on_modules_only(self):
        complete_setup(disabled_modules=["announcements"])
        self.client.force_login(make_administrator())
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Worship")
        self.assertNotContains(response, "Announcements")
        self.assertContains(response, "Administration")

    def test_plain_user_has_no_administration_menu(self):
        complete_setup()
        self.client.force_login(make_user())
        self.assertNotContains(self.client.get(reverse("home")), "Administration")


class SetupWizardTests(TestCase):
    def setUp(self):
        self.client.force_login(make_administrator())

    def url(self, section):
        return reverse("church:setup", kwargs={"section": section})

    def test_full_wizard(self):
        response = self.client.get(self.url("details"))
        self.assertContains(response, "Step 1 of 3")

        response = self.client.post(self.url("details"), details_data())
        self.assertRedirects(response, self.url("labels"))
        response = self.client.post(self.url("labels"), labels_data())
        self.assertRedirects(response, self.url("modules"))
        response = self.client.post(
            self.url("modules"), {"enabled": ["members", "worship"]}
        )
        self.assertRedirects(response, reverse("home"))

        profile = ChurchProfile.load()
        self.assertTrue(profile.setup_completed)
        self.assertEqual(profile.name, "Grace Community Church")
        self.assertEqual(profile.currency, "PHP")
        self.assertEqual(profile.label_set.get("sermon"), "Homily")
        self.assertEqual(
            sorted(profile.disabled_modules), ["announcements", "occasions", "teams"]
        )
        self.assertEqual(AuditEvent.objects.count(), 3)

    def test_finished_wizard_redirects_to_settings(self):
        complete_setup()
        response = self.client.get(self.url("labels"))
        self.assertRedirects(
            response, reverse("church:settings", kwargs={"section": "labels"})
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
        self.assertContains(details, 'name="currency"')
        labels = self.client.get(self.url("labels"))
        self.assertContains(labels, "e.g. Sermon, Homily, Message")
        self.assertContains(labels, 'name="sermon__plural"')
        modules = self.client.get(self.url("modules"))
        self.assertContains(modules, 'role="switch"', count=5)
        self.assertContains(modules, " checked", count=5)
        self.assertContains(modules, "Needs Worship switched on.")

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

    def test_invalid_currency_is_rejected(self):
        response = self.client.post(self.url("details"), details_data(currency="PESO"))
        self.assertContains(response, "is-invalid")
        self.assertEqual(ChurchProfile.load().currency, "PHP")

    def test_logo_upload(self):
        data = details_data(logo=image_file())
        self.client.post(self.url("details"), data)
        profile = ChurchProfile.load()
        self.assertTrue(profile.logo.name.startswith("church/logo"))
        self.assertContains(self.client.get(reverse("home")), profile.logo.url)

    def test_logo_over_2_mb_is_rejected(self):
        data = details_data(logo=image_file(size=(1000, 1000), noise=True))
        response = self.client.post(self.url("details"), data)
        self.assertContains(response, "2 MB or smaller")

    def test_labels_change_module_names(self):
        self.client.post(
            self.url("labels"),
            labels_data(member__singular="Parishioner", member__plural="Parishioners"),
        )
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Parishioners")
        event = AuditEvent.objects.get()
        self.assertEqual(
            event.changes["Label: Member"],
            ["Member / Members", "Parishioner / Parishioners"],
        )

    def test_switching_modules_off_and_on(self):
        self.client.post(self.url("modules"), {"enabled": ["members"]})
        profile = ChurchProfile.load()
        self.assertEqual(len(profile.disabled_modules), 4)
        self.assertNotContains(self.client.get(reverse("home")), "Worship")

        everything = ["members", "worship", "teams", "occasions", "announcements"]
        self.client.post(self.url("modules"), {"enabled": everything})
        self.assertEqual(ChurchProfile.load().disabled_modules, [])

    def test_stale_module_codes_do_not_break_the_audit_trail(self):
        ChurchProfile.objects.update(disabled_modules=["giving"])
        self.client.post(self.url("modules"), {"enabled": ["members", "worship"]})
        self.assertEqual(
            sorted(ChurchProfile.load().disabled_modules),
            ["announcements", "occasions", "teams"],
        )
