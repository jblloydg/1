import re

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import ItemPost, SystemSettings, AbuseReport, Profile
from .validators import validate_photo, validate_profile_photo

User = get_user_model()
STUDENT_ID_PATTERN = re.compile(r"^\d{4}-\d{4}$")


PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 -]{5,18}[0-9]$")


def email_in_use(email, exclude_user=None):
    """Email addresses are unique across all accounts, ignoring letter case."""
    users = User.objects.filter(email__iexact=email)
    if exclude_user is not None:
        users = users.exclude(pk=exclude_user.pk)
    return users.exists()


def _check_password_strength(form, field, password, candidate):
    try:
        validate_password(password, candidate)
    except ValidationError as exc:
        form.add_error(field, exc)


class FindItLoginForm(AuthenticationForm):
    """Students sign in with their Student ID; staff and administrators use their assigned username."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": (
            "Incorrect Student ID / username or password. Passwords are case-sensitive. "
            "If your account was suspended, contact a Find-IT administrator."
        ),
    }

    username = forms.CharField(
        label="Student ID or staff username",
        widget=forms.TextInput(attrs={"autocomplete": "username", "placeholder": "2024-0122", "autofocus": True}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "Your password", "data-password-toggle": "true"}),
    )

    def clean_username(self):
        return self.cleaned_data["username"].strip()


class SignupForm(forms.Form):
    """Student self-registration. The role is always Student and cannot be chosen."""

    first_name = forms.CharField(max_length=60, label="First name", widget=forms.TextInput(attrs={"autocomplete": "given-name"}))
    last_name = forms.CharField(max_length=60, label="Last name", widget=forms.TextInput(attrs={"autocomplete": "family-name"}))
    student_id = forms.CharField(
        max_length=9, label="Student ID", help_text="Format: YYYY-NNNN, such as 2024-0122. Only the format is checked.",
        widget=forms.TextInput(attrs={"placeholder": "2024-0122", "autocomplete": "username"}),
    )
    email = forms.EmailField(max_length=254, label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    password1 = forms.CharField(
        label="Password", strip=False,
        help_text="At least 8 characters. Avoid common passwords, passwords that are only numbers, or anything close to your name or ID.",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-password-toggle": "true"}),
    )
    password2 = forms.CharField(
        label="Confirm password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-password-toggle": "true"}),
    )

    def clean_first_name(self):
        return self.cleaned_data["first_name"].strip()

    def clean_last_name(self):
        return self.cleaned_data["last_name"].strip()

    def clean_student_id(self):
        value = self.cleaned_data["student_id"].strip()
        if not STUDENT_ID_PATTERN.fullmatch(value):
            raise ValidationError("Use the Student ID format YYYY-NNNN, such as 2024-0122.")
        if User.objects.filter(username__iexact=value).exists() or Profile.objects.filter(student_id=value).exists():
            raise ValidationError("That Student ID already has an account.")
        return value

    def clean_email(self):
        value = self.cleaned_data["email"].strip().lower()
        if email_in_use(value):
            raise ValidationError("That email address is already used by another account.")
        return value

    def clean(self):
        cleaned = super().clean()
        password1, password2 = cleaned.get("password1"), cleaned.get("password2")
        if password1 and password2:
            if password1 != password2:
                self.add_error("password2", "The passwords do not match.")
            else:
                candidate = User(
                    username=cleaned.get("student_id", ""), email=cleaned.get("email", ""),
                    first_name=cleaned.get("first_name", ""), last_name=cleaned.get("last_name", ""),
                )
                _check_password_strength(self, "password1", password1, candidate)
        return cleaned

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["student_id"],
            email=self.cleaned_data["email"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            password=self.cleaned_data["password1"],
        )
        # Role is assigned here, never taken from the submitted form.
        user.profile.role = Profile.Role.STUDENT
        user.profile.student_id = self.cleaned_data["student_id"]
        user.profile.save(update_fields=["role", "student_id"])
        return user


class StaffAccountForm(forms.Form):
    """Administrator-only form. Always creates a Staff role account."""

    first_name = forms.CharField(max_length=60, label="First name")
    last_name = forms.CharField(max_length=60, label="Last name", required=False)
    username = forms.RegexField(
        regex=r"^[A-Za-z][A-Za-z0-9._-]{2,31}$",
        label="Staff username",
        help_text="3–32 letters, numbers, dots, dashes, or underscores, starting with a letter. Not a student ID.",
        error_messages={"invalid": "Use 3–32 letters, numbers, dots, dashes, or underscores, starting with a letter."},
    )
    email = forms.EmailField(max_length=254, label="Email address", required=False)
    password = forms.CharField(
        label="Temporary password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-password-toggle": "true"}),
    )
    password_confirm = forms.CharField(
        label="Confirm temporary password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-password-toggle": "true"}),
    )

    def clean_username(self):
        value = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=value).exists():
            raise ValidationError("That username is already in use.")
        return value

    def clean_email(self):
        value = self.cleaned_data.get("email", "").strip().lower()
        if value and email_in_use(value):
            raise ValidationError("That email address is already used by another account.")
        return value

    def clean(self):
        cleaned = super().clean()
        password, confirm = cleaned.get("password"), cleaned.get("password_confirm")
        if password and confirm:
            if password != confirm:
                self.add_error("password_confirm", "The passwords do not match.")
            else:
                candidate = User(
                    username=cleaned.get("username", ""), email=cleaned.get("email", ""),
                    first_name=cleaned.get("first_name", ""), last_name=cleaned.get("last_name", ""),
                )
                _check_password_strength(self, "password", password, candidate)
        return cleaned

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data.get("email", ""),
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data.get("last_name", "").strip(),
            password=self.cleaned_data["password"],
        )
        user.profile.role = Profile.Role.STAFF
        user.profile.student_id = None
        user.profile.save(update_fields=["role", "student_id"])
        return user


class ProfileForm(forms.Form):
    """Fields a signed-in user may change on their own profile.

    Student ID, username, role, and account status are deliberately absent.
    """

    first_name = forms.CharField(max_length=60, label="First name", widget=forms.TextInput(attrs={"autocomplete": "given-name"}))
    last_name = forms.CharField(max_length=60, label="Last name", required=False, widget=forms.TextInput(attrs={"autocomplete": "family-name"}))
    email = forms.EmailField(max_length=254, label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    contact_number = forms.CharField(
        max_length=20, label="Contact number", required=False,
        help_text="Optional. Digits, spaces, or dashes, such as 0917 123 4567 or +63 917 123 4567.",
        widget=forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
    )
    photo = forms.ImageField(
        label="Profile picture", required=False,
        help_text="Optional. JPG, PNG, or WebP; up to 2 MB.",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )
    remove_photo = forms.BooleanField(label="Remove my current profile picture", required=False)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        profile = user.profile
        kwargs.setdefault("initial", {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "contact_number": profile.contact_number,
        })
        super().__init__(*args, **kwargs)

    def clean_first_name(self):
        value = self.cleaned_data["first_name"].strip()
        if not value:
            raise ValidationError("Enter your first name.")
        return value

    def clean_last_name(self):
        return self.cleaned_data.get("last_name", "").strip()

    def clean_email(self):
        value = self.cleaned_data["email"].strip().lower()
        if email_in_use(value, exclude_user=self.user):
            raise ValidationError("That email address is already used by another account.")
        return value

    def clean_contact_number(self):
        value = " ".join(self.cleaned_data.get("contact_number", "").split())
        if not value:
            return ""
        digits = re.sub(r"\D", "", value)
        if not PHONE_PATTERN.fullmatch(value) or not 7 <= len(digits) <= 15:
            raise ValidationError("Enter a valid contact number using digits, spaces, or dashes.")
        return value

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo:
            validate_profile_photo(photo)
        return photo

    @transaction.atomic
    def save(self):
        user, profile = self.user, self.user.profile
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.save(update_fields=["first_name", "last_name", "email"])
        profile.contact_number = self.cleaned_data["contact_number"]
        old_photo_name = profile.photo.name if profile.photo else ""
        new_photo = self.cleaned_data.get("photo")
        if new_photo:
            profile.photo = new_photo
        elif self.cleaned_data.get("remove_photo"):
            profile.photo = None
        profile.save(update_fields=["contact_number", "photo"])
        if old_photo_name and old_photo_name != (profile.photo.name if profile.photo else ""):
            storage = Profile._meta.get_field("photo").storage
            transaction.on_commit(lambda: storage.delete(old_photo_name))
        return user


class FindItPasswordChangeForm(PasswordChangeForm):
    """Django's secure password change form with Find-IT labels and show/hide toggles."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "old_password": "Current password",
            "new_password1": "New password",
            "new_password2": "Confirm new password",
        }
        for name, label in labels.items():
            self.fields[name].label = label
            self.fields[name].widget.attrs["data-password-toggle"] = "true"
        self.fields["new_password1"].help_text = (
            "At least 8 characters. Avoid common passwords, passwords that are only numbers, "
            "or anything close to your name, ID, or email."
        )


class ItemPostForm(forms.ModelForm):
    question_1 = forms.CharField(max_length=240, required=False, label="Private question 1")
    question_2 = forms.CharField(max_length=240, required=False, label="Private question 2")
    question_3 = forms.CharField(max_length=240, required=False, label="Private question 3")
    question_4 = forms.CharField(max_length=240, required=False, label="Private question 4")
    question_5 = forms.CharField(max_length=240, required=False, label="Private question 5")

    class Meta:
        model = ItemPost
        fields = ["post_type", "category", "title", "description", "location", "approximate_date", "photo"]
        widgets = {
            "post_type": forms.Select(attrs={"data-post-type": "true"}),
            "location": forms.TextInput(attrs={"placeholder": "A broad area, such as Library 2nd floor or Canteen"}),
            "title": forms.TextInput(attrs={"placeholder": "A broad name, such as blue water bottle"}),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Describe visible details without revealing private identifiers."}),
            "approximate_date": forms.DateInput(attrs={"type": "date"}),
            "photo": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        }

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo:
            validate_photo(photo)
        return photo

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("post_type") == ItemPost.Type.FOUND:
            questions = [cleaned.get(f"question_{n}", "").strip() for n in range(1, 6)]
            if any(not question for question in questions):
                raise ValidationError("A found-item post needs exactly five private verification questions.")
            if len({q.casefold() for q in questions}) != 5:
                raise ValidationError("Use five different private questions.")
        return cleaned

    def question_texts(self):
        return [self.cleaned_data[f"question_{n}"].strip() for n in range(1, 6)]


class CommentForm(forms.Form):
    text = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Add a public comment"}),
    )


class ClaimAnswerForm(forms.Form):
    def __init__(self, *args, questions=None, **kwargs):
        super().__init__(*args, **kwargs)
        for question in questions or []:
            self.fields[f"answer_{question.pk}"] = forms.CharField(
                label=question.text,
                max_length=1200,
                widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Your private answer"}),
            )


class ReportForm(forms.ModelForm):
    class Meta:
        model = AbuseReport
        fields = ["reason", "details"]
        widgets = {"details": forms.Textarea(attrs={"rows": 4})}


class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = ["guardhouse_grace_days", "archive_purge_days"]
        widgets = {
            "guardhouse_grace_days": forms.NumberInput(attrs={"min": 1, "placeholder": "Disabled"}),
            "archive_purge_days": forms.NumberInput(attrs={"min": 1, "placeholder": "Disabled"}),
        }

    def clean_guardhouse_grace_days(self):
        return self._clean_timer("guardhouse_grace_days")

    def clean_archive_purge_days(self):
        return self._clean_timer("archive_purge_days")

    def _clean_timer(self, field):
        value = self.cleaned_data.get(field)
        if value is not None and value < 1:
            raise ValidationError("Leave blank to keep this timer disabled, or enter at least one day.")
        if value is not None and value > 3650:
            raise ValidationError("Choose a value of 3650 days or less.")
        return value


class AdminReviewForm(forms.Form):
    action = forms.ChoiceField(choices=[
        ("resolve", "Resolve with no account action"),
        ("suspend", "Suspend reported account"),
        ("restore", "Restore account"),
    ])
    admin_note = forms.CharField(max_length=1500, required=False, widget=forms.Textarea(attrs={"rows": 3}))


class CloseReasonForm(forms.Form):
    reason = forms.CharField(max_length=240, required=False, label="Reason (optional)")
