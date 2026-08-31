from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.exceptions import AuthenticationFailed, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.serializers import (
    ChangePasswordSerializer,
    EmailTokenObtainPairSerializer,
    LogoutSerializer,
    RegisterSerializer,
)

User = get_user_model()
factory = APIRequestFactory()


class RegisterSerializerTests(TestCase):
    """Tests unitaires sur RegisterSerializer, sans passer par une vraie requête HTTP."""

    def test_valid_data_creates_user(self):
        serializer = RegisterSerializer(data={"email": "new@example.com", "password": "StrongPass123"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(user.email, "new@example.com")
        self.assertTrue(user.check_password("StrongPass123"))
        # Le username est généré automatiquement à partir de la partie avant le @
        self.assertEqual(user.username, "new")

    def test_duplicate_email_rejected(self):
        User.objects.create_user(username="existing", email="dup@example.com", password="whatever123")
        serializer = RegisterSerializer(data={"email": "dup@example.com", "password": "StrongPass123"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_weak_password_rejected(self):
        serializer = RegisterSerializer(data={"email": "weak@example.com", "password": "1234"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_username_collision_gets_suffixed(self):
        User.objects.create_user(username="dupname", email="dupname@old.com", password="whatever123")
        serializer = RegisterSerializer(data={"email": "dupname@new.com", "password": "StrongPass123"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertEqual(user.username, "dupname1")


class EmailTokenObtainPairSerializerTests(TestCase):
    """Tests unitaires sur le login JWT par email."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="loginuser", email="login@example.com", password="CorrectPass123"
        )

    def test_correct_credentials_return_tokens(self):
        request = factory.post("/api/token/")
        serializer = EmailTokenObtainPairSerializer(
            data={"email": "login@example.com", "password": "CorrectPass123"},
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn("access", serializer.validated_data)
        self.assertIn("refresh", serializer.validated_data)

    def test_wrong_password_rejected(self):
        request = factory.post("/api/token/")
        serializer = EmailTokenObtainPairSerializer(
            data={"email": "login@example.com", "password": "WrongPass"},
            context={"request": request},
        )
        # AuthenticationFailed n'est pas une ValidationError classique : elle
        # n'est pas absorbée par is_valid(), elle remonte telle quelle (c'est
        # la vue, pas le serializer, qui est censée l'attraper et en faire un 401).
        with self.assertRaises(AuthenticationFailed):
            serializer.is_valid()

    def test_unknown_email_rejected(self):
        request = factory.post("/api/token/")
        serializer = EmailTokenObtainPairSerializer(
            data={"email": "ghost@example.com", "password": "whatever123"},
            context={"request": request},
        )
        with self.assertRaises(AuthenticationFailed):
            serializer.is_valid()


class ChangePasswordSerializerTests(TestCase):
    """Tests unitaires sur le changement de mot de passe."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="pwuser", email="pw@example.com", password="OldPass123"
        )
        request = factory.post("/api/change-password/")
        request.user = self.user
        self.request = request

    def test_correct_old_password_changes_it(self):
        serializer = ChangePasswordSerializer(
            data={"old_password": "OldPass123", "new_password": "NewPass456"},
            context={"request": self.request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass456"))

    def test_wrong_old_password_rejected(self):
        serializer = ChangePasswordSerializer(
            data={"old_password": "WrongOld", "new_password": "NewPass456"},
            context={"request": self.request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("old_password", serializer.errors)

    def test_weak_new_password_rejected(self):
        serializer = ChangePasswordSerializer(
            data={"old_password": "OldPass123", "new_password": "1234"},
            context={"request": self.request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("new_password", serializer.errors)


class LogoutSerializerTests(TestCase):
    """Tests unitaires sur la révocation (blacklist) d'un refresh token."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="logoutuser", email="logout@example.com", password="Pass123456"
        )
        self.refresh = RefreshToken.for_user(self.user)

    def test_valid_refresh_gets_blacklisted(self):
        serializer = LogoutSerializer(data={"refresh": str(self.refresh)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        # Une fois blacklisté, le token doit être rejeté par sa propre vérification
        with self.assertRaises(TokenError):
            self.refresh.check_blacklist()

    def test_garbage_token_rejected_on_save(self):
        serializer = LogoutSerializer(data={"refresh": "not-a-real-token"})
        # Valide au niveau du champ (c'est juste une chaîne de caractères)...
        self.assertTrue(serializer.is_valid())
        # ...mais échoue à la vérification cryptographique du token lui-même
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            serializer.save()