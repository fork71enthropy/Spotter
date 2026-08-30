from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


# Create your models here.
class CustomUser(AbstractUser):
    # On force l'unicité en base : allauth l'imposait déjà côté formulaire
    # (ACCOUNT_UNIQUE_MAIL = True) mais pas au niveau de la table SQL.
    # C'est cette contrainte qui garantit que User.objects.get(email=...)
    # ne peut jamais lever un MultipleObjectsReturned lors du login JWT.
    email = models.EmailField(unique=True)

    hours = models.IntegerField(
        default=20,
        validators=[MaxValueValidator(20), MinValueValidator(0)]
    )