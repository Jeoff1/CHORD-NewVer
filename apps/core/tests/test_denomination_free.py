"""Guard for decision 0001: CHORD never records or mentions a denomination.

Scans the project's own code, templates, static files and seed data. If this
fails, turn the church difference into a setting instead of naming a
denomination (see docs/CHORD-Vault/02-Architecture/Decisions/0001).
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase

BANNED = re.compile(
    r"\b(denominations?|denominational|traditions?|religions?)\b", re.IGNORECASE
)
SCANNED_DIRS = ("apps", "config", "templates", "static")
SKIPPED_DIRS = {"__pycache__", "vendor"}
SUFFIXES = {".py", ".html", ".txt", ".json", ".js", ".css", ".csv", ".yaml", ".yml"}
BASE_DIR = Path(settings.BASE_DIR)
THIS_FILE = Path(__file__).resolve()


def scanned_files():
    for top in SCANNED_DIRS:
        for path in (BASE_DIR / top).rglob("*"):
            if (
                path.suffix in SUFFIXES
                and path.is_file()
                and not SKIPPED_DIRS.intersection(path.parts)
                and path.resolve() != THIS_FILE
            ):
                yield path


class DenominationFreeTests(SimpleTestCase):
    def test_scan_covers_project_code(self):
        scanned = {p.relative_to(BASE_DIR).as_posix() for p in scanned_files()}
        self.assertIn("config/settings.py", scanned)
        self.assertIn("templates/base.html", scanned)

    def test_no_denomination_wording(self):
        hits = [
            f"{path.relative_to(BASE_DIR)}:{number}: {line.strip()}"
            for path in scanned_files()
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            )
            if BANNED.search(line)
        ]
        self.assertEqual(hits, [], "Denomination wording found:\n" + "\n".join(hits))


class PlatformFieldsAndFormsTests(TestCase):
    """Phase 9B: the platform's own fields and forms, as they run, never
    ask about or name a denomination (decision 0001)."""

    @staticmethod
    def words_of_field(field):
        found = [
            str(getattr(field, "name", "")),
            str(getattr(field, "verbose_name", "") or ""),
            str(getattr(field, "label", "") or ""),
            str(getattr(field, "help_text", "") or ""),
        ]
        for choice in getattr(field, "choices", None) or []:
            found.extend(str(part) for part in choice)
        return found

    def assert_clean(self, where, texts):
        hits = [text for text in texts if BANNED.search(text)]
        self.assertEqual(hits, [], where)

    def test_the_new_model_fields(self):
        from apps.accounts.models import Membership, Role
        from apps.announcements.models import Announcement
        from apps.church.models import ChurchProfile
        from apps.occasions.models import OccasionType

        for model in (ChurchProfile, Membership, Role, OccasionType, Announcement):
            for field in model._meta.get_fields():
                with self.subTest(model=model.__name__, field=field.name):
                    self.assert_clean(field.name, self.words_of_field(field))

    def test_the_new_forms(self):
        from apps.accounts.forms import AddExistingAccountForm, SignUpForm
        from apps.church.forms import (
            ChurchDetailsForm,
            ChurchHomepageForm,
            ChurchRegistrationForm,
            ModulesForm,
        )
        from apps.core.testing import first_church
        from apps.occasions.urls import TYPES_LIST

        church = first_church()
        forms = [
            ChurchRegistrationForm(),
            SignUpForm(),
            AddExistingAccountForm(church=church),
            ChurchDetailsForm(instance=church),
            ChurchHomepageForm(instance=church),
            ModulesForm(instance=church),
            TYPES_LIST.get_form_class()(),
        ]
        for form in forms:
            for name, field in form.fields.items():
                with self.subTest(form=type(form).__name__, field=name):
                    self.assert_clean(name, [name, *self.words_of_field(field)])

    def test_the_new_pages(self):
        from django.urls import reverse

        from apps.core.testing import complete_setup, make_administrator, make_user

        complete_setup()
        for url in (reverse("churches:register"), reverse("accounts:login")):
            self.assert_clean(url, [self.client.get(url).content.decode()])
        self.client.force_login(make_administrator())
        for url in (
            reverse("churches:register"),
            reverse("church:settings", kwargs={"section": "homepage"}),
            reverse("church:settings", kwargs={"section": "modules"}),
            reverse("occasions:types_create"),
            reverse("accounts:user_add_existing"),
        ):
            self.assert_clean(url, [self.client.get(url).content.decode()])
        self.client.force_login(make_user(church=False))
        self.assert_clean("home", [self.client.get(reverse("home")).content.decode()])

    def test_what_a_new_church_starts_with(self):
        from apps.accounts.models import Role
        from apps.core.testing import make_church
        from apps.occasions.models import OccasionType
        from apps.songs.models import ThemeTag
        from apps.worship.models import ServiceTemplate, TemplateSlot

        church = make_church("Grace Chapel")
        texts = [church.name, church.slug]
        texts += [
            f"{r.title} {r.description}" for r in Role.objects.filter(church=church)
        ]
        texts += [f"{t.name} {t.keywords}" for t in ThemeTag.objects.for_church(church)]
        texts += [
            f"{t.name} {t.description}"
            for t in ServiceTemplate.objects.for_church(church)
        ]
        texts += [s.name for s in TemplateSlot.objects.for_church(church)]
        texts += [
            f"{t.name} {t.description}" for t in OccasionType.objects.for_church(church)
        ]
        self.assert_clean("seeded rows", texts)
