import csv
import io
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.core.custom_fields import FieldType
from apps.core.testing import complete_setup, make_member, make_user
from apps.members import services
from apps.members.models import Household, Member, MemberField

IMPORTER = ["members.view_member", "members.import_member"]
PRIVATE = ["members.view_private_details"]


def csv_file(text, encoding="utf-8", name="members.csv"):
    return SimpleUploadedFile(name, text.encode(encoding), content_type="text/csv")


GOOD_AND_BAD = """First name,Last name,Birth date,Email,Status,Household,Role in household,Favourite colour
Jose,Santos,1970-05-01,jose@example.com,Member,Santos Family,Head,blue
Maria,Santos,03/15/1972,,,Santos Family,Spouse,
Pia,Reyes,31/31/1999,,Member,,,
Leo,Cruz,,,Wanderer,,,
,Nameless,,,,,,
Ana,Lim,,,,,Child,
Jose,Santos,1970-05-01,,,,,
"""


class ImportTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.user = make_user(perms=IMPORTER + PRIVATE)
        self.client.force_login(self.user)

    def upload(self, text, **kwargs):
        return self.client.post(
            reverse("members:import"), {"file": csv_file(text, **kwargs)}
        )

    def preview(self):
        return self.client.get(reverse("members:import_preview"))


class ImportFlowTests(ImportTestCase):
    def test_needs_permission(self):
        self.client.force_login(make_user(perms=["members.view_member"]))
        self.assertEqual(self.client.get(reverse("members:import")).status_code, 403)

    def test_preview_saves_nothing_and_reports_each_problem(self):
        response = self.upload(GOOD_AND_BAD)
        self.assertRedirects(response, reverse("members:import_preview"))
        response = self.preview()
        self.assertFalse(Member.objects.exists())

        check = response.context["check"]
        self.assertEqual([r.name for r in check.ready], ["Jose Santos", "Maria Santos"])
        problems = {r.number: " ".join(r.problems) for r in check.with_problems}
        self.assertIn("isn't a date", problems[4])
        self.assertIn("Wanderer", problems[5])
        self.assertIn("First name", problems[6])
        self.assertIn("give a household", problems[7])
        self.assertIn("duplicate", problems[8])  # repeats line 2
        self.assertEqual(check.ignored_columns, ["Favourite colour"])
        self.assertContains(response, "Favourite colour")

    def test_import_creates_ready_rows_households_and_audit(self):
        self.upload(GOOD_AND_BAD)
        response = self.client.post(reverse("members:import_preview"))
        self.assertRedirects(response, reverse("members:list"))

        jose = Member.objects.get(first_name="Jose")
        maria = Member.objects.get(first_name="Maria")
        self.assertEqual(Member.objects.count(), 2)
        self.assertEqual(jose.household, maria.household)
        self.assertEqual(Household.objects.get().name, "Santos Family")
        self.assertEqual(maria.relationship.name, "Spouse")
        self.assertEqual(maria.status.name, "Member")  # blank status → default
        self.assertEqual(maria.birth_date.isoformat(), "1972-03-15")
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditEvent.Action.CREATED).count(), 3
        )
        self.assertNotIn("members_import", self.client.session)

    def test_duplicate_of_existing_member_is_not_imported(self):
        make_member(first_name="Jose", last_name="Santos", email="jose@example.com")
        self.upload("First name,Last name,Email\nJose,Santos,JOSE@example.com\n")
        check = self.preview().context["check"]
        self.assertEqual(check.ready, [])
        self.assertIn("duplicate", check.with_problems[0].problems[0])

    def test_problem_rows_download(self):
        self.upload(GOOD_AND_BAD)
        response = self.client.get(reverse("members:import_problems"))
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0][0], "Line")
        self.assertEqual(rows[0][-1], "Problems")
        self.assertEqual([row[0] for row in rows[1:]], ["4", "5", "6", "7", "8"])

    def test_missing_name_column_blocks_import(self):
        self.upload("Given,Family\nJose,Santos\n")
        response = self.preview()
        self.assertContains(response, "has no First name or Last name column")
        self.client.post(reverse("members:import_preview"))
        self.assertFalse(Member.objects.exists())

    def test_start_over_clears_the_check(self):
        self.upload(GOOD_AND_BAD)
        self.client.post(reverse("members:import_cancel"))
        self.assertRedirects(self.preview(), reverse("members:import"))


class ImportFileTests(ImportTestCase):
    def test_excel_style_files_are_read(self):
        self.upload("﻿First name,Last name\nJosé,Peña\n")
        self.assertEqual(self.preview().context["check"].ready[0].name, "José Peña")
        self.upload("First name,Last name\nJosé,Peña\n", encoding="cp1252")
        self.assertEqual(self.preview().context["check"].ready[0].name, "José Peña")

    def test_unusable_files_are_explained(self):
        response = self.upload("")  # Django refuses an empty upload itself
        self.assertContains(response, "empty")
        response = self.upload(" \r\n")
        self.assertContains(response, "The file is empty.")
        response = self.upload("First name,Last name\n,\n")
        self.assertContains(response, "no rows to import")
        with mock.patch.object(services, "MAX_IMPORT_ROWS", 2):
            response = self.upload("First name,Last name\nA,B\nC,D\nE,F\n")
        self.assertContains(response, "more than 2 rows")

    def test_custom_fields_are_imported(self):
        MemberField.objects.create(
            label="Baptized", field_type=FieldType.YES_NO, sort_order=1
        )
        MemberField.objects.create(
            label="Size", field_type=FieldType.CHOICE, choices="S\nM", sort_order=2
        )
        self.upload(
            "First name,Last name,Baptized,Size\nAna,Lim,yes,m\nBo,Go,maybe,XL\n"
        )
        check = self.preview().context["check"]
        self.assertEqual(len(check.ready), 1)
        self.assertEqual(len(check.with_problems[0].problems), 2)
        self.client.post(reverse("members:import_preview"))
        self.assertEqual(
            Member.objects.get().custom_data, {"baptized": True, "size": "M"}
        )

    def test_without_private_permission_private_columns_are_ignored(self):
        self.client.force_login(make_user(perms=IMPORTER))
        self.upload("First name,Last name,Birth date\nAna,Lim,1990-01-01\n")
        check = self.preview().context["check"]
        self.assertEqual(check.ignored_columns, ["Birth date"])
        self.client.post(reverse("members:import_preview"))
        self.assertIsNone(Member.objects.get().birth_date)


class ExportTests(TestCase):
    def setUp(self):
        complete_setup()
        MemberField.objects.create(label="Allergies", is_private=True)
        MemberField.objects.create(label="Shirt size")
        make_member(
            first_name="Ana",
            last_name="Lim",
            email="ana@example.com",
            custom_data={"allergies": "Nuts", "shirt_size": "M"},
        )
        make_member(first_name="Ben", last_name="Go")

    def export(self, perms, **params):
        self.client.force_login(make_user(perms=["members.view_member", *perms]))
        response = self.client.get(reverse("members:export"), params)
        if response.status_code != 200:
            return response.status_code
        return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))

    def test_needs_permission(self):
        self.assertEqual(self.export([]), 403)

    def test_private_columns_need_private_permission(self):
        rows = self.export(["members.export_member"])
        self.assertNotIn("Email", rows[0])
        self.assertNotIn("Allergies", rows[0])
        self.assertIn("Shirt size", rows[0])
        rows = self.export(["members.export_member", *PRIVATE])
        self.assertIn("Email", rows[0])
        self.assertIn("Nuts", rows[1] + rows[2])

    def test_export_follows_the_list_filters(self):
        rows = self.export(["members.export_member"], q="Ana")
        self.assertEqual(len(rows), 2)

    def test_export_can_be_imported_again(self):
        rows = self.export(["members.export_member", *PRIVATE])
        Member.objects.all().delete()
        text = "\n".join(",".join(f'"{c}"' for c in row) for row in rows)
        self.client.force_login(make_user(perms=IMPORTER + PRIVATE))
        self.client.post(reverse("members:import"), {"file": csv_file(text)})
        check = self.client.get(reverse("members:import_preview")).context["check"]
        self.assertEqual(len(check.ready), 2)
        self.assertEqual(check.ignored_columns, [])

    def test_template_has_the_columns(self):
        self.client.force_login(make_user(perms=IMPORTER))
        response = self.client.get(reverse("members:import_template"))
        header = response.content.decode("utf-8-sig")
        self.assertIn('"First name"', header)
        self.assertNotIn("Birth date", header)
