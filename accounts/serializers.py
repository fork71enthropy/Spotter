from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Profil de l'utilisateur connecté, exposé sur /api/me/."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "hours", "date_joined"]
        # username/hours/date_joined : gérés par le système, pas par l'utilisateur
        # lui-même (hours est un quota, username est généré à l'inscription).
        read_only_fields = ["id", "username", "hours", "date_joined"]


class RegisterSerializer(serializers.ModelSerializer):
    """
    Création de compte via l'API : seulement email + password.
    On suit la même logique que le site actuel (ACCOUNT_USERNAME_REQUIRED = False
    côté allauth) : le username technique est généré automatiquement, invisible
    pour l'utilisateur.
    """

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "password"]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet email.")
        return value

    def validate_password(self, value):
        # Réutilise les mêmes règles que celles définies dans
        # AUTH_PASSWORD_VALIDATORS (settings.py) : longueur mini, pas trop
        # commun, pas uniquement numérique, pas trop proche du username/email.
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    @staticmethod
    def _generate_username(email):
        base = email.split("@")[0][:140] or "user"
        username = base
        suffix = 0
        while User.objects.filter(username=username).exists():
            suffix += 1
            username = f"{base}{suffix}"
        return username

    def create(self, validated_data):
        username = self._generate_username(validated_data["email"])
        return User.objects.create_user(
            username=username,
            email=validated_data["email"],
            password=validated_data["password"],
        )


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Login JWT par (email, password) plutôt que (username, password).

    TokenObtainPairSerializer part du principe que USERNAME_FIELD = "username"
    (c'est le cas ici au niveau Django), donc on ne peut pas juste changer
    `username_field` : authenticate() irait chercher un kwarg "username" qui
    n'existerait plus. On remplace donc entièrement le champ et la validation.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # On retire le champ "username" injecté par le parent et on le
        # remplace par "email", qui est ce que le frontend React enverra.
        self.fields.pop("username", None)
        self.fields["email"] = serializers.EmailField()

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise AuthenticationFailed(
                "Aucun compte actif trouvé avec ces identifiants.",
                "no_active_account",
            )

        # On authentifie avec le username réel de Django (get_username()),
        # même si l'utilisateur, lui, ne l'a jamais tapé.
        authenticated_user = authenticate(
            request=self.context.get("request"),
            username=user.get_username(),
            password=password,
        )

        if authenticated_user is None or not authenticated_user.is_active:
            raise AuthenticationFailed(
                "Aucun compte actif trouvé avec ces identifiants.",
                "no_active_account",
            )

        refresh = self.get_token(authenticated_user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }