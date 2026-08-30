from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from Reservation.models import Carel, Creneau, Reservation

User = get_user_model()


def make_user(**kwargs):
    defaults = {"username": "etudiant", "email": "etudiant@example.com", "password": "pass12345", "hours": 20}
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


class CarelListViewTests(APITestCase):
    def setUp(self):
        self.etudiant = make_user()
        self.client.force_authenticate(user=self.etudiant)

    def test_list_carels(self):
        Carel.objects.create(numero=101, etage=1, nb_places=2)
        Carel.objects.create(numero=102, etage=1, nb_places=1)
        url = reverse("api_carel_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # La pagination DRF enveloppe la liste dans {"count","next","previous","results"}
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 2)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse("api_carel_list")
        response = self.client.get(url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class ReservationListCreateViewTests(APITestCase):
    def setUp(self):
        self.etudiant = make_user()
        self.carel = Carel.objects.create(numero=101, etage=1, nb_places=2)
        self.client.force_authenticate(user=self.etudiant)

    def _payload(self, **overrides):
        payload = {
            "carel": str(self.carel.id),
            "date": "2026-09-01T10:00:00Z",
            "duration": 3,
        }
        payload.update(overrides)
        return payload

    def test_create_reservation_deducts_hours(self):
        url = reverse("api_reservation_list_create")
        response = self.client.post(url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.etudiant.refresh_from_db()
        self.assertEqual(self.etudiant.hours, 17)  # 20 - 3
        self.assertEqual(Reservation.objects.count(), 1)

    def test_list_only_shows_my_reservations(self):
        autre = make_user(username="autre", email="autre@example.com")
        creneau = Creneau.objects.create(date=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc), duration=1)
        Reservation.objects.create(etudiant=autre, carel=self.carel, creneau=creneau)

        url = reverse("api_reservation_list_create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)  # aucune réservation ne m'appartient

    def test_create_rejects_when_carel_full(self):
        carel_plein = Carel.objects.create(numero=999, etage=1, nb_places=1)
        creneau = Creneau.objects.create(date=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc), duration=1)
        Reservation.objects.create(
            etudiant=make_user(username="premier", email="premier@example.com"),
            carel=carel_plein,
            creneau=creneau,
        )

        url = reverse("api_reservation_list_create")
        response = self.client.post(
            url,
            {"carel": str(carel_plein.id), "date": "2026-09-01T10:00:00Z", "duration": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse("api_reservation_list_create")
        response = self.client.post(url, self._payload(), format="json")
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class ReservationCancelViewTests(APITestCase):
    def setUp(self):
        self.etudiant = make_user(hours=15)
        self.carel = Carel.objects.create(numero=101, etage=1, nb_places=2)
        self.creneau = Creneau.objects.create(
            date=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc), duration=3
        )
        self.reservation = Reservation.objects.create(
            etudiant=self.etudiant, carel=self.carel, creneau=self.creneau
        )
        self.client.force_authenticate(user=self.etudiant)

    def test_cancel_refunds_hours(self):
        url = reverse("api_reservation_cancel", kwargs={"pk": self.reservation.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.etudiant.refresh_from_db()
        self.assertEqual(self.etudiant.hours, 18)  # 15 + 3
        self.assertFalse(Reservation.objects.filter(pk=self.reservation.pk).exists())

    def test_cannot_cancel_someone_elses_reservation(self):
        autre = make_user(username="autre", email="autre@example.com")
        self.client.force_authenticate(user=autre)

        url = reverse("api_reservation_cancel", kwargs={"pk": self.reservation.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Reservation.objects.filter(pk=self.reservation.pk).exists())