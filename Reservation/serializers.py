from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Carel, Creneau, Reservation


class CarelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carel
        fields = ["id", "numero", "etage", "nb_places"]


class CarelAvailabilitySerializer(serializers.ModelSerializer):
    """
    Carel + un booléen "disponible" pour UN créneau précis (passé via le
    contexte du serializer). Une seule réservation qui chevauche ce créneau
    suffit à le rendre indisponible, quel que soit nb_places (voir
    CarelDailyAvailabilitySerializer pour l'explication complète).
    """

    disponible = serializers.SerializerMethodField()

    class Meta:
        model = Carel
        fields = ["id", "numero", "etage", "nb_places", "disponible"]

    def get_disponible(self, carel):
        start = self.context["start"]
        end = self.context["end"]
        intervals = self.context["intervals_by_carel"].get(carel.id, [])
        return not any(s < end and e > start for (s, e) in intervals)


class CarelDailyAvailabilitySerializer(serializers.ModelSerializer):
    """
    Carel + la liste des heures de début encore libres AUJOURD'HUI
    (créneaux d'une durée donnée, 1h par défaut), sous forme de chaînes
    "HH:MM" -> facile à afficher tel quel côté React.
    """

    creneaux_libres = serializers.SerializerMethodField()

    class Meta:
        model = Carel
        fields = ["id", "numero", "etage", "nb_places", "creneaux_libres"]

    def get_creneaux_libres(self, carel):
        candidate_times = self.context["candidate_times"]
        duration = self.context["duration"]
        intervals = self.context["intervals_by_carel"].get(carel.id, [])

        libres = []
        for start in candidate_times:
            end = start + timedelta(hours=duration)
            # Une SEULE réservation qui chevauche suffit à bloquer le créneau,
            # quel que soit nb_places : une réservation couvre tout le carel
            # (utilisé en groupe), ce n'est pas un compteur de places libres.
            has_overlap = any(s < end and e > start for (s, e) in intervals)
            if not has_overlap:
                libres.append({"heure": start.strftime("%H:%M"), "date": start.isoformat()})
        return libres


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


def _overlaps_any(reservations, start, end):
    """True si au moins une réservation de la liste chevauche [start, end)."""
    return any(
        r.creneau.date < end and (r.creneau.date + timedelta(hours=r.creneau.duration)) > start
        for r in reservations
    )


class ReservationCreateSerializer(serializers.Serializer):
    """
    POST /api/reservation/reservations/
    {"carel": "<uuid>", "date": "2026-09-01T10:00:00Z", "duration": 2}

    Récupère ou crée le Creneau (date, duration) correspondant, vérifie :
    - que l'étudiant n'a pas déjà une autre réservation qui chevauche (il ne
      peut pas être à deux endroits en même temps),
    - que ce carel n'est pas déjà occupé par quelqu'un d'autre sur ce créneau,
    - que le quota d'heures suffit,
    puis crée la réservation et décrémente son quota `hours`.
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

        start = creneau.date
        end = start + timedelta(hours=duration)

        # 1) L'ÉTUDIANT ne peut pas être à deux endroits en même temps :
        #    aucun chevauchement avec une de SES PROPRES réservations,
        #    peu importe le carel concerné.
        mes_reservations_du_jour = Reservation.objects.filter(
            etudiant=etudiant, creneau__date__date=start.date()
        ).select_related("creneau")
        if _overlaps_any(mes_reservations_du_jour, start, end):
            raise serializers.ValidationError(
                "Vous avez déjà une réservation qui chevauche ce créneau "
                "(impossible d'être à deux endroits en même temps)."
            )

        # 2) Le CAREL ne doit pas déjà être occupé par quelqu'un d'autre sur
        #    ce créneau (une seule réservation par carel/heure, quel que
        #    soit nb_places -> voir CarelDailyAvailabilitySerializer).
        meme_jour_carel = Reservation.objects.filter(
            carel=carel, creneau__date__date=start.date()
        ).select_related("creneau")
        if _overlaps_any(meme_jour_carel, start, end):
            raise serializers.ValidationError("Ce carel est déjà réservé sur ce créneau.")

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