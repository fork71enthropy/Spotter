from django.urls import path

from .views import BookDetailAPIView, BookListAPIView, ReviewCreateAPIView

urlpatterns = [
    path("", BookListAPIView.as_view(), name="api_book_list"),
    path("<uuid:pk>/", BookDetailAPIView.as_view(), name="api_book_detail"),
    path("<uuid:book_pk>/reviews/", ReviewCreateAPIView.as_view(), name="api_review_create"),
]