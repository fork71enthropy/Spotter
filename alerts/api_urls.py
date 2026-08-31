from django.urls import path

from .views import RoomsAvailabilityAPIView, WatchedSlotCancelAPIView, WatchedSlotListCreateAPIView

urlpatterns = [
    path("rooms/", RoomsAvailabilityAPIView.as_view(), name="api_alerts_rooms"),
    path("watches/", WatchedSlotListCreateAPIView.as_view(), name="api_watch_list_create"),
    path("watches/<uuid:pk>/", WatchedSlotCancelAPIView.as_view(), name="api_watch_cancel"),
]