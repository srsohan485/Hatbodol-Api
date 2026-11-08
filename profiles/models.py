from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    full_name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to="profiles/", blank=True, null=True)
    area = models.CharField(max_length=150)  # যেমন: "মোহাম্মদপুর, ঢাকা"
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    phone = models.CharField(max_length=11, blank=True, default="")
    is_phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} ({self.user.email})"


class UserSettings(models.Model):
    LANGUAGE_CHOICES = (("bn", "বাংলা"), ("en", "English"))

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="app_settings"
    )
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="bn")
    notifications_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Settings of {self.user.email}"


class PhoneChangeRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    new_phone = models.CharField(max_length=11)
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
