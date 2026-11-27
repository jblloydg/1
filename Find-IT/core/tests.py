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
