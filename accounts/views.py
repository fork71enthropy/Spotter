from django.urls import reverse_lazy
from django.views import generic
from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView
from .forms import CustomUserCreationForm
from .serializers import EmailTokenObtainPairSerializer, RegisterSerializer, UserSerializer
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