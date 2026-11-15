import datetime
import shutil
import tempfile
from io import BytesIO

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.audit.models import AuditEvent
from apps.church.models import ChurchProfile
from apps.core.custom_fields import FieldType
from apps.core.testing import (
    close_file_response,
    complete_setup,
    make_administrator,
    make_member,
    make_user,
)
from apps.members.models import (
    Household,
    Member,
    MemberField,
    MembershipStatus,
    RelationshipType,
)

TEMP_PRIVATE = tempfile.mkdtemp()
VIEWER = ["members.view_member"]
EDITOR = ["members.view_member", "members.add_member", "members.change_member"]
PRIVATE = ["members.view_private_details"]


def png(name="me.png"):
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "blue").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def detail_url(member):
    return reverse("members:detail", kwargs={"public_id": member.public_id})


def member_data(**overrides):
    data = {
        "first_name": "Maria",
        "last_name": "Santos",
        "status": MembershipStatus.default().pk,
    }
    data.update(overrides)
    return data


class MemberTestCase(TestCase):
    def setUp(self):
        complete_setup()


class ListTests(MemberTestCase):
    def setUp(self):
        super().setUp()
        self.ana = make_member(first_name="Ana", email="ana@example.com")
        self.ben = make_member(first_name="Ben")

    def names(self, user, **params):
        self.client.force_login(user)
        response = self.client.get(reverse("members:list"), params)
        return [m.first_name for m in response.context["object_list"]]

    def test_needs_permission(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(reverse("members:list")).status_code, 403)

    def test_switched_off_module_is_404_even_with_permission(self):
        complete_setup(disabled_modules=["members"])
        self.client.force_login(make_administrator())
        self.assertEqual(self.client.get(reverse("members:list")).status_code, 404)
        self.assertTrue(Member.objects.filter(pk=self.ana.pk).exists())

    def test_contact_search_needs_private_permission(self):
        self.assertEqual(self.names(make_user(perms=VIEWER), q="ana@"), [])
        private_viewer = make_user(perms=VIEWER + PRIVATE)
        self.assertEqual(self.names(private_viewer, q="ana@"), ["Ana"])

    def test_email_column_needs_private_permission(self):
        self.client.force_login(make_user(perms=VIEWER))
        self.assertNotContains(self.client.get(reverse("members:list")), "ana@example")

    def test_archived_and_status_filters(self):
        self.ben.archived_at = datetime.datetime.now(datetime.UTC)
        self.ben.save()
        visitor = MembershipStatus.objects.get(name="Visitor")
        make_member(first_name="Vic", status=visitor)
        user = make_user(perms=VIEWER)
        self.assertEqual(self.names(user), ["Ana", "Vic"])
        self.assertEqual(self.names(user, show="archived"), ["Ben"])
        self.assertEqual(self.names(user, status=visitor.pk), ["Vic"])

    def test_module_name_follows_labels(self):
        complete_setup(
            labels={"member": {"singular": "Parishioner", "plural": "Parishioners"}}
        )
        self.client.force_login(make_user(perms=VIEWER))
        self.assertContains(
            self.client.get(reverse("members:list")),
            '<h1 class="h3 mb-0">Parishioners</h1>',
            html=False,
        )


class CreateAndEditTests(MemberTestCase):
    def test_create_uses_default_status_and_audits(self):
        self.client.force_login(make_user(perms=EDITOR + PRIVATE))
        response = self.client.get(reverse("members:create"))
        self.assertEqual(
            response.context["form"]["status"].value(), MembershipStatus.default().pk
        )
        response = self.client.post(
            reverse("members:create"),
            member_data(birth_date="1990-04-02", email="maria@example.com"),
        )
        member = Member.objects.get()
        self.assertRedirects(response, detail_url(member))
        self.assertEqual(member.birth_date, datetime.date(1990, 4, 2))
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.CREATED)
        self.assertEqual(event.changes["Last name"], ["", "Santos"])

    def test_custom_fields_are_saved_and_audited(self):
        size = MemberField.objects.create(
            label="Shirt size", field_type=FieldType.CHOICE, choices="S\nM\nL"
        )
        baptized = MemberField.objects.create(
            label="Baptized", field_type=FieldType.YES_NO
        )
        self.client.force_login(make_user(perms=EDITOR))
        self.client.post(
            reverse("members:create"),
            member_data(**{size.form_name: "M", baptized.form_name: "yes"}),
        )
        member = Member.objects.get()
        self.assertEqual(member.custom_data, {"shirt_size": "M", "baptized": True})
        self.assertEqual(AuditEvent.objects.get().changes["Baptized"], ["", "Yes"])

    def test_editor_without_private_permission_keeps_private_values(self):
        allergy = MemberField.objects.create(label="Allergies", is_private=True)
        member = make_member(
            first_name="Ana",
            birth_date=datetime.date(1990, 1, 1),
            email="ana@example.com",
            custom_data={"allergies": "Peanuts"},
        )
        self.client.force_login(make_user(perms=EDITOR))
        form = self.client.get(
            reverse("members:update", kwargs={"public_id": member.public_id})
        ).context["form"]
        self.assertNotIn("birth_date", form.fields)
        self.assertNotIn(allergy.form_name, form.fields)

        self.client.post(
            reverse("members:update", kwargs={"public_id": member.public_id}),
            member_data(first_name="Anna", last_name=member.last_name),
        )
        member.refresh_from_db()
        self.assertEqual(member.first_name, "Anna")
        self.assertEqual(member.birth_date, datetime.date(1990, 1, 1))
        self.assertEqual(member.email, "ana@example.com")
        self.assertEqual(member.custom_data["allergies"], "Peanuts")

    def test_household_role_needs_a_household(self):
        self.client.force_login(make_user(perms=EDITOR))
        head = RelationshipType.objects.get(name="Head")
        response = self.client.post(
            reverse("members:create"), member_data(relationship=head.pk)
        )
        self.assertContains(response, "Choose a household first.")

    def test_inactive_status_is_not_offered_for_new_members(self):
        visitor = MembershipStatus.objects.get(name="Visitor")
        visitor.is_active = False
        visitor.save()
        self.client.force_login(make_user(perms=EDITOR))
        form = self.client.get(reverse("members:create")).context["form"]
        self.assertNotIn(visitor, form.fields["status"].queryset)

    def test_linked_account_can_only_be_linked_once(self):
        user = make_user()
        make_member(user=user)
        self.client.force_login(make_user(perms=EDITOR))
        form = self.client.get(reverse("members:create")).context["form"]
        self.assertNotIn(user, form.fields["user"].queryset)


class DetailPrivacyTests(MemberTestCase):
    def setUp(self):
        super().setUp()
        self.member = make_member(
            first_name="Ana",
            birth_date=datetime.date(1985, 6, 15),
            phone="0917 555 0101",
            address="12 Mango St.",
        )

    def test_viewer_without_private_permission_sees_no_private_details(self):
        self.client.force_login(make_user(perms=VIEWER))
        response = self.client.get(detail_url(self.member))
        self.assertContains(response, "Ana")
        for secret in ("Jun 15, 1985", "0917 555 0101", "12 Mango St."):
            self.assertNotContains(response, secret)

    def test_private_permission_shows_them(self):
        self.client.force_login(make_user(perms=VIEWER + PRIVATE))
        response = self.client.get(detail_url(self.member))
        for secret in ("Jun 15, 1985", "0917 555 0101", "12 Mango St."):
            self.assertContains(response, secret)

    def test_administrator_sees_recent_changes(self):
        admin = make_administrator()
        self.client.force_login(admin)
        self.client.post(
            reverse("members:archive", kwargs={"public_id": self.member.public_id}),
            {"archive": "1"},
        )
        self.assertContains(self.client.get(detail_url(self.member)), "Recent changes")


class OwnRecordTests(MemberTestCase):
    def test_linked_person_sees_own_private_details(self):
        user = make_user()
        make_member(user=user, first_name="Ana", phone="0917 555 0101")
        self.client.force_login(user)
        response = self.client.get(reverse("members:me"))
        self.assertContains(response, "0917 555 0101")
        self.assertNotContains(response, "Edit")

    def test_unlinked_account_gets_a_message(self):
        self.client.force_login(make_user())
        response = self.client.get(reverse("members:me"))
        self.assertContains(response, "linked to a member record")

    def test_own_record_does_not_open_other_records(self):
        user = make_user()
        make_member(user=user)
        other = make_member()
        self.client.force_login(user)
        self.assertEqual(self.client.get(detail_url(other)).status_code, 403)

    def test_menu_link_appears_only_when_linked(self):
        user = make_user()
        self.client.force_login(user)
        self.assertNotContains(self.client.get(reverse("home")), reverse("members:me"))
        make_member(user=user)
        self.assertContains(self.client.get(reverse("home")), reverse("members:me"))


class ArchiveTests(MemberTestCase):
    def test_archive_and_restore(self):
        member = make_member()
        url = reverse("members:archive", kwargs={"public_id": member.public_id})
        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(self.client.post(url, {"archive": "1"}).status_code, 403)

        self.client.force_login(make_user(perms=EDITOR))
        self.client.post(url, {"archive": "1"})
        member.refresh_from_db()
        self.assertTrue(member.is_archived)
        self.client.post(url, {"archive": "0"})
        member.refresh_from_db()
        self.assertFalse(member.is_archived)
        changes = [e.changes["Archived"] for e in AuditEvent.objects.order_by("pk")]
        self.assertEqual(changes, [["No", "Yes"], ["Yes", "No"]])

    def test_archive_needs_post(self):
        member = make_member()
        self.client.force_login(make_user(perms=EDITOR))
        url = reverse("members:archive", kwargs={"public_id": member.public_id})
        self.assertEqual(self.client.get(url).status_code, 405)


@override_settings(PRIVATE_MEDIA_ROOT=TEMP_PRIVATE)
class FileTests(MemberTestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_PRIVATE, ignore_errors=True)

    def test_photo_is_private_and_served_with_permission(self):
        self.client.force_login(make_user(perms=EDITOR))
        self.client.post(reverse("members:create"), member_data(photo=png()))
        member = Member.objects.get()
        self.assertTrue(member.photo.path.startswith(TEMP_PRIVATE))
        self.assertFalse(member.photo.path.startswith(str(settings.MEDIA_ROOT)))

        photo_url = reverse("members:photo", kwargs={"public_id": member.public_id})
        response = self.client.get(photo_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("inline", response["Content-Disposition"])
        close_file_response(response)

        self.client.force_login(make_user())
        self.assertEqual(self.client.get(photo_url).status_code, 403)

    def test_edit_page_links_current_photo_to_the_private_view(self):
        self.client.force_login(make_user(perms=EDITOR))
        self.client.post(reverse("members:create"), member_data(photo=png()))
        member = Member.objects.get()
        response = self.client.get(
            reverse("members:update", kwargs={"public_id": member.public_id})
        )
        self.assertContains(
            response, reverse("members:photo", kwargs={"public_id": member.public_id})
        )

    def test_private_custom_file_needs_private_permission(self):
        consent = MemberField.objects.create(
            label="Consent form", field_type=FieldType.FILE, is_private=True
        )
        self.client.force_login(make_user(perms=EDITOR + PRIVATE))
        self.client.post(
            reverse("members:create"),
            member_data(
                **{consent.form_name: SimpleUploadedFile("consent.pdf", b"%PDF")}
            ),
        )
        member = Member.objects.get()
        url = reverse(
            "members:file",
            kwargs={"public_id": member.public_id, "key": consent.key},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        close_file_response(response)

        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_disallowed_file_type_is_rejected(self):
        field = MemberField.objects.create(label="Form", field_type=FieldType.FILE)
        self.client.force_login(make_user(perms=EDITOR))
        response = self.client.post(
            reverse("members:create"),
            member_data(**{field.form_name: SimpleUploadedFile("x.html", b"<b>")}),
        )
        self.assertContains(response, "is-invalid")
        self.assertFalse(Member.objects.exists())

    def test_own_photo(self):
        user = make_user()
        self.client.force_login(make_user(perms=EDITOR))
        self.client.post(
            reverse("members:create"), member_data(photo=png(), user=user.pk)
        )
        self.client.force_login(user)
        response = self.client.get(reverse("members:my_photo"))
        self.assertEqual(response.status_code, 200)
        close_file_response(response)


class HouseholdTests(MemberTestCase):
    def test_create_list_and_detail(self):
        self.client.force_login(make_administrator())
        self.client.post(reverse("members:household_create"), {"name": "Santos Family"})
        household = Household.objects.get()
        head = RelationshipType.objects.get(name="Head")
        make_member(first_name="Jose", household=household, relationship=head)

        response = self.client.get(reverse("members:household_list"))
        self.assertEqual(response.context["object_list"][0].member_count, 1)
        response = self.client.get(
            reverse(
                "members:household_detail", kwargs={"public_id": household.public_id}
            )
        )
        self.assertContains(response, "Jose")
        self.assertContains(response, "Head")

    def test_edit_is_audited(self):
        household = Household.objects.create(name="Reyes Family")
        self.client.force_login(make_administrator())
        url = reverse(
            "members:household_update", kwargs={"public_id": household.public_id}
        )
        self.client.post(url, {"name": "Reyes-Cruz Family", "notes": ""})
        household.refresh_from_db()
        self.assertEqual(household.name, "Reyes-Cruz Family")
        self.assertEqual(
            AuditEvent.objects.get().changes["Name"],
            ["Reyes Family", "Reyes-Cruz Family"],
        )

    def test_detail_shows_household_mates(self):
        household = Household.objects.create(name="Reyes Family")
        ana = make_member(first_name="Ana", household=household)
        make_member(first_name="Ben", household=household)
        self.client.force_login(make_user(perms=VIEWER))
        self.assertContains(self.client.get(detail_url(ana)), "Ben")


class SettingListTests(MemberTestCase):
    def test_statuses_list_add_and_edit(self):
        self.client.force_login(make_administrator())
        response = self.client.get(reverse("members:status_list"))
        self.assertContains(response, "Regular Attendee")
        self.assertContains(response, "Household roles")  # settings tabs

        self.client.post(
            reverse("members:status_create"),
            {"name": "Catechumen", "sort_order": 5, "is_active": "on"},
        )
        status = MembershipStatus.objects.get(name="Catechumen")
        self.client.post(
            reverse("members:status_update", kwargs={"pk": status.pk}),
            {"name": "Seeker", "sort_order": 5, "is_active": "on"},
        )
        status.refresh_from_db()
        self.assertEqual(status.name, "Seeker")
        self.assertEqual(
            list(AuditEvent.objects.values_list("action", flat=True).order_by("pk")),
            ["created", "changed"],
        )

    def test_viewer_cannot_add(self):
        self.client.force_login(make_user(perms=["members.view_membershipstatus"]))
        response = self.client.get(reverse("members:status_list"))
        self.assertNotContains(response, "Add status")
        self.assertEqual(
            self.client.get(reverse("members:status_create")).status_code, 403
        )

    def test_field_definitions_need_choices_for_choice_type(self):
        self.client.force_login(make_administrator())
        response = self.client.post(
            reverse("members:field_create"),
            {"label": "Size", "field_type": "choice", "sort_order": 0},
        )
        self.assertContains(response, "Add at least one choice.")

    def test_switched_off_module_hides_settings(self):
        ChurchProfile.objects.update(disabled_modules=["members"])
        self.client.force_login(make_administrator())
        self.assertEqual(
            self.client.get(reverse("members:status_list")).status_code, 404
        )
