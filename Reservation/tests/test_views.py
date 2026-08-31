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





class CarelAvailabilityAPIViewTests(APITestCase):
    def setUp(self):
        self.etudiant = make_user()
        self.client.force_authenticate(user=self.etudiant)
        self.carel = Carel.objects.create(numero=101, etage=1, nb_places=2)

    def test_missing_params_rejected(self):
        url = reverse("api_carel_availability")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_date_format_rejected(self):
        url = reverse("api_carel_availability")
        response = self.client.get(url, {"date": "pas-une-date", "duration": "2"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_slot_never_booked_is_fully_available(self):
        url = reverse("api_carel_availability")
        response = self.client.get(url, {"date": "2026-09-01T10:00:00Z", "duration": "2"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        carel_data = next(c for c in response.data if c["id"] == str(self.carel.id))
        self.assertTrue(carel_data["disponible"])

    def test_any_existing_reservation_makes_it_unavailable(self):
        # nb_places=2 sur ce carel, mais UNE SEULE réservation suffit à le
        # bloquer : nb_places n'est qu'une info de capacité, pas un nombre
        # de réservations concurrentes autorisées.
        creneau = Creneau.objects.create(date=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc), duration=2)
        Reservation.objects.create(etudiant=self.etudiant, carel=self.carel, creneau=creneau)

        url = reverse("api_carel_availability")
        response = self.client.get(url, {"date": "2026-09-01T10:00:00Z", "duration": "2"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        carel_data = next(c for c in response.data if c["id"] == str(self.carel.id))
        self.assertFalse(carel_data["disponible"])

    def test_overlapping_reservation_makes_it_unavailable(self):
        carel_solo = Carel.objects.create(numero=202, etage=2, nb_places=1)
        creneau = Creneau.objects.create(date=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc), duration=2)
        Reservation.objects.create(etudiant=self.etudiant, carel=carel_solo, creneau=creneau)

        url = reverse("api_carel_availability")
        response = self.client.get(url, {"date": "2026-09-01T10:00:00Z", "duration": "2"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        carel_data = next(c for c in response.data if c["id"] == str(carel_solo.id))
        self.assertFalse(carel_data["disponible"])

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse("api_carel_availability")
        response = self.client.get(url, {"date": "2026-09-01T10:00:00Z", "duration": "2"})
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))




class CarelDailyAvailabilityAPIViewTests(APITestCase):

    def setUp(self):
        self.etudiant = make_user()
        self.client.force_authenticate(user=self.etudiant)
        self.carel = Carel.objects.create(numero=101, etage=1, nb_places=2)

    def _today_at(self, hour, minute=0):
        from django.utils import timezone as dj_timezone
        today = dj_timezone.localdate()
        return dj_timezone.make_aware(datetime(today.year, today.month, today.day, hour, minute))

    def test_no_params_returns_full_day_1h_slots(self):
        url = reverse("api_carel_daily_availability")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        carel_data = next(c for c in response.data if c["id"] == str(self.carel.id))
        # De 08:00 à 19:00 par pas de 30 min -> 23 créneaux candidats
        self.assertEqual(len(carel_data["creneaux_libres"]), 23)
        heures = [c["heure"] for c in carel_data["creneaux_libres"]]
        self.assertIn("08:00", heures)
        self.assertIn("19:00", heures)
        # Chaque créneau doit aussi porter une date ISO complète, exploitable
        # telle quelle par le front pour réserver (pas de reconstruction de
        # date côté JS -> pas de risque de décalage de fuseau horaire).
        self.assertIn("date", carel_data["creneaux_libres"][0])

    def test_fully_booked_slot_disappears_from_list(self):
        creneau_9h = Creneau.objects.create(date=self._today_at(9), duration=1)
        Reservation.objects.create(etudiant=self.etudiant, carel=self.carel, creneau=creneau_9h)
        autre = make_user(username="autre", email="autre@example.com")
        Reservation.objects.create(etudiant=autre, carel=self.carel, creneau=creneau_9h)

        url = reverse("api_carel_daily_availability")
        response = self.client.get(url)
        carel_data = next(c for c in response.data if c["id"] == str(self.carel.id))
        heures = [c["heure"] for c in carel_data["creneaux_libres"]]
        # 09:00-10:00 est complet (2/2 places) -> tout créneau candidat de 1h
        # dont la fenêtre chevauche [09:00,10:00) doit disparaître : 08:30
        # (08h30-09h30), 09:00, et 09:30 (09h30-10h30).
        self.assertNotIn("08:30", heures)
        self.assertNotIn("09:00", heures)
        self.assertNotIn("09:30", heures)
        # Les créneaux qui ne chevauchent PAS (juste avant/après), eux, restent libres
        self.assertIn("08:00", heures)
        self.assertIn("10:00", heures)

    def test_overlap_detected_across_different_durations(self):
        # Reproduit exactement le scénario signalé : une réservation de 2h à
        # 10h00 (donc 10h00-12h00) doit bloquer TOUTE tentative de 1h qui
        # chevauche cette plage, même si ce n'est pas exactement 10h00.
        carel_solo = Carel.objects.create(numero=303, etage=3, nb_places=1)
        creneau_2h = Creneau.objects.create(date=self._today_at(10), duration=2)
        Reservation.objects.create(etudiant=self.etudiant, carel=carel_solo, creneau=creneau_2h)

        url = reverse("api_carel_daily_availability")
        response = self.client.get(url)  # duration=1 par défaut
        carel_data = next(c for c in response.data if c["id"] == str(carel_solo.id))
        heures = [c["heure"] for c in carel_data["creneaux_libres"]]

        for heure_bloquee in ["09:30", "10:00", "10:30", "11:00", "11:30"]:
            self.assertNotIn(heure_bloquee, heures, f"{heure_bloquee} devrait être bloqué")
        for heure_libre in ["09:00", "12:00"]:
            self.assertIn(heure_libre, heures, f"{heure_libre} devrait rester libre")

    def test_any_reservation_blocks_regardless_of_nb_places(self):
        # nb_places=2 sur ce carel, mais UNE SEULE réservation suffit à
        # bloquer le créneau -> nb_places est juste une info de capacité
        # physique, pas un nombre de réservations concurrentes autorisées.
        creneau_9h = Creneau.objects.create(date=self._today_at(9), duration=1)
        Reservation.objects.create(etudiant=self.etudiant, carel=self.carel, creneau=creneau_9h)

        url = reverse("api_carel_daily_availability")
        response = self.client.get(url)
        carel_data = next(c for c in response.data if c["id"] == str(self.carel.id))
        heures = [c["heure"] for c in carel_data["creneaux_libres"]]
        self.assertNotIn("09:00", heures)

    def test_custom_duration_param(self):
        url = reverse("api_carel_daily_availability")
        response = self.client.get(url, {"duration": "2"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Une réservation de 1h sur ce même horaire n'affecte pas la recherche en 2h
        # (Creneau différent : (date, duration) est la clé) -> tout reste libre.
        carel_data = next(c for c in response.data if c["id"] == str(self.carel.id))
        self.assertEqual(len(carel_data["creneaux_libres"]), 23)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse("api_carel_daily_availability")
        response = self.client.get(url)
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))