import uuid

from django.conf import settings
from django.db import models


class WatchedSlot(models.Model):
    """
    Une surveillance active : "préviens-moi quand telle salle du site
    Affluences a un créneau libre dans telle plage horaire, tel jour."

    Volontairement indépendant des modèles Carel/Creneau/Reservation :
    ceci ne réserve rien sur NOTRE système, ça surveille un site externe.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watched_slots"
    )

    # Identifie la ressource côté Affluences (voir alerts/constants.py).
    site_id = models.CharField(max_length=64)
    site_nom = models.CharField(max_length=200)
    resource_id = models.IntegerField()
    resource_nom = models.CharField(max_length=200)

    date_cible = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()

    est_actif = models.BooleanField(default=True)
    notifie_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.resource_nom} le {self.date_cible} {self.heure_debut}-{self.heure_fin}"