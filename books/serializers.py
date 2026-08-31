from rest_framework import serializers

from .models import Book, Review


class ReviewSerializer(serializers.ModelSerializer):
    """Review affichée dans le détail d'un livre (lecture seule)."""

    author = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "review", "author"]


class ReviewCreateSerializer(serializers.ModelSerializer):
    """POST /api/books/<uuid>/reviews/ -> author et book injectés côté vue."""

    class Meta:
        model = Review
        fields = ["id", "review"]


class BookListSerializer(serializers.ModelSerializer):
    """Version allégée pour /api/books/ (pas de reviews, pour rester léger)."""

    class Meta:
        model = Book
        fields = ["id", "title", "author", "price", "cover"]


class BookDetailSerializer(serializers.ModelSerializer):
    """Version complète pour /api/books/<uuid>/, reviews imbriquées."""

    reviews = ReviewSerializer(many=True, read_only=True)

    class Meta:
        model = Book
        fields = ["id", "title", "author", "price", "cover", "reviews"]