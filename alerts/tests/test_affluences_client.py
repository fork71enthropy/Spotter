from datetime import time

from django.test import TestCase

from alerts.affluences_client import libres_dans_la_plage

from .fixtures import AFFLUENCES_SAMPLE_RESPONSE


class LibresDansLaPlageTests(TestCase):
    """
    Teste la logique de parsing sur de VRAIES données capturées depuis
    l'API Affluences pour BU Rockefeller (voir fixtures.py) -> si
    Affluences change subtilement la forme de sa réponse, ce test le
    détectera.
    """

    def test_room_fully_available_in_range(self):
        # Carrel 03 (id 758) : entièrement libre de 16h à 19h
        libres = libres_dans_la_plage(
            AFFLUENCES_SAMPLE_RESPONSE, resource_id=758, heure_debut=time(16, 0), heure_fin=time(19, 0)
        )
        self.assertEqual(libres, ["16:00", "17:00", "18:00"])

    def test_room_partially_full_in_range(self):
        # Carrel 05 (id 760) : libre à 16h, complet à 17h, libre à 18h/19h
        libres = libres_dans_la_plage(
            AFFLUENCES_SAMPLE_RESPONSE, resource_id=760, heure_debut=time(16, 0), heure_fin=time(18, 0)
        )
        self.assertEqual(libres, ["16:00"])  # 17:00 exclu (full)

    def test_room_available_slot_appears_after_full_period(self):
        libres = libres_dans_la_plage(
            AFFLUENCES_SAMPLE_RESPONSE, resource_id=760, heure_debut=time(17, 0), heure_fin=time(20, 0)
        )
        self.assertEqual(libres, ["18:00", "19:00"])

    def test_fully_booked_room_has_empty_hours_not_full_entries(self):
        # Particularité de Rockefeller découverte en vrai : un carel complet
        # n'a PAS des entrées state="full", "hours" est carrément vide.
        # Le parsing doit s'en sortir sans planter et renvoyer [].
        libres = libres_dans_la_plage(
            AFFLUENCES_SAMPLE_RESPONSE, resource_id=757, heure_debut=time(8, 0), heure_fin=time(20, 0)
        )
        self.assertEqual(libres, [])

    def test_closed_room_has_empty_hours(self):
        libres = libres_dans_la_plage(
            AFFLUENCES_SAMPLE_RESPONSE, resource_id=24017, heure_debut=time(8, 0), heure_fin=time(20, 0)
        )
        self.assertEqual(libres, [])

    def test_unknown_resource_id_returns_empty(self):
        libres = libres_dans_la_plage(
            AFFLUENCES_SAMPLE_RESPONSE, resource_id=999999, heure_debut=time(8, 0), heure_fin=time(20, 0)
        )
        self.assertEqual(libres, [])

    def test_range_boundaries_are_half_open(self):
        # [debut, fin) : l'heure de fin elle-même n'est PAS incluse.
        libres = libres_dans_la_plage(
            AFFLUENCES_SAMPLE_RESPONSE, resource_id=758, heure_debut=time(16, 0), heure_fin=time(17, 0)
        )
        self.assertEqual(libres, ["16:00"])  # 17:00 exclu car == heure_fin