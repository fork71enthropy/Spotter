# books/views.py

from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin
) 
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from rest_framework import generics, permissions
from .models import Book, Review
from .permissions import HasSpecialStatus
from .serializers import BookDetailSerializer, BookListSerializer, ReviewCreateSerializer

class BookListView(LoginRequiredMixin,ListView):
    model = Book
    context_object_name = "book_list"
    template_name = "books/book_list.html"
    login_url = "account_login"


class BookDetailView(LoginRequiredMixin,PermissionRequiredMixin,DetailView):
    model = Book 
    context_object_name = "book"
    template_name = "books/book_detail.html"
    login_url = "account_login"
    permission_required = "books.special_status"
    queryset = Book.objects.all().prefetch_related('reviews__author',)

# The user can see the list of books, but not see the details ! 

class SearchResultsListView(ListView):
    model = Book
    context_object_name = "book_list"
    template_name = "books/search_results.html"

    def get_queryset(self):
        query = self.request.GET.get("q")
        return Book.objects.filter(
            Q(title__icontains=query) | Q(title__icontains=query)
        )


# --- API pour le frontend React ---------------------------------------------

class BookListAPIView(generics.ListAPIView):
    """
    GET /api/books/            -> tous les livres
    GET /api/books/?q=monier   -> filtre par titre OU auteur (icontains)
    """
    serializer_class = BookListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Book.objects.all().order_by("title")
        query = self.request.query_params.get("q")
        if query:
            # Bug corrigé par rapport à SearchResultsListView : on cherche
            # bien sur title ET author, pas deux fois sur title.
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(author__icontains=query)
            )
        return queryset


class BookDetailAPIView(generics.RetrieveAPIView):
    """GET /api/books/<uuid>/ -> détail + reviews (nécessite special_status)."""
    serializer_class = BookDetailSerializer
    permission_classes = [permissions.IsAuthenticated, HasSpecialStatus]
    queryset = Book.objects.all().prefetch_related("reviews__author")


class ReviewCreateAPIView(generics.CreateAPIView):
    """POST /api/books/<uuid>/reviews/  {"review": "..."} -> ajoute une review."""
    serializer_class = ReviewCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        book = get_object_or_404(Book, pk=self.kwargs["book_pk"])
        serializer.save(author=self.request.user, book=book)