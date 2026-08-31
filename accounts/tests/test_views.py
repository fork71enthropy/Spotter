from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class RegisterViewTests(APITestCase):
    """Teste POST /api/register/"""

    def test_register_creates_user(self):
        url = reverse("api_register")
        response = self.client.post(url, {"email": "newuser@example.com", "password": "StrongPass123"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())
        # Le mot de passe ne doit jamais être renvoyé dans la réponse
        self.assertNotIn("password", response.data)

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(username="existing", email="dup@example.com", password="whatever123")
        url = reverse("api_register")
        response = self.client.post(url, {"email": "dup@example.com", "password": "StrongPass123"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_rejects_weak_password(self):
        url = reverse("api_register")
        response = self.client.post(url, {"email": "weak@example.com", "password": "1234"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TokenObtainViewTests(APITestCase):
    """Teste POST /api/token/ (login JWT par email)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="loginuser", email="login@example.com", password="CorrectPass123"
        )

    def test_login_with_correct_credentials(self):
        url = reverse("token_obtain_pair")
        response = self.client.post(url, {"email": "login@example.com", "password": "CorrectPass123"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_wrong_password_fails(self):
        url = reverse("token_obtain_pair")
        response = self.client.post(url, {"email": "login@example.com", "password": "WrongPassword"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_with_unknown_email_fails(self):
        url = reverse("token_obtain_pair")
        response = self.client.post(url, {"email": "ghost@example.com", "password": "whatever123"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MeViewTests(APITestCase):
    """Teste GET/PATCH /api/me/"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="meuser", email="me@example.com", password="CorrectPass123"
        )

    def _get_access_token(self):
        url = reverse("token_obtain_pair")
        response = self.client.post(url, {"email": "me@example.com", "password": "CorrectPass123"})
        return response.data["access"]

    def test_me_requires_authentication(self):
        url = reverse("api_me")
        response = self.client.get(url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_me_returns_profile_when_authenticated(self):
        access = self._get_access_token()
        url = reverse("api_me")
        response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "me@example.com")
        self.assertEqual(response.data["hours"], 20)

    def test_me_can_edit_email(self):
        access = self._get_access_token()
        url = reverse("api_me")
        response = self.client.patch(url, {"email": "newemail@example.com"}, HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "newemail@example.com")

    def test_me_cannot_edit_hours(self):
        access = self._get_access_token()
        url = reverse("api_me")
        response = self.client.patch(url, {"hours": 999}, HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.hours, 20)  # inchangé : champ read-only


class ChangePasswordViewTests(APITestCase):
    """Teste POST /api/change-password/"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="pwuser", email="pw@example.com", password="OldPass123"
        )
        response = self.client.post(
            reverse("token_obtain_pair"), {"email": "pw@example.com", "password": "OldPass123"}
        )
        self.access = response.data["access"]

    def test_change_password_with_correct_old_password(self):
        url = reverse("api_change_password")
        response = self.client.post(
            url,
            {"old_password": "OldPass123", "new_password": "NewPass456"},
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass456"))

    def test_change_password_rejects_wrong_old_password(self):
        url = reverse("api_change_password")
        response = self.client.post(
            url,
            {"old_password": "WrongOld", "new_password": "NewPass456"},
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_requires_authentication(self):
        url = reverse("api_change_password")
        response = self.client.post(url, {"old_password": "OldPass123", "new_password": "NewPass456"})
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class LogoutViewTests(APITestCase):
    """Teste POST /api/logout/"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="logoutuser", email="logout@example.com", password="Pass123456"
        )
        response = self.client.post(
            reverse("token_obtain_pair"), {"email": "logout@example.com", "password": "Pass123456"}
        )
        self.access = response.data["access"]
        self.refresh = response.data["refresh"]

    def test_logout_blacklists_refresh_token(self):
        url = reverse("api_logout")
        response = self.client.post(
            url, {"refresh": self.refresh}, HTTP_AUTHORIZATION=f"Bearer {self.access}"
        )
        self.assertEqual(response.status_code, 205)

        refresh_response = self.client.post(reverse("token_refresh"), {"refresh": self.refresh})
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authentication(self):
        url = reverse("api_logout")
        response = self.client.post(url, {"refresh": self.refresh})
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))