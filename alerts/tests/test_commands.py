from datetime import date, time, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from alerts.affluences_client import AffluencesError
from alerts.models import WatchedSlot

from .fixtures import AFFLUENCES_SAMPLE_RESPONSE

User = get_user_model()


def make_user(**kwargs):
    defaults = {"username": "etu", "email": "etu@example.com", "password": "pass12345"}
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def make_watch(user, **kwargs):
    defaults = {
        "site_id": "fc134457-489e-43aa-8a75-bc2853a3509a",
        "site_nom": "BU Rockefeller",
        "resource_id": 758,
        "resource_nom": "Carrel 03",
        "date_cible": date.today() + timedelta(days=1),
        "heure_debut": time(16, 0),
        "heure_fin": time(19, 0),
    }
    defaults.update(kwargs)
    return WatchedSlot.objects.create(utilisateur=user, **defaults)


class PollAffluencesCommandTests(TestCase):
    def setUp(self):
        self.user = make_user()

    @patch("alerts.management.commands.poll_affluences.fetch_availability")
    def test_notifies_when_slot_becomes_available(self, mock_fetch):
        mock_fetch.return_value = AFFLUENCES_SAMPLE_RESPONSE
        # Carrel 03 (id 758) est "available" de 16h à 19h dans la fixture
        watch = make_watch(self.user, resource_id=758, heure_debut=time(16, 0), heure_fin=time(19, 0))

        out = StringIO()
        call_command("poll_affluences", "--once", stdout=out)

        watch.refresh_from_db()
        self.assertIsNotNone(watch.notifie_le)
        self.assertIn("ALERTE", out.getvalue())

    @patch("alerts.management.commands.poll_affluences.fetch_availability")
    def test_does_not_notify_when_room_fully_booked(self, mock_fetch):
        mock_fetch.return_value = AFFLUENCES_SAMPLE_RESPONSE
        # Carrel 02 (id 757) est complet ("hours" vide) dans la fixture
        watch = make_watch(
            self.user, resource_id=757, resource_nom="Carrel 02",
            heure_debut=time(8, 0), heure_fin=time(20, 0),
        )

        call_command("poll_affluences", "--once", stdout=StringIO())

        watch.refresh_from_db()
        self.assertIsNone(watch.notifie_le)

    @patch("alerts.management.commands.poll_affluences.fetch_availability")
    def test_already_notified_watch_is_skipped(self, mock_fetch):
        mock_fetch.return_value = AFFLUENCES_SAMPLE_RESPONSE
        from django.utils import timezone as dj_timezone

        watch = make_watch(self.user, resource_id=758)
        watch.notifie_le = dj_timezone.now()
        watch.save(update_fields=["notifie_le"])

        call_command("poll_affluences", "--once", stdout=StringIO())

        # Un watch déjà notifié ne doit générer aucun nouvel appel API
        mock_fetch.assert_not_called()

    @patch("alerts.management.commands.poll_affluences.fetch_availability")
    def test_single_api_call_for_multiple_watchers_same_day(self, mock_fetch):
        # Deux étudiants différents surveillent des carrels différents le
        # même jour -> un seul appel API doit suffire pour les deux.
        mock_fetch.return_value = AFFLUENCES_SAMPLE_RESPONSE
        autre = make_user(username="autre", email="autre@example.com")
        make_watch(self.user, resource_id=758)
        make_watch(autre, resource_id=760, heure_debut=time(18, 0), heure_fin=time(20, 0))

        call_command("poll_affluences", "--once", stdout=StringIO())

        self.assertEqual(mock_fetch.call_count, 1)

    @patch("alerts.management.commands.poll_affluences.fetch_availability")
    def test_affluences_error_does_not_crash_the_command(self, mock_fetch):
        mock_fetch.side_effect = AffluencesError("timeout")
        watch = make_watch(self.user, resource_id=758)

        # Ne doit lever aucune exception, juste écrire un avertissement.
        call_command("poll_affluences", "--once", stdout=StringIO(), stderr=StringIO())

        watch.refresh_from_db()
        self.assertIsNone(watch.notifie_le)

    @patch("alerts.management.commands.poll_affluences.fetch_availability")
    def test_past_or_inactive_watches_ignored(self, mock_fetch):
        mock_fetch.return_value = AFFLUENCES_SAMPLE_RESPONSE
        make_watch(self.user, resource_id=758, date_cible=date.today() - timedelta(days=1))
        make_watch(self.user, resource_id=760, est_actif=False)

        call_command("poll_affluences", "--once", stdout=StringIO())

        # Aucun watch valide -> aucun appel API déclenché
        mock_fetch.assert_not_called()
