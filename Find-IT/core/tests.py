from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ItemPost, Profile

User = get_user_model()


class CategoryLocationFilterTests(TestCase):
    """Tests for the item category and location feature."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="2026-9001", password="Test-Only-Pass-1", first_name="Test User")
        Profile.objects.get_or_create(user=cls.user)
        cls.bottle = ItemPost.objects.create(
            author=cls.user, post_type=ItemPost.Type.FOUND, title="Blue bottle",
            description="Matte blue bottle.", category=ItemPost.Category.BOTTLE, location="Library 2nd floor",
        )
        cls.keys = ItemPost.objects.create(
            author=cls.user, post_type=ItemPost.Type.LOST, title="Key ring",
            description="Two keys on a ring.", category=ItemPost.Category.KEYS, location="Canteen",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def titles(self, **params):
        response = self.client.get(reverse("home"), params)
        self.assertEqual(response.status_code, 200)
        return {post.title for post in response.context["posts"]}

    def test_default_category_is_other(self):
        post = ItemPost.objects.create(author=self.user, post_type=ItemPost.Type.LOST, title="Thing", description="x")
        self.assertEqual(post.category, ItemPost.Category.OTHER)
        self.assertEqual(post.location, "")

    def test_filter_by_category(self):
        self.assertEqual(self.titles(category="KEYS"), {"Key ring"})

    def test_invalid_category_is_ignored(self):
        self.assertEqual(self.titles(category="NOT_A_CATEGORY"), {"Blue bottle", "Key ring"})

    def test_filter_by_location_is_case_insensitive(self):
        self.assertEqual(self.titles(location="library"), {"Blue bottle"})

    def test_keyword_search_includes_location(self):
        self.assertEqual(self.titles(q="canteen"), {"Key ring"})

    def test_filters_combine(self):
        self.assertEqual(self.titles(category="BOTTLE", location="canteen"), set())

    def test_create_post_saves_category_and_location(self):
        response = self.client.post(reverse("create-post"), {
            "post_type": "LOST", "category": "ELECTRONICS", "title": "Black phone",
            "description": "Black phone in a plain case.", "location": "Gym",
        })
        post = ItemPost.objects.get(title="Black phone")
        self.assertRedirects(response, reverse("post-detail", args=[post.pk]))
        self.assertEqual(post.category, ItemPost.Category.ELECTRONICS)
        self.assertEqual(post.location, "Gym")

    def test_detail_page_shows_category_and_location(self):
        response = self.client.get(reverse("post-detail", args=[self.bottle.pk]))
        self.assertContains(response, "Bottle or container")
        self.assertContains(response, "Library 2nd floor")


# ---------------------------------------------------------------------------
# Account management and user profile
# ---------------------------------------------------------------------------
import io
import os
import shutil
import tempfile

from django.contrib.auth import SESSION_KEY
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from .models import StaffAuditLog

TEST_PASSWORD = "Campus-Test-Pass-91"
TEMP_MEDIA = tempfile.mkdtemp(prefix="findit-test-media-")


def make_image(name="avatar.png", fmt="PNG", size=(40, 40)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (0, 139, 135)).save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{fmt.lower()}")


def make_user(username, role=Profile.Role.STUDENT, email="", superuser=False, **extra):
    user = User.objects.create_user(username=username, password=TEST_PASSWORD, email=email, **extra)
    if superuser:
        user.is_staff = user.is_superuser = True
        user.save()
    user.profile.role = role
    user.profile.student_id = username if role == Profile.Role.STUDENT else None
    user.profile.save()
    return user


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class AccountTestBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.student = make_user("2026-1001", email="student1@example.com", first_name="Sam", last_name="Student")
        cls.other_student = make_user("2026-1002", email="student2@example.com", first_name="Other")
        cls.staff = make_user("guard.one", role=Profile.Role.STAFF, email="guard@example.com", first_name="Gina")
        cls.admin = make_user("admin.one", role=Profile.Role.ADMIN, superuser=True, first_name="Ada")

    def signup_data(self, **overrides):
        data = {
            "first_name": "Nina", "last_name": "Newcomer", "student_id": "2026-2001",
            "email": "nina@example.com", "password1": TEST_PASSWORD, "password2": TEST_PASSWORD,
        }
        data.update(overrides)
        return data


class RegistrationTests(AccountTestBase):
    def test_student_registration_creates_student_and_signs_in(self):
        response = self.client.post(reverse("signup"), self.signup_data(), follow=True)
        user = User.objects.get(username="2026-2001")
        self.assertEqual(user.profile.role, Profile.Role.STUDENT)
        self.assertEqual(user.profile.student_id, "2026-2001")
        self.assertEqual((user.first_name, user.last_name, user.email), ("Nina", "Newcomer", "nina@example.com"))
        self.assertTrue(user.check_password(TEST_PASSWORD))
        self.assertEqual(int(self.client.session[SESSION_KEY]), user.pk)
        self.assertContains(response, "Your student account was created")

    def test_role_cannot_be_chosen_during_registration(self):
        self.client.post(reverse("signup"), self.signup_data(role="admin", is_superuser="1", is_staff="1"))
        user = User.objects.get(username="2026-2001")
        self.assertEqual(user.profile.role, Profile.Role.STUDENT)
        self.assertFalse(user.is_staff or user.is_superuser)

    def test_duplicate_student_id_rejected(self):
        response = self.client.post(reverse("signup"), self.signup_data(student_id="2026-1001"))
        self.assertContains(response, "That Student ID already has an account.")
        self.assertEqual(User.objects.filter(username="2026-1001").count(), 1)

    def test_duplicate_email_rejected_case_insensitive(self):
        response = self.client.post(reverse("signup"), self.signup_data(email="STUDENT1@example.com"))
        self.assertContains(response, "That email address is already used by another account.")
        self.assertFalse(User.objects.filter(username="2026-2001").exists())

    def test_student_id_format_checked(self):
        response = self.client.post(reverse("signup"), self.signup_data(student_id="20262001"))
        self.assertContains(response, "Use the Student ID format YYYY-NNNN")

    def test_required_fields(self):
        response = self.client.post(reverse("signup"), {})
        for field in ["first_name", "last_name", "student_id", "email", "password1", "password2"]:
            self.assertIn(field, response.context["form"].errors)

    def test_weak_password_rejected(self):
        response = self.client.post(reverse("signup"), self.signup_data(password1="12345678", password2="12345678"))
        self.assertIn("password1", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="2026-2001").exists())

    def test_password_mismatch_rejected(self):
        response = self.client.post(reverse("signup"), self.signup_data(password2="Different-Pass-77"))
        self.assertContains(response, "The passwords do not match.")


class LoginTests(AccountTestBase):
    def login(self, username, password=TEST_PASSWORD, **extra):
        return self.client.post(reverse("login"), {"username": username, "password": password, **extra})

    def test_student_login_with_student_id_goes_home(self):
        response = self.login("2026-1001")
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.student.pk)

    def test_staff_login_goes_to_staff_workspace(self):
        self.assertRedirects(self.login("guard.one"), reverse("staff-dashboard"))

    def test_admin_login_goes_to_staff_workspace(self):
        self.assertRedirects(self.login("admin.one"), reverse("staff-dashboard"))

    def test_login_respects_safe_next(self):
        response = self.login("2026-1001", next=reverse("my-profile"))
        self.assertRedirects(response, reverse("my-profile"))

    def test_login_ignores_external_next(self):
        response = self.login("2026-1001", next="https://evil.example.com/")
        self.assertRedirects(response, reverse("home"))

    def test_wrong_password_shows_error(self):
        response = self.login("2026-1001", password="wrong-password")
        self.assertContains(response, "Incorrect Student ID / username or password")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_suspended_account_cannot_log_in(self):
        self.staff.is_active = False
        self.staff.save()
        response = self.login("guard.one")
        self.assertContains(response, "Incorrect Student ID / username or password")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_login_page_has_password_toggle_and_csrf(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "data-password-toggle")
        self.assertContains(response, "csrfmiddlewaretoken")


class AdminAccountManagementTests(AccountTestBase):
    def staff_data(self, **overrides):
        data = {
            "first_name": "Rey", "last_name": "Guard", "username": "rey.guard", "email": "rey@example.com",
            "password": TEST_PASSWORD, "password_confirm": TEST_PASSWORD,
        }
        data.update(overrides)
        return data

    def test_admin_creates_staff_account(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("staff-accounts"), self.staff_data(), follow=True)
        user = User.objects.get(username="rey.guard")
        self.assertEqual(user.profile.role, Profile.Role.STAFF)
        self.assertIsNone(user.profile.student_id)
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertContains(response, "Staff account for Rey Guard was created.")
        self.assertTrue(StaffAuditLog.objects.filter(action="created_staff_account", target_id=str(user.pk)).exists())

    def test_staff_form_rejects_duplicate_email(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("staff-accounts"), self.staff_data(email="guard@example.com"))
        self.assertContains(response, "That email address is already used by another account.")

    def test_admin_sees_all_accounts_with_roles(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("staff-accounts"))
        for username in ["2026-1001", "guard.one", "admin.one"]:
            self.assertContains(response, username)
        response = self.client.get(reverse("staff-accounts"), {"role": "staff"})
        self.assertEqual({u.username for u in response.context["page_obj"]}, {"guard.one"})

    def test_admin_suspends_and_activates_staff(self):
        self.client.force_login(self.admin)
        url = reverse("staff-account-status", args=[self.staff.pk])
        self.client.post(url, {"action": "suspend"})
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)
        self.client.post(url, {"action": "activate"})
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_active)
        self.assertEqual(self.staff.profile.role, Profile.Role.STAFF)

    def test_suspended_staff_session_is_ended(self):
        staff_client = self.client_class()
        staff_client.force_login(self.staff)
        self.client.force_login(self.admin)
        self.client.post(reverse("staff-account-status", args=[self.staff.pk]), {"action": "suspend"})
        response = staff_client.get(reverse("staff-dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_status_endpoint_refuses_self_and_superusers(self):
        # Since the admin-accounts update, administrators may deactivate students too,
        # but never their own account or a Django superuser.
        self.client.force_login(self.admin)
        other_super = make_user("root.two", role=Profile.Role.ADMIN, superuser=True)
        for target in [self.admin, other_super]:
            response = self.client.post(reverse("staff-account-status", args=[target.pk]), {"action": "suspend"})
            self.assertEqual(response.status_code, 403)
            target.refresh_from_db()
            self.assertTrue(target.is_active)

    def test_status_endpoint_requires_post(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("staff-account-status", args=[self.staff.pk]))
        self.assertEqual(response.status_code, 405)


class RolePermissionTests(AccountTestBase):
    def test_student_blocked_from_staff_and_admin_pages(self):
        self.client.force_login(self.student)
        for name in ["staff-dashboard", "staff-accounts", "admin-settings", "admin-reports"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_staff_blocked_from_admin_pages(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("staff-dashboard")).status_code, 200)
        for name in ["staff-accounts", "admin-settings", "admin-reports"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_staff_cannot_create_staff_or_change_status(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("staff-accounts"), {
            "first_name": "X", "username": "sneaky.staff", "password": TEST_PASSWORD, "password_confirm": TEST_PASSWORD,
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="sneaky.staff").exists())
        other = make_user("guard.two", role=Profile.Role.STAFF)
        response = self.client.post(reverse("staff-account-status", args=[other.pk]), {"action": "suspend"})
        self.assertEqual(response.status_code, 403)

    def test_staff_cannot_promote_self_via_profile_form(self):
        self.client.force_login(self.staff)
        self.client.post(reverse("edit-profile"), {
            "first_name": "Gina", "email": "guard@example.com", "role": "admin", "is_superuser": "on", "is_active": "",
        })
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.profile.role, Profile.Role.STAFF)
        self.assertFalse(self.staff.is_superuser)
        self.assertTrue(self.staff.is_active)

    def test_staff_cannot_open_django_admin(self):
        self.client.force_login(self.staff)
        response = self.client.get("/django-admin/")
        self.assertEqual(response.status_code, 302)

    def test_anonymous_redirected_to_login(self):
        for name in ["my-profile", "edit-profile", "change-password", "staff-accounts"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn(reverse("login"), response["Location"])


class ProfileTests(AccountTestBase):
    def edit(self, **overrides):
        data = {"first_name": "Samantha", "last_name": "Student", "email": "sam.new@example.com", "contact_number": "0917 123 4567"}
        data.update(overrides)
        return self.client.post(reverse("edit-profile"), data, follow=True)

    def test_profile_page_shows_details(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("my-profile"))
        for text in ["Sam Student", "2026-1001", "student1@example.com", "Student", "Active", "Registered"]:
            self.assertContains(response, text)

    def test_staff_profile_shows_username(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("my-profile"))
        self.assertContains(response, "<dt>Username</dt><dd>guard.one</dd>", html=True)

    def test_edit_profile_saves_and_shows_immediately(self):
        self.client.force_login(self.student)
        response = self.edit()
        self.assertRedirects(response, reverse("my-profile"))
        self.assertContains(response, "Your profile was updated.")
        self.assertContains(response, "Samantha Student")
        self.assertContains(response, "0917 123 4567")
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "sam.new@example.com")

    def test_locked_fields_cannot_be_changed(self):
        self.client.force_login(self.student)
        self.edit(username="hacked", student_id="2099-9999", role="admin", is_active="")
        self.student.refresh_from_db()
        self.assertEqual(self.student.username, "2026-1001")
        self.assertEqual(self.student.profile.student_id, "2026-1001")
        self.assertEqual(self.student.profile.role, Profile.Role.STUDENT)
        self.assertTrue(self.student.is_active)

    def test_duplicate_email_rejected_on_edit(self):
        self.client.force_login(self.student)
        response = self.edit(email="Student2@Example.com")
        self.assertContains(response, "That email address is already used by another account.")
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "student1@example.com")

    def test_keeping_own_email_is_allowed(self):
        self.client.force_login(self.student)
        self.assertRedirects(self.edit(email="student1@example.com"), reverse("my-profile"))

    def test_invalid_values_rejected(self):
        self.client.force_login(self.student)
        response = self.edit(first_name="  ", email="not-an-email", contact_number="call me")
        errors = response.context["form"].errors
        self.assertEqual(set(errors), {"first_name", "email", "contact_number"})

    def test_profile_picture_upload_and_replace(self):
        self.client.force_login(self.student)
        with self.captureOnCommitCallbacks(execute=True):
            self.edit(photo=make_image("first.png"))
        self.student.profile.refresh_from_db()
        first_name = self.student.profile.photo.name
        self.assertTrue(first_name.startswith("profile-photos/"))
        storage = self.student.profile.photo.storage
        self.assertTrue(storage.exists(first_name))
        response = self.client.get(reverse("my-profile"))
        self.assertContains(response, self.student.profile.photo.url)
        with self.captureOnCommitCallbacks(execute=True):
            self.edit(photo=make_image("second.jpg", fmt="JPEG"))
        self.student.profile.refresh_from_db()
        self.assertNotEqual(self.student.profile.photo.name, first_name)
        self.assertFalse(storage.exists(first_name), "Old picture should be deleted after replacement.")

    def test_remove_profile_picture(self):
        self.client.force_login(self.student)
        self.edit(photo=make_image())
        self.edit(remove_photo="on")
        self.student.profile.refresh_from_db()
        self.assertFalse(self.student.profile.photo)

    def test_non_image_file_rejected(self):
        self.client.force_login(self.student)
        fake = SimpleUploadedFile("notes.png", b"this is not an image", content_type="image/png")
        response = self.edit(photo=fake)
        self.assertIn("photo", response.context["form"].errors)

    def test_wrong_image_type_rejected(self):
        self.client.force_login(self.student)
        response = self.edit(photo=make_image("anim.gif", fmt="GIF"))
        self.assertIn("photo", response.context["form"].errors)

    def test_oversized_image_rejected(self):
        self.client.force_login(self.student)
        buffer = io.BytesIO()
        Image.frombytes("RGB", (1100, 1100), os.urandom(1100 * 1100 * 3)).save(buffer, "PNG")
        self.assertGreater(len(buffer.getvalue()), 2 * 1024 * 1024)
        big = SimpleUploadedFile("big.png", buffer.getvalue(), content_type="image/png")
        response = self.edit(photo=big)
        self.assertContains(response, "smaller than 2 MB")
        self.assertIn("photo", response.context["form"].errors)

    def test_users_only_edit_their_own_profile(self):
        # The edit URL has no user id; whatever is posted only changes the signed-in user.
        self.client.force_login(self.other_student)
        self.edit(first_name="Changed", email="other.new@example.com", user_id=self.student.pk, username="2026-1001")
        self.student.refresh_from_db()
        self.other_student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Sam")
        self.assertEqual(self.other_student.first_name, "Changed")

    def test_profile_link_in_navigation(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("my-profile"))
        self.assertContains(response, reverse("change-password"))
        self.assertContains(response, "data-profile-menu")


class ChangePasswordTests(AccountTestBase):
    NEW = "Fresh-Campus-Pass-42"

    def test_change_password_success_keeps_session(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("change-password"), {
            "old_password": TEST_PASSWORD, "new_password1": self.NEW, "new_password2": self.NEW,
        }, follow=True)
        self.assertRedirects(response, reverse("my-profile"))
        self.assertContains(response, "Your password was changed.")
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password(self.NEW))
        self.assertEqual(self.client.get(reverse("my-profile")).status_code, 200)

    def test_wrong_current_password(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("change-password"), {
            "old_password": "not-my-password", "new_password1": self.NEW, "new_password2": self.NEW,
        })
        self.assertIn("old_password", response.context["form"].errors)
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password(TEST_PASSWORD))

    def test_mismatch_and_weak_new_password(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("change-password"), {
            "old_password": TEST_PASSWORD, "new_password1": self.NEW, "new_password2": self.NEW + "x",
        })
        self.assertIn("new_password2", response.context["form"].errors)
        response = self.client.post(reverse("change-password"), {
            "old_password": TEST_PASSWORD, "new_password1": "password", "new_password2": "password",
        })
        self.assertIn("new_password2", response.context["form"].errors)
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password(TEST_PASSWORD))

    def test_other_sessions_signed_out_after_change(self):
        other_device = self.client_class()
        other_device.force_login(self.student)
        self.client.force_login(self.student)
        self.client.post(reverse("change-password"), {
            "old_password": TEST_PASSWORD, "new_password1": self.NEW, "new_password2": self.NEW,
        })
        self.assertEqual(other_device.get(reverse("my-profile")).status_code, 302)


class CsrfProtectionTests(AccountTestBase):
    def test_account_forms_reject_missing_csrf(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for name in ["edit-profile", "change-password", "staff-accounts"]:
            self.assertEqual(client.post(reverse(name), {}).status_code, 403, name)
        anon = self.client_class(enforce_csrf_checks=True)
        self.assertEqual(anon.post(reverse("signup"), self.signup_data()).status_code, 403)


# ---------------------------------------------------------------------------
# Admin accounts, moderator verification, chat safety and general reports
# ---------------------------------------------------------------------------
from django.utils import timezone

from .consumers import _staff_user
from .models import (
    AbuseReport, ChatMessage, Conversation, GeneralReport, ModeratorVerification, ModeratorVerificationEvent,
    ReportStatus, ReportStatusEvent,
)
from .permissions import can_review_reports, is_verified_moderator
from .services import change_moderator_verification


class ModerationTestBase(AccountTestBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.moderator = make_user("mod.one", role=Profile.Role.STAFF, email="mod@example.com", first_name="Mona")
        change_moderator_verification(cls.moderator, cls.admin, "request")
        change_moderator_verification(cls.moderator, cls.admin, "approve", "Trusted guard.")
        cls.post = ItemPost.objects.create(
            author=cls.student, post_type=ItemPost.Type.LOST, title="Grey backpack", description="Plain grey backpack.",
        )
        cls.conversation = Conversation.objects.create(
            post=cls.post, initiator=cls.other_student, recipient=cls.student,
        )
        cls.bad_message = ChatMessage.objects.create(
            conversation=cls.conversation, sender=cls.other_student, text="Send me money first or else.",
        )
        ChatMessage.objects.create(conversation=cls.conversation, sender=cls.student, text="No thanks.")

    def report_chat(self, client=None, **overrides):
        data = {
            "reason": "SCAM", "target_user": self.other_student.pk, "reported_message": self.bad_message.pk,
            "details": "They asked for money before returning my bag.",
        }
        data.update(overrides)
        return (client or self.client).post(reverse("report-chat", args=[self.conversation.pk]), data)


class AdminAccountEditTests(ModerationTestBase):
    def edit_data(self, account, **overrides):
        data = {
            "first_name": account.first_name or "Name", "last_name": account.last_name, "email": account.email,
            "contact_number": "", "role": account.profile.role, "is_active": "1" if account.is_active else "0",
        }
        data.update(overrides)
        return data

    def test_admin_edits_account_details_and_role(self):
        self.client.force_login(self.admin)
        url = reverse("edit-account", args=[self.staff.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, self.edit_data(self.staff, first_name="Regina", role="admin"), follow=True)
        self.assertContains(response, "was updated")
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.first_name, "Regina")
        self.assertEqual(self.staff.profile.role, Profile.Role.ADMIN)
        self.assertTrue(StaffAuditLog.objects.filter(action="edited_account", target_id=str(self.staff.pk)).exists())

    def test_admin_deactivates_and_activates_student(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("staff-account-status", args=[self.student.pk]), {"action": "suspend"})
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        self.client.post(reverse("staff-account-status", args=[self.student.pk]), {"action": "activate"})
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)

    def test_staff_without_student_id_cannot_become_student(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("edit-account", args=[self.staff.pk]), self.edit_data(self.staff, role="student"))
        self.assertIn("role", response.context["form"].errors)

    def test_admin_cannot_change_own_role_or_status(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("edit-account", args=[self.admin.pk]), self.edit_data(self.admin, role="student", is_active="0"))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertTrue(self.admin.is_superuser)

    def test_last_active_admin_protected(self):
        lone_admin = make_user("admin.two", role=Profile.Role.ADMIN, first_name="Second")
        self.admin.is_active = False
        self.admin.save()
        helper = make_user("admin.three", role=Profile.Role.ADMIN, first_name="Third")
        self.client.force_login(helper)
        # helper and lone_admin are both active admins: demoting one is fine.
        self.client.post(reverse("edit-account", args=[lone_admin.pk]), self.edit_data(lone_admin, role="staff"))
        lone_admin.refresh_from_db()
        self.assertEqual(lone_admin.profile.role, Profile.Role.STAFF)
        # Now helper is the only active admin; another admin cannot exist to demote them, and self-edit is locked.
        response = self.client.post(reverse("staff-account-status", args=[helper.pk]), {"action": "suspend"})
        self.assertEqual(response.status_code, 403)

    def test_role_change_away_from_staff_revokes_moderator(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("edit-account", args=[self.moderator.pk]), self.edit_data(self.moderator, role="admin"))
        verification = ModeratorVerification.objects.get(staff=self.moderator)
        self.assertEqual(verification.status, ModeratorVerification.Status.REVOKED)
        self.assertTrue(verification.events.filter(new_status="REVOKED").exists())

    def test_staff_and_students_cannot_edit_accounts_or_assign_roles(self):
        for actor in [self.staff, self.moderator, self.student]:
            self.client.force_login(actor)
            url = reverse("edit-account", args=[actor.pk])
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.post(url, {"first_name": "X", "role": "admin", "is_active": "1"})
            actor.refresh_from_db()
            self.assertNotEqual(actor.profile.role, Profile.Role.ADMIN)
            self.assertEqual(self.client.get(reverse("admin-dashboard")).status_code, 403)

    def test_account_search_and_status_filter(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("staff-accounts"), {"q": "mod@example"})
        self.assertEqual([u.username for u in response.context["page_obj"]], ["mod.one"])
        self.student.is_active = False
        self.student.save()
        response = self.client.get(reverse("staff-accounts"), {"status": "inactive"})
        self.assertEqual([u.username for u in response.context["page_obj"]], ["2026-1001"])


class ModeratorVerificationTests(ModerationTestBase):
    def decide(self, staff, action, remarks=""):
        return self.client.post(reverse("moderator-verification-action", args=[staff.pk]), {"action": action, "remarks": remarks})

    def test_admin_requests_and_approves(self):
        self.client.force_login(self.admin)
        self.decide(self.staff, "request")
        verification = ModeratorVerification.objects.get(staff=self.staff)
        self.assertEqual(verification.status, ModeratorVerification.Status.PENDING)
        self.assertFalse(is_verified_moderator(self.staff))
        self.decide(self.staff, "approve", "Approved by security office.")
        verification.refresh_from_db()
        self.assertEqual(verification.status, ModeratorVerification.Status.VERIFIED)
        self.assertEqual(verification.reviewed_by, self.admin)
        self.assertIsNotNone(verification.decided_at)
        self.assertEqual(verification.remarks, "Approved by security office.")
        self.assertTrue(is_verified_moderator(self.staff))

    def test_admin_rejects(self):
        self.client.force_login(self.admin)
        self.decide(self.staff, "request")
        self.decide(self.staff, "reject", "Not on duty roster.")
        self.assertEqual(ModeratorVerification.objects.get(staff=self.staff).status, ModeratorVerification.Status.REJECTED)
        self.assertFalse(can_review_reports(self.staff))

    def test_admin_revokes(self):
        self.client.force_login(self.admin)
        self.decide(self.moderator, "revoke", "Left the office.")
        self.assertEqual(ModeratorVerification.objects.get(staff=self.moderator).status, ModeratorVerification.Status.REVOKED)
        self.assertFalse(can_review_reports(self.moderator))

    def test_invalid_transitions_refused(self):
        self.client.force_login(self.admin)
        response = self.decide(self.staff, "approve")  # never requested
        self.assertFalse(ModeratorVerification.objects.filter(staff=self.staff).exists())
        self.assertContains(self.client.get(reverse("moderator-verifications")), "Moderator verification")
        self.decide(self.moderator, "reject")  # already verified
        self.assertEqual(ModeratorVerification.objects.get(staff=self.moderator).status, ModeratorVerification.Status.VERIFIED)

    def test_only_staff_can_be_moderators(self):
        self.client.force_login(self.admin)
        self.decide(self.student, "request")
        self.assertFalse(ModeratorVerification.objects.filter(staff=self.student).exists())

    def test_history_is_recorded_and_shown(self):
        self.client.force_login(self.admin)
        self.decide(self.staff, "request")
        self.decide(self.staff, "reject", "Try again next term.")
        self.decide(self.staff, "request")
        events = ModeratorVerificationEvent.objects.filter(verification__staff=self.staff)
        self.assertEqual(events.count(), 3)
        response = self.client.get(reverse("moderator-verifications"))
        self.assertContains(response, "Try again next term.")

    def test_non_admins_cannot_manage_verifications(self):
        for actor in [self.staff, self.moderator, self.student]:
            self.client.force_login(actor)
            self.assertEqual(self.client.get(reverse("moderator-verifications")).status_code, 403)
            self.assertEqual(self.decide(actor, "request").status_code, 403)
        self.assertFalse(ModeratorVerification.objects.filter(staff=self.staff).exists())

    def test_pending_rejected_revoked_staff_have_no_moderator_access(self):
        report = AbuseReport.objects.create(reporter=self.student, conversation=self.conversation, target_user=self.other_student, reason="SPAM", details="Spam messages here.")
        for status in ["PENDING", "REJECTED", "REVOKED", None]:
            ModeratorVerification.objects.filter(staff=self.staff).delete()
            if status:
                ModeratorVerification.objects.create(staff=self.staff, status=status)
            self.client.force_login(self.staff)
            for url in [reverse("admin-reports"), reverse("general-reports"), reverse("review-report", args=[report.pk]),
                        reverse("chat-room", args=[self.conversation.pk])]:
                self.assertEqual(self.client.get(url).status_code, 403, f"{status} {url}")
            self.assertFalse(_staff_user(self.staff))
            response = self.client.post(reverse("pause-chat", args=[self.conversation.pk]))
            self.assertEqual(response.status_code, 403)

    def test_verified_moderator_has_access(self):
        self.client.force_login(self.moderator)
        for url in [reverse("admin-reports"), reverse("general-reports"), reverse("chat-room", args=[self.conversation.pk])]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertTrue(_staff_user(self.moderator))

    def test_deactivated_moderator_loses_access(self):
        self.moderator.is_active = False
        self.moderator.save()
        self.assertFalse(is_verified_moderator(self.moderator))


class ChatSafetyReportTests(ModerationTestBase):
    def test_participant_submits_report(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("report-chat", args=[self.conversation.pk])).status_code, 200)
        response = self.report_chat()
        report = AbuseReport.objects.get()
        self.assertRedirects(response, reverse("chat-room", args=[self.conversation.pk]))
        self.assertRegex(report.reference, r"^CSR-\d{8}-[0-9A-F]{6}$")
        self.assertEqual(report.status, ReportStatus.SUBMITTED)
        self.assertEqual((report.reporter, report.target_user, report.reported_message), (self.student, self.other_student, self.bad_message))
        self.assertEqual(report.events.count(), 1)
        # Not automatic: no suspension, chat not paused by a participant report.
        self.other_student.refresh_from_db()
        self.conversation.refresh_from_db()
        self.assertTrue(self.other_student.is_active)
        self.assertFalse(self.conversation.is_paused)

    def test_report_validation(self):
        self.client.force_login(self.student)
        response = self.report_chat(target_user=self.student.pk, details="short", reason="")
        self.assertEqual(set(response.context["form"].errors), {"target_user", "details", "reason"})
        stranger_message = ChatMessage.objects.create(
            conversation=Conversation.objects.create(post=self.post, initiator=self.staff, recipient=self.student),
            sender=self.staff, text="Elsewhere",
        )
        response = self.report_chat(reported_message=stranger_message.pk)
        self.assertIn("reported_message", response.context["form"].errors)
        self.assertFalse(AbuseReport.objects.exists())

    def test_non_participant_cannot_report_or_view(self):
        outsider = make_user("2026-1003", email="out@example.com")
        self.client.force_login(outsider)
        self.assertEqual(self.report_chat().status_code, 403)
        self.assertEqual(self.client.get(reverse("chat-room", args=[self.conversation.pk])).status_code, 403)

    def test_reviewer_status_flow_and_history(self):
        self.client.force_login(self.student)
        self.report_chat()
        report = AbuseReport.objects.get()
        self.client.force_login(self.moderator)
        url = reverse("review-report", args=[report.pk])
        response = self.client.get(url)
        self.assertContains(response, "Send me money first")
        self.client.post(url, {"action": "UNDER_REVIEW", "remarks": "Checking messages."})
        report.refresh_from_db()
        self.assertEqual(report.status, ReportStatus.UNDER_REVIEW)
        self.assertEqual(report.assigned_reviewer, self.moderator)
        self.client.post(url, {"action": "RESOLVED", "remarks": "Warned the user."})
        report.refresh_from_db()
        self.assertEqual(report.status, ReportStatus.RESOLVED)
        self.assertEqual(report.reviewed_by, self.moderator)
        self.assertIsNotNone(report.resolved_at)
        self.assertEqual(report.admin_note, "Warned the user.")
        self.assertEqual(
            list(report.events.values_list("new_status", flat=True)),
            ["SUBMITTED", "UNDER_REVIEW", "RESOLVED"],
        )
        # Closed reports cannot be resolved again without reopening.
        response = self.client.post(url, {"action": "DISMISSED"})
        self.assertIn("action", response.context["form"].errors)

    def test_dismiss_and_filters(self):
        r1 = AbuseReport.objects.create(reporter=self.student, conversation=self.conversation, target_user=self.other_student, reason="SPAM", details="Spam spam spam.")
        AbuseReport.objects.create(reporter=self.other_student, conversation=self.conversation, target_user=self.student, reason="HARASSMENT", details="Rude replies here.")
        self.client.force_login(self.admin)
        self.client.post(reverse("review-report", args=[r1.pk]), {"action": "DISMISSED", "remarks": "Not spam."})
        list_url = reverse("admin-reports")
        self.assertEqual(len(self.client.get(list_url, {"status": "DISMISSED"}).context["page_obj"]), 1)
        self.assertEqual(len(self.client.get(list_url, {"category": "HARASSMENT"}).context["page_obj"]), 1)
        self.assertEqual(len(self.client.get(list_url, {"q": r1.reference}).context["page_obj"]), 1)
        today = timezone.localdate().isoformat()
        self.assertEqual(len(self.client.get(list_url, {"date_from": today, "date_to": today}).context["page_obj"]), 2)
        self.assertEqual(len(self.client.get(list_url, {"date_to": "2000-01-01"}).context["page_obj"]), 0)

    def test_only_admin_can_suspend_from_report(self):
        report = AbuseReport.objects.create(reporter=self.student, conversation=self.conversation, target_user=self.other_student, reason="THREATS", details="Threatening messages.")
        self.client.force_login(self.moderator)
        url = reverse("review-report", args=[report.pk])
        self.client.post(url, {"action": "RESOLVED", "account_action": "suspend"})
        self.other_student.refresh_from_db()
        self.assertTrue(self.other_student.is_active, "Moderators cannot suspend accounts.")
        report.status = ReportStatus.UNDER_REVIEW
        report.save()
        self.client.force_login(self.admin)
        self.client.post(url, {"action": "RESOLVED", "account_action": "suspend", "remarks": "Confirmed threats."})
        self.other_student.refresh_from_db()
        self.assertFalse(self.other_student.is_active)

    def test_reports_private_and_remarks_internal(self):
        self.client.force_login(self.student)
        self.report_chat()
        report = AbuseReport.objects.get()
        report.admin_note = "INTERNAL-ONLY-NOTE"
        report.save()
        response = self.client.get(reverse("my-reports"))
        self.assertContains(response, report.reference)
        self.assertNotContains(response, "INTERNAL-ONLY-NOTE")
        self.client.force_login(self.other_student)
        self.assertNotContains(self.client.get(reverse("my-reports")), report.reference)
        for user in [self.student, self.other_student, self.staff]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("review-report", args=[report.pk])).status_code, 403)
            self.assertEqual(self.client.get(reverse("admin-reports")).status_code, 403)

    def test_existing_reports_migrated_fields(self):
        report = AbuseReport.objects.create(reporter=self.student, reason="OTHER", details="Something else.")
        self.assertTrue(report.reference.startswith("CSR-"))
        self.assertEqual(report.status, ReportStatus.SUBMITTED)


@override_settings(PRIVATE_MEDIA_ROOT=TEMP_MEDIA + "/private")
class GeneralReportTests(ModerationTestBase):
    def submit(self, **overrides):
        data = {"category": "SUSPICIOUS_LISTING", "description": "This listing looks fake to me.", "post": self.post.pk}
        data.update(overrides)
        return self.client.post(reverse("general-report-create"), data)

    def test_submit_with_listing_and_attachment(self):
        self.client.force_login(self.other_student)
        page = self.client.get(reverse("general-report-create"), {"post": self.post.pk})
        self.assertContains(page, "Grey backpack")
        response = self.submit(attachment=make_image("screen.png"))
        self.assertRedirects(response, reverse("my-reports"))
        report = GeneralReport.objects.get()
        self.assertRegex(report.reference, r"^GRP-\d{8}-[0-9A-F]{6}$")
        self.assertEqual((report.reporter, report.post, report.status), (self.other_student, self.post, ReportStatus.SUBMITTED))
        self.assertTrue(report.attachment.name.startswith("report-attachments/"))
        self.assertNotIn("screen", report.attachment.name)
        # Stored outside public media.
        self.assertFalse(report.attachment.path.startswith(str(TEMP_MEDIA) + "/report-attachments"))
        self.post.refresh_from_db()
        self.assertFalse(self.post.is_archived, "Reported listings are not hidden automatically.")
        self.assertEqual(self.post.status, ItemPost.Status.OPEN)

    def test_technical_report_without_listing(self):
        self.client.force_login(self.student)
        self.submit(category="TECHNICAL", post="", description="Upload button does nothing on my phone.")
        self.assertIsNone(GeneralReport.objects.get().post)

    def test_attachment_validation(self):
        self.client.force_login(self.student)
        bad = SimpleUploadedFile("evil.png", b"<script>alert(1)</script>", content_type="image/png")
        self.assertIn("attachment", self.submit(attachment=bad).context["form"].errors)
        exe = SimpleUploadedFile("tool.exe", b"MZ....", content_type="application/octet-stream")
        self.assertIn("attachment", self.submit(attachment=exe).context["form"].errors)
        pdf = SimpleUploadedFile("proof.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf")
        self.assertRedirects(self.submit(attachment=pdf), reverse("my-reports"))
        self.assertIn("description", self.submit(description="short").context["form"].errors)

    def test_attachment_access_control(self):
        self.client.force_login(self.other_student)
        self.submit(attachment=make_image("screen.png"))
        report = GeneralReport.objects.get()
        url = reverse("general-report-attachment", args=[report.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        b"".join(response.streaming_content)
        for user in [self.student, self.staff]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)
        for user in [self.moderator, self.admin]:
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            b"".join(response.streaming_content)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.get(f"/media/{report.attachment.name}").status_code, 404)

    def test_reviewer_reviews_with_related_item_and_history(self):
        self.client.force_login(self.other_student)
        self.submit()
        report = GeneralReport.objects.get()
        self.client.force_login(self.moderator)
        url = reverse("general-report-detail", args=[report.pk])
        response = self.client.get(url)
        self.assertContains(response, "Grey backpack")
        self.assertContains(response, self.student.username)
        self.client.post(url, {"action": "UNDER_REVIEW"})
        self.client.post(url, {"action": "NOTE", "remarks": "Asked author for details."})
        self.client.post(url, {"action": "RESOLVED", "remarks": "Listing corrected."})
        report.refresh_from_db()
        self.assertEqual(report.status, ReportStatus.RESOLVED)
        self.assertEqual(report.internal_remarks, "Listing corrected.")
        self.assertEqual(report.reviewed_by, self.moderator)
        self.assertEqual(
            list(report.events.values_list("new_status", "note")),
            [("SUBMITTED", ""), ("UNDER_REVIEW", ""), ("UNDER_REVIEW", "Asked author for details."), ("RESOLVED", "Listing corrected.")],
        )
        self.client.force_login(self.other_student)
        self.assertNotContains(self.client.get(reverse("my-reports")), "Listing corrected.")

    def test_unauthorized_cannot_review(self):
        self.client.force_login(self.other_student)
        self.submit()
        report = GeneralReport.objects.get()
        for user in [self.student, self.other_student, self.staff]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("general-report-detail", args=[report.pk])).status_code, 403)
            self.client.post(reverse("general-report-detail", args=[report.pk]), {"action": "DISMISSED"})
        report.refresh_from_db()
        self.assertEqual(report.status, ReportStatus.SUBMITTED)

    def test_report_event_constraint(self):
        from django.db import IntegrityError, transaction as db_transaction
        with self.assertRaises(IntegrityError), db_transaction.atomic():
            ReportStatusEvent.objects.create(new_status="SUBMITTED")


class AdminDashboardTests(ModerationTestBase):
    def test_counts_match_database_and_update(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin-dashboard"))
        c = response.context
        self.assertEqual(c["account_counts"]["total"], User.objects.count())
        self.assertEqual(c["account_counts"]["students"], 2)
        self.assertEqual(c["account_counts"]["staff"], 2)
        self.assertEqual(c["account_counts"]["admins"], 1)
        self.assertEqual(c["account_counts"]["inactive"], 0)
        self.assertEqual(c["verification_counts"]["VERIFIED"], 1)
        self.assertEqual(c["chat_counts"]["TOTAL"], 0)
        self.assertEqual(c["general_counts"]["TOTAL"], 0)

        self.client.force_login(self.student)
        self.report_chat()
        self.client.post(reverse("general-report-create"), {"category": "TECHNICAL", "description": "Search is slow today."})
        self.client.force_login(self.admin)
        self.client.post(reverse("staff-account-status", args=[self.other_student.pk]), {"action": "suspend"})
        report = AbuseReport.objects.get()
        self.client.post(reverse("review-report", args=[report.pk]), {"action": "UNDER_REVIEW"})
        c = self.client.get(reverse("admin-dashboard")).context
        self.assertEqual(c["chat_counts"]["TOTAL"], 1)
        self.assertEqual(c["chat_counts"]["UNDER_REVIEW"], 1)
        self.assertEqual(c["chat_counts"]["SUBMITTED"], 0)
        self.assertEqual(c["general_counts"]["SUBMITTED"], 1)
        self.assertEqual(c["account_counts"]["inactive"], 1)

    def test_dashboard_admin_only(self):
        for user in [self.student, self.staff, self.moderator]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("admin-dashboard")).status_code, 403)

    def test_staff_workspace_still_works(self):
        for user, sees_reports in [(self.staff, False), (self.moderator, True), (self.admin, True)]:
            self.client.force_login(user)
            response = self.client.get(reverse("staff-dashboard"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["is_reviewer"], sees_reports)


class ExistingFeatureSmokeTests(ModerationTestBase):
    def test_core_pages_still_render(self):
        self.client.force_login(self.student)
        for name, args in [("home", []), ("post-detail", [self.post.pk]), ("create-post", []), ("my-posts", []),
                           ("my-claims", []), ("messages", []), ("notifications", []), ("my-profile", []), ("my-reports", []),
                           ("chat-room", [self.conversation.pk])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)
        self.client.force_login(self.admin)
        for name in ["admin-dashboard", "staff-accounts", "moderator-verifications", "admin-reports", "general-reports",
                     "admin-settings", "staff-dashboard"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("edit-account", args=[self.student.pk])).status_code, 200)

    def test_post_detail_has_report_link(self):
        self.client.force_login(self.other_student)
        response = self.client.get(reverse("post-detail", args=[self.post.pk]))
        self.assertContains(response, f"{reverse('general-report-create')}?post={self.post.pk}")
