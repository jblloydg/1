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
        self.assertEqual({u.username for u in response.context["accounts"]}, {"guard.one"})

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

    def test_status_endpoint_only_changes_staff(self):
        self.client.force_login(self.admin)
        for target in [self.student, self.admin]:
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
