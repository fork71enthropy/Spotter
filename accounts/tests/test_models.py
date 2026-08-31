from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


class CustomUserModelTests(TestCase):
    """Tests unitaires sur accounts/models.py (CustomUser)."""

    def test_create_user(self):
        user = User.objects.create_user(
            username="will", email="will@email.com", password="testpass123"
        )
        self.assertEqual(user.username, "will")
        self.assertEqual(user.email, "will@email.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        admin_user = User.objects.create_superuser(
            username="superadmin", email="superadmin@email.com", password="testpass123"
        )
        self.assertTrue(admin_user.is_active)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)

    def test_hours_defaults_to_20(self):
        user = User.objects.create_user(
            username="defaulthours", email="defaulthours@email.com", password="testpass123"
        )
        self.assertEqual(user.hours, 20)

    def test_email_must_be_unique(self):
        User.objects.create_user(
            username="first", email="dup@email.com", password="testpass123"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username="second", email="dup@email.com", password="testpass123"
                )