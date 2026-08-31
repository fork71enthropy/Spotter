from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from alerts.affluences_client import AffluencesError
from alerts.models import WatchedSlot

from .fixtures import AFFLUENCES_SAMPLE_RESPONSE

User = get_user_model()


def make_user(**kwargs):
    defaults = {"username": "etu", "email": "etu@example.com", "password": "pass12345"}
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


class RoomsAvailabilityAPIViewTests(APITestCase):
    """
    On mocke systématiquement fetch_availability() : on ne veut JAMAIS
    qu'un test fasse un vrai appel réseau vers reservation.affluences.com
    (lent, non déterministe, et malpoli envers un service tiers).
    """

    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    @patch("alerts.views.fetch_availability")
    def test_returns_rooms_from_affluences(self, mock_fetch):
        mock_fetch.return_value = AFFLUENCES_SAMPLE_RESPONSE
        url = reverse("api_alerts_rooms")
        response = self.client.get(url, {"date": "2026-09-01"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 4)
        mock_fetch.assert_called_once()

    def test_missing_date_param_rejected(self):
        url = reverse("api_alerts_rooms")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("alerts.views.fetch_availability")
    def test_affluences_error_returns_502(self, mock_fetch):
        mock_fetch.side_effect = AffluencesError("timeout")
        url = reverse("api_alerts_rooms")
        response = self.client.get(url, {"date": "2026-09-01"})
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse("api_alerts_rooms")
        response = self.client.get(url, {"date": "2026-09-01"})
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class WatchedSlotViewTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def _payload(self, **overrides):
        payload = {
            "resource_id": 758,
            "resource_nom": "Carrel 03",
            "date_cible": str(date.today() + timedelta(days=1)),
            "heure_debut": "14:00",
            "heure_fin": "18:00",
        }
        payload.update(overrides)
        return payload

    def test_create_watch(self):
        url = reverse("api_watch_list_create")
        response = self.client.post(url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(WatchedSlot.objects.count(), 1)
        self.assertEqual(WatchedSlot.objects.first().utilisateur, self.user)

    def test_list_only_shows_my_watches(self):
        autre = make_user(username="autre", email="autre@example.com")
        WatchedSlot.objects.create(
            utilisateur=autre,
            site_id="x",
            site_nom="x",
            resource_id=1,
            resource_nom="Autre salle",
            date_cible=date.today() + timedelta(days=1),
            heure_debut=time(9, 0),
            heure_fin=time(10, 0),
        )
        url = reverse("api_watch_list_create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_cancel_own_watch(self):
        watch = WatchedSlot.objects.create(
            utilisateur=self.user,
            site_id="x",
            site_nom="x",
            resource_id=1,
            resource_nom="Salle",
            date_cible=date.today() + timedelta(days=1),
            heure_debut=time(9, 0),
            heure_fin=time(10, 0),
        )
        url = reverse("api_watch_cancel", kwargs={"pk": watch.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(WatchedSlot.objects.filter(pk=watch.pk).exists())

    def test_cannot_cancel_someone_elses_watch(self):
        autre = make_user(username="autre", email="autre@example.com")
        watch = WatchedSlot.objects.create(
            utilisateur=autre,
            site_id="x",
            site_nom="x",
            resource_id=1,
            resource_nom="Salle",
            date_cible=date.today() + timedelta(days=1),
            heure_debut=time(9, 0),
            heure_fin=time(10, 0),
        )
        url = reverse("api_watch_cancel", kwargs={"pk": watch.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(WatchedSlot.objects.filter(pk=watch.pk).exists())

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse("api_watch_list_create")
        response = self.client.get(url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
