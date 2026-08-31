from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from alerts.constants import AFFLUENCES_SITE_ID, AFFLUENCES_SITE_NOM
from alerts.serializers import WatchedSlotSerializer

User = get_user_model()
factory = APIRequestFactory()


class WatchedSlotSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="etu", email="etu@example.com", password="pass12345")
        request = factory.post("/api/alerts/watches/")
        request.user = self.user
        self.request = request

    def _valid_payload(self, **overrides):
        payload = {
            "resource_id": 758,
            "resource_nom": "Carrel 03",
            "date_cible": date.today() + timedelta(days=1),
            "heure_debut": time(14, 0),
            "heure_fin": time(18, 0),
        }
        payload.update(overrides)
        return payload

    def test_valid_payload_creates_watch_with_fixed_site(self):
        serializer = WatchedSlotSerializer(data=self._valid_payload(), context={"request": self.request})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        watch = serializer.save()
        self.assertEqual(watch.utilisateur, self.user)
        self.assertEqual(watch.site_id, AFFLUENCES_SITE_ID)
        self.assertEqual(watch.site_nom, AFFLUENCES_SITE_NOM)

    def test_heure_fin_before_heure_debut_rejected(self):
        payload = self._valid_payload(heure_debut=time(18, 0), heure_fin=time(14, 0))
        serializer = WatchedSlotSerializer(data=payload, context={"request": self.request})
        self.assertFalse(serializer.is_valid())

    def test_heure_fin_equal_to_heure_debut_rejected(self):
        payload = self._valid_payload(heure_debut=time(14, 0), heure_fin=time(14, 0))
        serializer = WatchedSlotSerializer(data=payload, context={"request": self.request})
        self.assertFalse(serializer.is_valid())

    def test_past_date_rejected(self):
        payload = self._valid_payload(date_cible=date.today() - timedelta(days=1))
        serializer = WatchedSlotSerializer(data=payload, context={"request": self.request})
        self.assertFalse(serializer.is_valid())

    def test_client_cannot_override_site(self):
        # Même si le client envoie site_id/site_nom dans le payload, ils
        # doivent être ignorés (read_only + toujours réécrits dans create()).
        payload = self._valid_payload(site_id="autre-site", site_nom="Autre site")
        serializer = WatchedSlotSerializer(data=payload, context={"request": self.request})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        watch = serializer.save()
        self.assertEqual(watch.site_id, AFFLUENCES_SITE_ID)
