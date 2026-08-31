# Extrait RÉEL de la réponse de l'API Affluences pour BU Rockefeller
# (capturé le 31/08/2026 via les DevTools, cf. discussion avec l'utilisateur).
# Recadré à quelques carrels représentatifs, mais structure et valeurs
# intactes -- couvre les 3 états observés : available, full (avec hours
# vide quand tout est pris), closed (fermé, hours vide aussi).

AFFLUENCES_SAMPLE_RESPONSE = [
    {
        "resource_id": 758,
        "resource_name": "Carrel 03",
        "resource_type": 2,
        "granularity": 60,
        "capacity": 1,
        "slots_state": "available",
        "hours": [
            {"hour": "16:00", "state": "available", "places_available": 1, "places_bookable": 1},
            {"hour": "17:00", "state": "available", "places_available": 1, "places_bookable": 1},
            {"hour": "18:00", "state": "available", "places_available": 1, "places_bookable": 1},
            {"hour": "19:00", "state": "available", "places_available": 1, "places_bookable": 1},
        ],
    },
    {
        "resource_id": 760,
        "resource_name": "Carrel 05",
        "resource_type": 2,
        "granularity": 60,
        "capacity": 1,
        "slots_state": "available",
        "hours": [
            {"hour": "16:00", "state": "available", "places_available": 1, "places_bookable": 1},
            {"hour": "17:00", "state": "full", "places_available": 0, "places_bookable": 0},
            {"hour": "18:00", "state": "available", "places_available": 1, "places_bookable": 1},
            {"hour": "19:00", "state": "available", "places_available": 1, "places_bookable": 1},
        ],
    },
    {
        # Carrel totalement complet : "hours" est VIDE, pas rempli de
        # state="full" -> le parsing doit s'en sortir sans planter.
        "resource_id": 757,
        "resource_name": "Carrel 02",
        "resource_type": 2,
        "granularity": 60,
        "capacity": 1,
        "slots_state": "full",
        "hours": [],
    },
    {
        # Carrel fermé (salle pas encore ouverte ce jour-là, réouverture
        # plus tard) : même chose, "hours" vide.
        "resource_id": 24017,
        "resource_name": "Carrel 30",
        "resource_type": 2,
        "granularity": 60,
        "capacity": 2,
        "slots_state": "closed",
        "hours": [],
        "next_open_day": "2026-09-07",
    },
]