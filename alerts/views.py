from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .affluences_client import AffluencesError, fetch_availability
from .constants import AFFLUENCES_SITE_ID
from .models import WatchedSlot
from .serializers import WatchedSlotSerializer

# Create your views here.


class RoomsAvailabilityAPIView(APIView):
    """
    GET /api/alerts/rooms/?date=2026-09-01
    -> proxy serveur vers l'API Affluences : renvoie la dispo de toutes les
    salles du site pour cette date. Le navigateur n'appelle JAMAIS
    directement reservation.affluences.com, tout passe par ce endpoint
    (plus simple à faire évoluer, et on garde le contrôle du rythme des
    appels externes).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"detail": "Le paramètre 'date' est requis (format YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            rooms = fetch_availability(AFFLUENCES_SITE_ID, date_str)
        except AffluencesError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(rooms)


class WatchedSlotListCreateAPIView(generics.ListCreateAPIView):
    """
    GET  /api/alerts/watches/ -> mes surveillances (actives + déclenchées)
    POST /api/alerts/watches/ -> en créer une nouvelle
    """

    serializer_class = WatchedSlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WatchedSlot.objects.filter(utilisateur=self.request.user)


class WatchedSlotCancelAPIView(generics.DestroyAPIView):
    """DELETE /api/alerts/watches/<uuid>/ -> arrête cette surveillance."""

    serializer_class = WatchedSlotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WatchedSlot.objects.filter(utilisateur=self.request.user)