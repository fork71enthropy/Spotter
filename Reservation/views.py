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
    -> tous les carels, chacun avec un booléen "disponible" pour CE créneau
    précis (chevauchement de plage horaire, pas juste égalité exacte).
    """
    serializer_class = CarelAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # une grille de dispo n'a pas besoin d'être paginée

    def get_queryset(self):
        return Carel.objects.all().order_by("etage", "numero")

    def _resolve_window(self):
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

        return parsed_date, parsed_date + timedelta(hours=duration)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        start, end = self._resolve_window()

        todays_reservations = (
            Reservation.objects.filter(creneau__date__date=start.date())
            .select_related("creneau")
            .values("carel_id", "creneau__date", "creneau__duration")
        )
        intervals_by_carel = {}
        for row in todays_reservations:
            s = row["creneau__date"]
            e = s + timedelta(hours=row["creneau__duration"])
            intervals_by_carel.setdefault(row["carel_id"], []).append((s, e))

        context.update({"start": start, "end": end, "intervals_by_carel": intervals_by_carel})
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

        # On récupère TOUTES les réservations du jour (toutes durées
        # confondues), et on les regroupe par carel sous forme d'intervalles
        # [début, fin). C'est ce qui permet de détecter un chevauchement
        # entre une réservation de 10h00/2h et une candidate de 10h30/1h,
        # même si ce ne sont pas le même (date, duration) exact.
        today = dj_timezone.localdate()
        todays_reservations = (
            Reservation.objects.filter(creneau__date__date=today)
            .select_related("creneau")
            .values("carel_id", "creneau__date", "creneau__duration")
        )
        intervals_by_carel = {}
        for row in todays_reservations:
            start = row["creneau__date"]
            end = start + timedelta(hours=row["creneau__duration"])
            intervals_by_carel.setdefault(row["carel_id"], []).append((start, end))

        context.update({
            "candidate_times": candidate_times,
            "duration": duration,
            "intervals_by_carel": intervals_by_carel,
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