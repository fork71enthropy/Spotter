from django.urls import path

from .views import (
    CarelListAPIView,
    CreneauListAPIView,
    ReservationCancelAPIView,
    ReservationListCreateAPIView,
)

urlpatterns = [
    path("carels/", CarelListAPIView.as_view(), name="api_carel_list"),
    path("creneaux/", CreneauListAPIView.as_view(), name="api_creneau_list"),
    path("reservations/", ReservationListCreateAPIView.as_view(), name="api_reservation_list_create"),
    path("reservations/<uuid:pk>/", ReservationCancelAPIView.as_view(), name="api_reservation_cancel"),
]









































