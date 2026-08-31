from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase

from alerts.models import WatchedSlot

User = get_user_model()


class WatchedSlotModelTests(TestCase):
    def test_str_representation(self):
        user = User.objects.create_user(username="etu", email="etu@example.com", password="pass12345")
        watch = WatchedSlot.objects.create(
            utilisateur=user,
            site_id="fc134457-489e-43aa-8a75-bc2853a3509a",
            site_nom="BU Rockefeller",
            resource_id=758,
            resource_nom="Carrel 03",
            date_cible=date(2026, 9, 1),
            heure_debut=time(14, 0),
            heure_fin=time(18, 0),
        )
        self.assertIn("Carrel 03", str(watch))
        self.assertIn("2026-09-01", str(watch))
