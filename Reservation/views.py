from django.shortcuts import get_object_or_404
from django.views.generic import ListView
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Carel, Creneau, Reservation
from .serializers import (
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