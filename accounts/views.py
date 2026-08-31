from django.urls import reverse_lazy
from django.views import generic
from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView
from .forms import CustomUserCreationForm
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import (
    ChangePasswordSerializer,
    EmailTokenObtainPairSerializer,
    LogoutSerializer,
    RegisterSerializer,
    UserSerializer,
)
# Create your views here.

class SignupPageView(generic.CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("login")
    #template_name = "registration/signup.html"


class EmailTokenObtainPairView(TokenObtainPairView):
    """POST {email, password} -> {access, refresh}"""
    serializer_class = EmailTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    """POST {email, password} -> crée le compte (public, pas besoin d'être connecté)."""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/me/ -> profil de l'utilisateur connecté (identifié via son JWT)."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class LogoutView(APIView):
    """POST /api/logout/ {"refresh": "..."} -> révoque ce refresh token."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=205)  # 205 Reset Content : "ok, vide ton state côté client"


class ChangePasswordView(APIView):
    """POST /api/change-password/ {"old_password": "...", "new_password": "..."}"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Mot de passe modifié avec succès."})