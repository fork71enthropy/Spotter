from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from books.models import Book, Review

User = get_user_model()


def make_user(**kwargs):
    defaults = {"username": "user", "email": "user@example.com", "password": "pass12345"}
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def grant_special_status(user):
    perm = Permission.objects.get(codename="special_status", content_type__app_label="books")
    user.user_permissions.add(perm)
    return User.objects.get(pk=user.pk)  # recharge pour vider le cache de permissions


class BookListAPIViewTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(user=self.user)
        Book.objects.create(title="Clean Code", author="Robert C. Martin", price="45.00")
        Book.objects.create(title="Effective Python", author="Brett Slatkin", price="39.99")
        Book.objects.create(title="Deep Learning", author="Ian Goodfellow", price="70.00")

    def test_list_all_books(self):
        url = reverse("api_book_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_search_by_title(self):
        url = reverse("api_book_list")
        response = self.client.get(url, {"q": "clean"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Clean Code")

    def test_search_by_author(self):
        url = reverse("api_book_list")
        response = self.client.get(url, {"q": "goodfellow"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Deep Learning")

    def test_search_with_no_match(self):
        url = reverse("api_book_list")
        response = self.client.get(url, {"q": "inexistant"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse("api_book_list")
        response = self.client.get(url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class BookDetailAPIViewTests(APITestCase):
    def setUp(self):
        self.book = Book.objects.create(title="Clean Code", author="Robert C. Martin", price="45.00")

    def test_user_without_special_status_is_rejected(self):
        user = make_user()
        self.client.force_authenticate(user=user)
        url = reverse("api_book_detail", kwargs={"pk": self.book.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_with_special_status_can_read_detail(self):
        user = grant_special_status(make_user())
        self.client.force_authenticate(user=user)
        url = reverse("api_book_detail", kwargs={"pk": self.book.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Clean Code")

    def test_superuser_can_read_detail_without_explicit_grant(self):
        admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pass12345"
        )
        self.client.force_authenticate(user=admin)
        url = reverse("api_book_detail", kwargs={"pk": self.book.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_requires_authentication(self):
        url = reverse("api_book_detail", kwargs={"pk": self.book.pk})
        response = self.client.get(url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class ReviewCreateAPIViewTests(APITestCase):
    def setUp(self):
        self.book = Book.objects.create(title="Clean Code", author="Robert C. Martin", price="45.00")
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def test_authenticated_user_can_post_review(self):
        url = reverse("api_review_create", kwargs={"book_pk": self.book.pk})
        response = self.client.post(url, {"review": "Très bon livre."})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Review.objects.count(), 1)
        review = Review.objects.first()
        self.assertEqual(review.author, self.user)
        self.assertEqual(review.book, self.book)

    def test_review_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse("api_review_create", kwargs={"book_pk": self.book.pk})
        response = self.client.post(url, {"review": "Test"})
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_review_on_nonexistent_book_returns_404(self):
        import uuid
        url = reverse("api_review_create", kwargs={"book_pk": uuid.uuid4()})
        response = self.client.post(url, {"review": "Test"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)