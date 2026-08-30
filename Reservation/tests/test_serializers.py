from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from Reservation.models import Carel, Creneau, Reservation
from Reservation.serializers import ReservationCreateSerializer

User = get_user_model()
factory = APIRequestFactory()


def make_user(**kwargs):
    defaults = {"username": "etudiant", "email": "etudiant@example.com", "password": "pass12345", "hours": 20}
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


class ReservationCreateSerializerTests(TestCase):
    def setUp(self):
        self.carel = Carel.objects.create(numero=101, etage=1, nb_places=1)
        self.etudiant = make_user()
        self.request = factory.post("/api/reservation/reservations/")
        self.request.user = self.etudiant

    def _valid_payload(self, **overrides):
        payload = {
            "carel": self.carel.id,
            "date": datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            "duration": 2,
        }
        payload.update(overrides)
        return payload

    def test_creates_reservation_and_deducts_hours(self):
        serializer = ReservationCreateSerializer(
            data=self._valid_payload(), context={"request": self.request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        reservation = serializer.save()

        self.assertEqual(reservation.etudiant, self.etudiant)
        self.etudiant.refresh_from_db()
        self.assertEqual(self.etudiant.hours, 18)  # 20 - 2

    def test_creates_creneau_on_the_fly_if_it_does_not_exist(self):
        self.assertEqual(Creneau.objects.count(), 0)
        serializer = ReservationCreateSerializer(
            data=self._valid_payload(), context={"request": self.request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.assertEqual(Creneau.objects.count(), 1)

    def test_invalid_time_slot_rejected(self):
        # 10h15 n'est pas une heure lisse (0 ou 30 min)
        payload = self._valid_payload(date=datetime(2026, 9, 1, 10, 15, tzinfo=timezone.utc))
        serializer = ReservationCreateSerializer(data=payload, context={"request": self.request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("date", serializer.errors)

    def test_full_carel_rejected(self):
        # nb_places=1 sur ce carel : le premier étudiant prend l'unique place...
        creneau = Creneau.objects.create(date=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc), duration=2)
        Reservation.objects.create(
            etudiant=make_user(username="premier", email="premier@example.com"),
            carel=self.carel,
            creneau=creneau,
        )
        # ...donc un second étudiant doit être refusé sur ce même créneau
        serializer = ReservationCreateSerializer(
            data=self._valid_payload(), context={"request": self.request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(ValidationError):
            serializer.save()

    def test_insufficient_hours_rejected(self):
        etudiant_pauvre = make_user(username="pauvre", email="pauvre@example.com", hours=1)
        request = factory.post("/api/reservation/reservations/")
        request.user = etudiant_pauvre

        serializer = ReservationCreateSerializer(
            data=self._valid_payload(duration=2), context={"request": request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(ValidationError):
            serializer.save()

    def test_duplicate_booking_by_same_student_rejected(self):
        creneau = Creneau.objects.create(date=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc), duration=2)
        Reservation.objects.create(etudiant=self.etudiant, carel=self.carel, creneau=creneau)

        serializer = ReservationCreateSerializer(
            data=self._valid_payload(), context={"request": self.request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(ValidationError):
            serializer.save()