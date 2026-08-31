from datetime import date as date_cls

from rest_framework import serializers

from .constants import AFFLUENCES_SITE_ID, AFFLUENCES_SITE_NOM
from .models import WatchedSlot


class WatchedSlotSerializer(serializers.ModelSerializer):
    """CRUD sur les surveillances de l'utilisateur connecté."""

    class Meta:
        model = WatchedSlot
        fields = [
            "id",
            "site_nom",
            "resource_id",
            "resource_nom",
            "date_cible",
            "heure_debut",
            "heure_fin",
            "est_actif",
            "notifie_le",
            "cree_le",
        ]
        read_only_fields = ["id", "site_nom", "est_actif", "notifie_le", "cree_le"]

    def validate(self, attrs):
        if attrs["heure_fin"] <= attrs["heure_debut"]:
            raise serializers.ValidationError("heure_fin doit être après heure_debut.")
        if attrs["date_cible"] < date_cls.today():
            raise serializers.ValidationError("Impossible de surveiller une date déjà passée.")
        return attrs

    def create(self, validated_data):
        validated_data["utilisateur"] = self.context["request"].user
        # Site figé pour l'instant (voir constants.py) : on ne laisse pas le
        # client choisir site_id/site_nom, pour ne surveiller que ce qu'on a
        # réellement testé.
        validated_data["site_id"] = AFFLUENCES_SITE_ID
        validated_data["site_nom"] = AFFLUENCES_SITE_NOM
        return super().create(validated_data)