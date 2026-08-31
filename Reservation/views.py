from datetime import datetime, timedelta

from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone as dj_timezone
from django.utils.dateparse import parse_datetime
from django.views.generic import ListView
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Carel, Creneau, DERNIER_CRENEAU, PREMIER_CRENEAU, Reservation
from .serializers import (
    CarelAvailabilitySerializer,
    CarelDailyAvailabilitySerializer,
    CarelSerializer,
    CreneauSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
)

# Create your views here.
class CarelListView(ListView):
    model = Carel
    context_object_name = "carels_dispos"
    template_name = "reservations/carels.html"


# --- API pour le frontend React ---------------------------------------------

class CarelListAPIView(generics.ListAPIView):
    """GET /api/reservation/carels/ -> tous les carels."""
    queryset = Carel.objects.all().order_by("etage", "numero")
    serializer_class = CarelSerializer
    permission_classes = [permissions.IsAuthenticated]


class CarelAvailabilityAPIView(generics.ListAPIView):
    """
    GET /api/reservation/carels/disponibilite/?date=2026-09-01T10:00:00Z&duration=2
    -> tous les carels, chacun avec son nombre de places encore libres pour
    CE créneau précis. C'est cet endpoint que le front utilisera pour
    n'afficher que les carels réellement disponibles (comme le vrai site de BU).
    """
    serializer_class = CarelAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # une grille de dispo n'a pas besoin d'être paginée

    def get_queryset(self):
        return Carel.objects.all().order_by("etage", "numero")

    def _resolve_creneau(self):
        date_str = self.request.query_params.get("date")
        duration_str = self.request.query_params.get("duration")
        if not date_str or not duration_str:
            raise ValidationError({"detail": "Les paramètres 'date' et 'duration' sont requis."})

        parsed_date = parse_datetime(date_str)
        if parsed_date is None:
            raise ValidationError({"date": "Format invalide (attendu : ISO 8601, ex. 2026-09-01T10:00:00Z)."})

        try:
            duration = int(duration_str)
        except ValueError:
            raise ValidationError({"duration": "Doit être un entier."})

        # On ne CRÉE jamais de Creneau ici (une requête GET ne doit jamais
        # avoir d'effet de bord) : si personne n'a encore réservé sur ce
        # créneau, il n'existe simplement pas encore en base -> tout est libre.
        return Creneau.objects.filter(date=parsed_date, duration=duration).first()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["creneau"] = self._resolve_creneau()
        return context


class CarelDailyAvailabilityAPIView(generics.ListAPIView):
    """
    GET /api/reservation/carels/disponibilite-du-jour/
    GET /api/reservation/carels/disponibilite-du-jour/?duration=2

    Vue par défaut (aucun paramètre requis) : pour chaque carel, la liste
    des heures de début encore libres AUJOURD'HUI (créneaux de 30 min entre
    08h00 et 19h00), pour la durée demandée (1h si non précisée).
    """
    serializer_class = CarelDailyAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    DEFAULT_DURATION = 1

    def get_queryset(self):
        return Carel.objects.all().order_by("etage", "numero")

    def _candidate_times(self):
        today = dj_timezone.localdate()
        start = dj_timezone.make_aware(datetime.combine(today, PREMIER_CRENEAU))
        end = dj_timezone.make_aware(datetime.combine(today, DERNIER_CRENEAU))
        times = []
        current = start
        while current <= end:
            times.append(current)
            current += timedelta(minutes=30)
        return times

    def get_serializer_context(self):
        context = super().get_serializer_context()

        duration_str = self.request.query_params.get("duration", str(self.DEFAULT_DURATION))
        try:
            duration = int(duration_str)
        except ValueError:
            raise ValidationError({"duration": "Doit être un entier."})

        candidate_times = self._candidate_times()

        # Une seule requête pour récupérer tous les Creneau du jour existant
        # déjà pour cette durée (au lieu d'une requête par créneau candidat).
        existing = Creneau.objects.filter(date__in=candidate_times, duration=duration)
        existing_by_date = {c.date: c for c in existing}

        # Une seule requête pour compter toutes les réservations concernées,
        # groupées par (carel, creneau).
        counts_qs = (
            Reservation.objects.filter(creneau__in=existing_by_date.values())
            .values("carel_id", "creneau_id")
            .annotate(count=Count("id"))
        )
        reservation_counts = {(row["carel_id"], row["creneau_id"]): row["count"] for row in counts_qs}

        context.update({
            "candidate_times": candidate_times,
            "existing_creneaux": existing_by_date,
            "reservation_counts": reservation_counts,
        })
        return context


class CreneauListAPIView(generics.ListAPIView):
    """GET /api/reservation/creneaux/ -> tous les créneaux déjà ouverts par une réservation."""
    queryset = Creneau.objects.all().order_by("date")
    serializer_class = CreneauSerializer
    permission_classes = [permissions.IsAuthenticated]


class ReservationListCreateAPIView(generics.ListCreateAPIView):
    """
    GET  /api/reservation/reservations/ -> mes réservations (pas celles des autres)
    POST /api/reservation/reservations/ -> en créer une nouvelle
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Reservation.objects.filter(etudiant=self.request.user)
            .select_related("carel", "creneau")
            .order_by("creneau__date")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ReservationCreateSerializer
        return ReservationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        reservation = serializer.save()
        output = ReservationSerializer(reservation)
        return Response(output.data, status=status.HTTP_201_CREATED)


class ReservationCancelAPIView(APIView):
    """DELETE /api/reservation/reservations/<uuid>/ -> annule et rembourse les heures."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        # etudiant=request.user dans le filtre : un étudiant ne peut annuler
        # que SA PROPRE réservation (sinon 404, pas 403, pour ne pas révéler
        # l'existence d'une réservation qui ne lui appartient pas).
        reservation = get_object_or_404(Reservation, pk=pk, etudiant=request.user)
        duration = reservation.creneau.duration
        etudiant = request.user

        reservation.delete()
        etudiant.hours = min(etudiant.hours + duration, 20)
        etudiant.save(update_fields=["hours"])

        return Response(status=status.HTTP_204_NO_CONTENT)