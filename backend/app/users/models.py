from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import UserManager


class User(AbstractUser):
    ROLE_CHOICES = (
        ("user", "User"),
        ("moderator", "Moderator"),
        ("admin", "Admin"),
    )

    username = None
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    avatar = models.URLField(blank=True, null=True)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="user")
    google_id = models.CharField(max_length=255, blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class GoogleOAuthConfig(models.Model):
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    redirect_uri = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Google OAuth настройка"
        verbose_name_plural = "Google OAuth настройки"

    def __str__(self):
        return f"Google OAuth ({'active' if self.is_active else 'inactive'})"
