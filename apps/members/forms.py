from django import forms
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.core.custom_fields import CustomFieldsFormMixin, FieldType
from apps.core.storage import PrivateFileInput

from .models import Household, Member, MemberField, MembershipStatus, RelationshipType

DATE_INPUT = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")

# Form sections, in order. Fields a user may not see are skipped.
SECTIONS = [
    ("Name", ["first_name", "middle_name", "last_name", "suffix", "sex"]),
    ("Private details", ["birth_date", "email", "phone", "address"]),
    ("Membership", ["status", "joined_on", "photo", "user", "notes"]),
    ("Household", ["household", "relationship"]),
]


class UserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        full_name = user.get_full_name()
        return f"{user.username} ({full_name})" if full_name else user.username


class MemberForm(CustomFieldsFormMixin, forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "suffix",
            "sex",
            "birth_date",
            "email",
            "phone",
            "address",
            "photo",
            "status",
            "joined_on",
            "household",
            "relationship",
            "user",
            "notes",
        ]
        widgets = {
            "birth_date": DATE_INPUT,
            "joined_on": DATE_INPUT,
            "address": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
        field_classes = {"user": UserChoiceField}

    def __init__(self, *args, can_view_private=True, for_import=False, **kwargs):
        super().__init__(*args, **kwargs)
        member = self.instance
        if not can_view_private:
            for name in Member.PRIVATE_FIELDS:
                self.fields.pop(name)
        self.fields["status"].queryset = MembershipStatus.objects.usable(
            member.status_id
        )
        default_status = MembershipStatus.default()
        if not member.pk and not self.initial.get("status") and default_status:
            self.initial["status"] = default_status.pk
        self.fields["relationship"].queryset = RelationshipType.objects.usable(
            member.relationship_id
        )
        self.fields["household"].queryset = Household.objects.all()
        self.fields["user"].queryset = get_user_model().objects.filter(
            is_active=True, member__isnull=True
        ) | get_user_model().objects.filter(pk=member.user_id)
        if member.pk:
            self.fields["photo"].widget = PrivateFileInput(
                url=reverse("members:photo", kwargs={"public_id": member.public_id})
            )

        definitions = MemberField.objects.all()
        if for_import:
            # Files can't come from a CSV; the import sets the household itself
            # because the household may not exist yet.
            definitions = definitions.exclude(field_type=FieldType.FILE)
            for name in ("photo", "user", "household", "relationship"):
                self.fields.pop(name)
        self.add_custom_fields(definitions, include_private=can_view_private)

    def custom_file_url(self, definition):
        if not self.instance.pk:
            return "#"
        return reverse(
            "members:file",
            kwargs={"public_id": self.instance.public_id, "key": definition.key},
        )

    def sections(self):
        """``(title, bound fields)`` per section, for the form template."""
        result = [
            (title, [self[name] for name in names if name in self.fields])
            for title, names in SECTIONS
        ]
        if self.custom_definitions:
            result.append(("More details", self.custom_fields()))
        return [(title, fields) for title, fields in result if fields]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("relationship") and not cleaned.get("household"):
            self.add_error("relationship", "Choose a household first.")
        return cleaned

    def save(self, commit=True):
        self.save_custom_fields(upload_folder="members/files")
        return super().save(commit)


class HouseholdForm(forms.ModelForm):
    class Meta:
        model = Household
        fields = ["name", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class ImportUploadForm(forms.Form):
    file = forms.FileField(
        label="CSV file",
        help_text="Save your spreadsheet as CSV (UTF-8). The first row must be "
        "the column names.",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}),
    )


class MemberAccountsForm(forms.Form):
    """Accounts for ticked members, with one role (Phase 9A, A4). Members
    who already have an account by the time it is saved are skipped, not
    refused, so the queryset is every member."""

    members = forms.ModelMultipleChoiceField(
        queryset=Member.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Tick at least one person."},
    )
    role = forms.ModelChoiceField(
        queryset=None,
        empty_label=None,
        help_text="Every new account gets this role. You can change it later "
        "on each user's page.",
    )

    def __init__(self, *args, **kwargs):
        from apps.accounts.models import Role

        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = Role.objects.order_by("name")
        default = Role.objects.filter(key="church_member").first()
        if default:
            self.fields["role"].initial = default.pk
