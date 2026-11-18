from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Role, User
from .roles import administrators


def role_field():
    return forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Roles",
        help_text="A user gets every permission of every role they hold.",
    )


class RolesMixin:
    """Saves the ``roles`` field into the user's groups, keeping any plain
    Django groups that aren't roles."""

    def save_roles(self, user):
        other_groups = list(user.groups.filter(role__isnull=True))
        user.groups.set([*self.cleaned_data["roles"], *other_groups])


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class UserCreateForm(RolesMixin, UserCreationForm):
    roles = role_field()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def save(self, commit=True):
        user = super().save(commit=True)
        self.save_roles(user)
        return user


class UserEditForm(RolesMixin, forms.ModelForm):
    roles = role_field()

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active"]
        labels = {"is_active": "Active"}
        help_texts = {
            "is_active": "Inactive users can't sign in. Users are deactivated, "
            "never deleted, so their history stays.",
        }

    def __init__(self, *args, editor, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        self.fields["roles"].initial = list(self.instance.roles)

    def clean(self):
        cleaned = super().clean()
        user = self.instance
        is_active = cleaned.get("is_active", user.is_active)
        roles = cleaned.get("roles") or []
        if user.pk == self.editor.pk and not is_active:
            raise forms.ValidationError("You can't deactivate your own account.")
        stays_administrator = is_active and (
            user.is_superuser or any(role.is_administrator for role in roles)
        )
        is_last_administrator = (
            administrators().filter(pk=user.pk).exists()
            and not administrators().exclude(pk=user.pk).exists()
        )
        if is_last_administrator and not stays_administrator:
            raise forms.ValidationError(
                "This is the only active administrator. Make someone else an "
                "administrator first."
            )
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=True)
        self.save_roles(user)
        return user


class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ["name", "description"]
