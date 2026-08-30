from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Carel, Creneau, Reservation


class CarelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carel
        fields = ["id", "numero", "etage", "nb_places"]


class CreneauSerializer(serializers.ModelSerializer):
    class Meta:
        model = Creneau
        fields = ["id", "date", "duration"]


class ReservationSerializer(serializers.ModelSerializer):
    """Lecture : affiche le carel et le créneau en détail (pas juste leurs IDs)."""

    carel = CarelSerializer(read_only=True)
    creneau = CreneauSerializer(read_only=True)

    class Meta:
        model = Reservation
        fields = ["id", "carel", "creneau"]


class ReservationCreateSerializer(serializers.Serializer):
    """
    POST /api/reservation/reservations/
    {"carel": "<uuid>", "date": "2026-09-01T10:00:00Z", "duration": 2}

    Récupère ou crée le Creneau (date, duration) correspondant, vérifie la
    capacité du carel (nb_places) et le quota d'heures de l'étudiant, puis
    crée la réservation et décrémente son quota `hours`.
    """

    carel = serializers.PrimaryKeyRelatedField(queryset=Carel.objects.all())
    date = serializers.DateTimeField()
    duration = serializers.IntegerField(min_value=1, max_value=12)

    def validate(self, attrs):
        # Creneau.save() appelle déjà self.full_clean() (règles métier : heure
        # lisse, plage 08h-19h) -> une DjangoValidationError levée ici est
        # automatiquement traduite en erreur DRF propre.
        try:
            creneau, _ = Creneau.objects.get_or_create(
                date=attrs["date"], duration=attrs["duration"]
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"date": exc.messages})

        attrs["creneau"] = creneau
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        etudiant = request.user
        carel = validated_data["carel"]
        creneau = validated_data["creneau"]
        duration = validated_data["duration"]

        if Reservation.objects.filter(etudiant=etudiant, carel=carel, creneau=creneau).exists():
            raise serializers.ValidationError("Vous avez déjà réservé ce carel sur ce créneau.")

        places_prises = Reservation.objects.filter(carel=carel, creneau=creneau).count()
        if places_prises >= carel.nb_places:
            raise serializers.ValidationError("Ce carel est complet sur ce créneau.")

        if etudiant.hours < duration:
            raise serializers.ValidationError(
                f"Quota d'heures insuffisant (il vous reste {etudiant.hours}h, "
                f"ce créneau en demande {duration}h)."
            )

        with transaction.atomic():
            reservation = Reservation.objects.create(
                etudiant=etudiant, carel=carel, creneau=creneau
            )
            etudiant.hours -= duration
            etudiant.save(update_fields=["hours"])

        return reservation