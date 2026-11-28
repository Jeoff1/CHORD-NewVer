import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .memberships import (
    AccountNotFound,
    find_account,
    is_last_administrator,
    may_manage_account,
)
from .models import Membership, Role, User


def role_field():
    return forms.ModelMultipleChoiceField(
        queryset=Role.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Roles",
        help_text="A user gets every permission of every role they hold.",
    )


class RolesMixin:
    """The ``roles`` field lists the church's roles, and saving puts the
    chosen ones on the user's Membership in that church (decision 0014)."""

    def setup_roles(self, church):
        self.church = church
        self.fields["roles"].queryset = Role.objects.filter(church=church)

    def save_roles(self, user):
        membership, _ = Membership.objects.get_or_create(user=user, church=self.church)
        membership.roles.set(self.cleaned_data["roles"])


def username_from_email(email):
    """A username no account has, made from ``email`` (Django's username
    characters only: letters, digits and @ . + - _), for accounts that sign
    in with their email."""
    base = re.sub(r"[^\w.@+-]", "", email.strip().lower())[:140] or "member"
    username, number = base, 1
    while User.objects.filter(username__iexact=username).exists():
        number += 1
        username = f"{base}-{number}"
    return username


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    """Django's sign-in form, for an email or a username (owner, 27 Nov
    2026): accounts made by registering a church sign in with their email;
    older ones and those an administrator made keep their username.
    ``ChurchRoleBackend`` finds the account."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": (
            "Please enter a correct email or username and password. Note that "
            "the password is case-sensitive."
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email or username"


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "middle_name", "last_name", "suffix", "email"]


class PersonalInfoForm(forms.ModelForm):
    """Edit Profile (UI/UX Phase 2): only the name fields the account already
    has. No picture or bio (the lead developer's decision, 28 Nov 2026)."""

    class Meta:
        model = User
        fields = ["first_name", "middle_name", "last_name", "suffix"]
        help_texts = {"suffix": "Optional, such as Jr., Sr. or III."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A full name, as registering asks for one.
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["middle_name"].help_text = "Optional."

    def clean(self):
        cleaned = super().clean()
        for name in self.Meta.fields:
            if isinstance(cleaned.get(name), str):
                cleaned[name] = " ".join(cleaned[name].split())
        return cleaned


class AppearanceForm(forms.ModelForm):
    """The person's own light or dark mode (Phase 9A, A7)."""

    class Meta:
        model = User
        fields = ["theme"]
        widgets = {"theme": forms.RadioSelect}
        labels = {"theme": "Light or dark mode"}
        help_texts = {
            "theme": "Only for you, on every device you sign in on. Match my "
            "device follows your phone's or computer's own setting."
        }


class UserCreateForm(RolesMixin, UserCreationForm):
    roles = role_field()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "first_name", "last_name", "email"]

    def __init__(self, *args, church, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_roles(church)

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

    ACCOUNT_FIELDS = ("username", "first_name", "last_name", "email", "is_active")

    def __init__(self, *args, editor, church, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        self.setup_roles(church)
        self.fields["roles"].initial = list(self.instance.roles_in(church))
        # Phase 9B: an account that also belongs to another church (or a
        # superuser's) is its owner's; this church manages only its roles.
        self.manages_account = may_manage_account(self.instance, church)
        if not self.manages_account:
            for name in self.ACCOUNT_FIELDS:
                self.fields[name].disabled = True
            self.fields["username"].help_text = (
                "This account also belongs to another church, so only its owner "
                "changes these details."
            )

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
        if is_last_administrator(user, self.church) and not stays_administrator:
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
        fields = ["title", "description"]

    def __init__(self, *args, church, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.church_id is None:
            self.instance.church = church

    def clean_title(self):
        # The church isn't a form field, so Django's own check of the
        # per-church unique name doesn't run; check it here.
        title = self.cleaned_data["title"]
        taken = Role.objects.filter(
            church=self.instance.church, title__iexact=title
        ).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("A role with this name already exists.")
        return title


class SignUpForm(UserCreationForm):
    """A person's own account, made in the first step of registering a
    church (Phase 9B; owner, 27 Nov 2026). It asks no username: the person
    signs in with their email (``EmailOrUsernameAuthenticationForm``), so
    the email must be no other account's, and the username Django still
    needs is made from it behind the scenes."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["first_name", "last_name", "middle_name", "suffix", "email"]
        labels = {"email": "Email address"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        # The name shows wherever the account does, now that it has no
        # username of its own choosing (owner, 27 Nov 2026).
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].help_text = "You sign in with it, and reset your password."
        # Wording approved with the sign-up page redesign (27 Nov 2026); the
        # rules themselves stay Django's: the field and its validators are
        # unchanged.
        self.fields["password2"].label = "Confirm password"
        self.fields["password2"].help_text = "Enter the same password again."

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account already uses this email. Sign in with it instead."
            )
        return email

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        if email:
            # Before the password checks, which compare it with the username.
            self.instance.username = username_from_email(email)
        return cleaned


class AddExistingAccountForm(forms.Form):
    """Add someone who already has an account to this church (Phase 9B),
    found by their exact username or email."""

    account = forms.CharField(
        label="Username or email",
        max_length=254,
        help_text="Exactly as the person gives it to you. Nothing is searched.",
    )
    roles = role_field()

    def __init__(self, *args, church, **kwargs):
        super().__init__(*args, **kwargs)
        self.church = church
        self.fields["roles"].queryset = Role.objects.filter(church=church)

    def clean_account(self):
        try:
            user = find_account(self.cleaned_data["account"])
        except AccountNotFound as problem:
            raise forms.ValidationError(str(problem)) from problem
        if Membership.objects.filter(user=user, church=self.church).exists():
            raise forms.ValidationError("That person is already in this church.")
        return user

    def save(self):
        membership = Membership.objects.create(
            user=self.cleaned_data["account"], church=self.church
        )
        membership.roles.set(self.cleaned_data["roles"])
        return membership


class VisitorAccountForm(forms.Form):
    """A visitor's account, asked in the pop-up when they request a service
    without one (28 Nov 2026): their name, email and a password. Nothing is
    made until they type the code emailed to them (``verification.py``)."""

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(label="Email address", max_length=254)
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="At least 8 characters, not only numbers, and unlike your "
        "name or email.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"

    def clean_email(self):
        return self.cleaned_data["email"].strip()

    @property
    def has_account(self):
        """Whether the email (valid so far) is an account's already."""
        email = self.cleaned_data.get("email") if hasattr(self, "cleaned_data") else ""
        return bool(email) and User.objects.filter(email__iexact=email).exists()

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        email = cleaned.get("email")
        if password and email and not self.has_account:
            # The same rules as every other password in CHORD.
            from django.contrib.auth import password_validation

            person = User(
                username=username_from_email(email),
                email=email,
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
            )
            try:
                password_validation.validate_password(password, person)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return cleaned


class EmailCodeForm(forms.Form):
    code = forms.CharField(
        label="Code",
        max_length=12,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "pattern": "[0-9 ]*",
            }
        ),
    )


class PasswordOnlyForm(forms.Form):
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
