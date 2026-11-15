import datetime
import shutil
import tempfile
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings

from apps.core.custom_fields import FieldType, custom_values, parse_date
from apps.core.storage import StoredFile, private_storage
from apps.members.models import MemberField

TEMP_PRIVATE = tempfile.mkdtemp()


def field(field_type=FieldType.TEXT, **kwargs):
    kwargs.setdefault("label", "Sample")
    return MemberField(field_type=field_type, **kwargs)


class DefinitionTests(TestCase):
    def test_key_comes_from_label_and_stays_unique(self):
        first = MemberField.objects.create(label="Baptism date")
        second = MemberField.objects.create(label="Baptism date")
        self.assertEqual(first.key, "baptism_date")
        self.assertEqual(second.key, "baptism_date_2")

    def test_key_survives_renaming(self):
        definition = MemberField.objects.create(label="Shirt size")
        definition.label = "T-shirt size"
        definition.save()
        self.assertEqual(definition.key, "shirt_size")

    def test_choice_field_needs_choices(self):
        with self.assertRaises(ValidationError):
            field(FieldType.CHOICE, choices="  \n").full_clean()


class FormFieldTests(SimpleTestCase):
    def test_each_type_gets_a_suitable_form_field(self):
        expected = {
            FieldType.TEXT: forms.CharField,
            FieldType.LONG_TEXT: forms.CharField,
            FieldType.NUMBER: forms.DecimalField,
            FieldType.DATE: forms.DateField,
            FieldType.CHOICE: forms.ChoiceField,
            FieldType.YES_NO: forms.ChoiceField,
            FieldType.FILE: forms.FileField,
        }
        for field_type, form_class in expected.items():
            with self.subTest(field_type=field_type):
                definition = field(field_type, choices="A\nB")
                self.assertIsInstance(definition.form_field(), form_class)

    def test_removed_choice_stays_selectable_for_existing_value(self):
        definition = field(FieldType.CHOICE, choices="Small\nLarge")
        choices = dict(definition.form_field("Medium").choices)
        self.assertIn("Medium", choices)

    def test_values_round_trip(self):
        cases = [
            (FieldType.DATE, datetime.date(2024, 3, 5), "2024-03-05"),
            (FieldType.NUMBER, Decimal("12.5000"), "12.5"),
            (FieldType.YES_NO, "yes", True),
            (FieldType.YES_NO, "no", False),
            (FieldType.TEXT, "", None),
        ]
        for field_type, cleaned, stored in cases:
            with self.subTest(field_type=field_type, cleaned=cleaned):
                definition = field(field_type)
                self.assertEqual(definition.to_storage(cleaned), stored)
        self.assertEqual(
            field(FieldType.DATE).to_initial("2024-03-05"), datetime.date(2024, 3, 5)
        )
        self.assertEqual(field(FieldType.YES_NO).to_initial(False), "no")

    def test_display(self):
        self.assertEqual(field(FieldType.DATE).display("2024-03-05"), "Mar 5, 2024")
        self.assertEqual(field(FieldType.YES_NO).display(True), "Yes")
        self.assertEqual(field(FieldType.FILE).display("a/b/scan.pdf"), "scan.pdf")
        self.assertEqual(field().display(None), "")


class ParseTextTests(SimpleTestCase):
    def test_parses_each_type(self):
        self.assertEqual(field(FieldType.NUMBER).parse_text("1,250.50"), "1250.5")
        self.assertEqual(field(FieldType.DATE).parse_text("03/05/2024"), "2024-03-05")
        self.assertIs(field(FieldType.YES_NO).parse_text("Y"), True)
        self.assertIs(field(FieldType.YES_NO).parse_text("no"), False)
        choice = field(FieldType.CHOICE, choices="Small\nLarge")
        self.assertEqual(choice.parse_text("large"), "Large")
        self.assertIsNone(field().parse_text("  "))

    def test_rejects_text_that_does_not_fit(self):
        bad = [
            (field(FieldType.NUMBER), "lots"),
            (field(FieldType.DATE), "31/31/2024"),
            (field(FieldType.YES_NO), "maybe"),
            (field(FieldType.CHOICE, choices="Small"), "Huge"),
            (field(FieldType.FILE), "scan.pdf"),
            (field(required=True), ""),
        ]
        for definition, text in bad:
            with self.subTest(field_type=definition.field_type, text=text):
                with self.assertRaises(ValidationError):
                    definition.parse_text(text)

    def test_parse_date_formats(self):
        expected = datetime.date(2024, 3, 31)
        for text in ("2024-03-31", "03/31/2024", "March 31, 2024", "Mar 31, 2024"):
            self.assertEqual(parse_date(text), expected)


@override_settings(PRIVATE_MEDIA_ROOT=TEMP_PRIVATE)
class FileValueTests(SimpleTestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_PRIVATE, ignore_errors=True)

    def test_upload_replace_and_clear(self):
        definition = field(FieldType.FILE)
        first = definition.to_storage(
            SimpleUploadedFile("scan.pdf", b"one"), upload_folder="test"
        )
        self.assertTrue(first.startswith("test/") and first.endswith("/scan.pdf"))
        self.assertTrue(private_storage.exists(first))

        kept = definition.to_storage(StoredFile(first), current=first)
        self.assertEqual(kept, first)

        second = definition.to_storage(
            SimpleUploadedFile("new.pdf", b"two"), current=first, upload_folder="test"
        )
        self.assertFalse(private_storage.exists(first))

        self.assertIsNone(definition.to_storage(False, current=second))
        self.assertFalse(private_storage.exists(second))


class CustomValuesTests(SimpleTestCase):
    def test_hides_private_and_inactive_fields(self):
        public = field(label="Shirt size", key="shirt")
        private = field(label="Allergies", key="allergies", is_private=True)
        inactive = field(label="Old", key="old", is_active=False)
        data = {"shirt": "L", "allergies": "Nuts", "old": "x"}
        shown = custom_values([public, private, inactive], data, include_private=False)
        self.assertEqual([v.label for v in shown], ["Shirt size"])
        shown = custom_values([public, private, inactive], data, include_private=True)
        self.assertEqual([v.text for v in shown], ["L", "Nuts"])
