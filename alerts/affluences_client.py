import requests

from .constants import AFFLUENCES_TYPE

AFFLUENCES_BASE_URL = "https://reservation.affluences.com/api"


class AffluencesError(Exception):
    """Levée quand l'appel à l'API Affluences échoue (réseau, timeout, réponse invalide)."""


def fetch_availability(site_id, date_str, start_hour="08:00", timeout=10):
    """
    Appelle l'API (non-officielle) d'Affluences et renvoie la liste brute
    des salles du site avec leur planning pour la journée demandée.

    Un seul appel renvoie TOUTES les salles du site (pas une par salle) :
    on appelle donc ceci une fois par (site, jour) surveillé, jamais une
    fois par WatchedSlot individuel.
    """
    url = f"{AFFLUENCES_BASE_URL}/resources/{site_id}/available"
    params = {"date": date_str, "start_hour": start_hour, "type": AFFLUENCES_TYPE}

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise AffluencesError(f"Erreur réseau en appelant Affluences : {exc}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise AffluencesError(f"Réponse Affluences illisible (pas du JSON) : {exc}") from exc


def libres_dans_la_plage(rooms, resource_id, heure_debut, heure_fin):
    """
    rooms : la liste brute renvoyée par fetch_availability().
    resource_id : l'id numérique de la salle (ex: 758).
    heure_debut, heure_fin : des objets datetime.time.

    Renvoie la liste des heures ("HH:MM") de cette salle qui sont à l'état
    "available" et comprises dans [heure_debut, heure_fin).
    """
    room = next((r for r in rooms if r.get("resource_id") == resource_id), None)
    if room is None:
        return []

    debut_str = heure_debut.strftime("%H:%M")
    fin_str = heure_fin.strftime("%H:%M")

    return [
        slot["hour"]
        for slot in room.get("hours", [])
        if debut_str <= slot.get("hour", "") < fin_str and slot.get("state") == "available"
    ]