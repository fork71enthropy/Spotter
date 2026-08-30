from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from Reservation.models import Carel, Creneau, Reservation

User = get_user_model()


def make_user(**kwargs):
    defaults = {"username": "etudiant", "email": "etudiant@example.com", "password": "pass12345"}
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


class CarelModelTests(TestCase):
    def test_create_valid_carel(self):
        carel = Carel.objects.create(numero=101, etage=1, nb_places=2)
        self.assertEqual(carel.numero, 101)
        self.assertIn("Carel 101", str(carel))

    def test_numero_out_of_range_rejected(self):
        carel = Carel(numero=1, etage=0, nb_places=1)  # min autorisé = 2
        with self.assertRaises(ValidationError):
            carel.full_clean()


class CreneauModelTests(TestCase):
    def test_valid_creneau_on_the_half_hour(self):
        creneau = Creneau(date=datetime(2026, 9, 1, 10, 30, tzinfo=timezone.utc), duration=2)
        creneau.save()  # save() appelle full_clean() en interne
        self.assertEqual(creneau.duration, 2)

    def test_creneau_not_on_half_hour_rejected(self):
        creneau = Creneau(date=datetime(2026, 9, 1, 10, 15, tzinfo=timezone.utc), duration=1)
        with self.assertRaises(ValidationError):
            creneau.save()

    def test_creneau_before_opening_rejected(self):
        creneau = Creneau(date=datetime(2026, 9, 1, 7, 30, tzinfo=timezone.utc), duration=1)
        with self.assertRaises(ValidationError):
            creneau.save()

    def test_creneau_after_closing_rejected(self):
        creneau = Creneau(date=datetime(2026, 9, 1, 20, 0, tzinfo=timezone.utc), duration=1)
        with self.assertRaises(ValidationError):
            creneau.save()


class ReservationModelTests(TestCase):
    def setUp(self):
        self.carel = Carel.objects.create(numero=101, etage=1, nb_places=2)
        self.creneau = Creneau.objects.create(
            date=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc), duration=2
        )
        self.etudiant = make_user()

    def test_create_reservation(self):
        reservation = Reservation.objects.create(
            etudiant=self.etudiant, carel=self.carel, creneau=self.creneau
        )
        self.assertEqual(reservation.etudiant, self.etudiant)

    def test_same_student_cannot_double_book_same_slot(self):
        Reservation.objects.create(etudiant=self.etudiant, carel=self.carel, creneau=self.creneau)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Reservation.objects.create(
                    etudiant=self.etudiant, carel=self.carel, creneau=self.creneau
                )

    def test_two_different_students_can_share_same_slot(self):
        # nb_places=2 sur ce carel : deux étudiants différents doivent pouvoir
        # réserver le même carel/créneau sans que la base ne s'y oppose.
        autre_etudiant = make_user(username="autre", email="autre@example.com")
        Reservation.objects.create(etudiant=self.etudiant, carel=self.carel, creneau=self.creneau)
        Reservation.objects.create(etudiant=autre_etudiant, carel=self.carel, creneau=self.creneau)
        self.assertEqual(
            Reservation.objects.filter(carel=self.carel, creneau=self.creneau).count(), 2
        )