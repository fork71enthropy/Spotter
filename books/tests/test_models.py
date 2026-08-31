from django.contrib.auth import get_user_model
from django.test import TestCase

from books.models import Book, Review

User = get_user_model()


class BookModelTests(TestCase):
    def test_create_book(self):
        book = Book.objects.create(title="Clean Code", author="Robert C. Martin", price="45.00")
        self.assertEqual(str(book), "Clean Code")

    def test_special_status_permission_exists(self):
        # Cette permission est déclarée dans Book.Meta.permissions -> elle doit
        # être bien créée en base par Django (via post_migrate), sinon
        # HasSpecialStatus ne pourra jamais fonctionner.
        from django.contrib.auth.models import Permission
        self.assertTrue(
            Permission.objects.filter(codename="special_status", content_type__app_label="books").exists()
        )


class ReviewModelTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(title="Effective Python", author="Brett Slatkin", price="39.99")
        self.author = User.objects.create_user(
            username="reviewer", email="reviewer@example.com", password="pass12345"
        )

    def test_create_review(self):
        review = Review.objects.create(book=self.book, author=self.author, review="Excellent livre.")
        self.assertEqual(str(review), "Excellent livre.")
        self.assertIn(review, self.book.reviews.all())