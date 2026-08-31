from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from books.models import Book, Review
from books.permissions import HasSpecialStatus
from books.serializers import BookDetailSerializer, BookListSerializer, ReviewSerializer

User = get_user_model()
factory = APIRequestFactory()


class HasSpecialStatusPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="plain", email="plain@example.com", password="pass12345"
        )
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pass12345"
        )

    def test_user_without_permission_is_rejected(self):
        request = factory.get("/api/books/whatever/")
        request.user = self.user
        permission = HasSpecialStatus()
        self.assertFalse(permission.has_permission(request, view=None))

    def test_user_with_permission_is_accepted(self):
        perm = Permission.objects.get(codename="special_status", content_type__app_label="books")
        self.user.user_permissions.add(perm)
        # user_permissions est mis en cache sur l'objet : on recharge depuis la DB
        self.user = User.objects.get(pk=self.user.pk)
        request = factory.get("/api/books/whatever/")
        request.user = self.user
        permission = HasSpecialStatus()
        self.assertTrue(permission.has_permission(request, view=None))

    def test_superuser_always_accepted(self):
        request = factory.get("/api/books/whatever/")
        request.user = self.superuser
        permission = HasSpecialStatus()
        self.assertTrue(permission.has_permission(request, view=None))


class BookSerializerTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(title="Clean Code", author="Robert C. Martin", price="45.00")
        self.reviewer = User.objects.create_user(
            username="reviewer", email="reviewer@example.com", password="pass12345"
        )
        Review.objects.create(book=self.book, author=self.reviewer, review="Superbe livre.")

    def test_list_serializer_excludes_reviews(self):
        data = BookListSerializer(self.book).data
        self.assertNotIn("reviews", data)
        self.assertEqual(data["title"], "Clean Code")

    def test_detail_serializer_includes_nested_reviews(self):
        data = BookDetailSerializer(self.book).data
        self.assertIn("reviews", data)
        self.assertEqual(len(data["reviews"]), 1)
        self.assertEqual(data["reviews"][0]["review"], "Superbe livre.")
        self.assertEqual(data["reviews"][0]["author"], "reviewer")

    def test_review_serializer_shows_author_username_not_id(self):
        review = self.book.reviews.first()
        data = ReviewSerializer(review).data
        self.assertEqual(data["author"], "reviewer")