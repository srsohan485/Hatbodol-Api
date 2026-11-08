import random
import re
from django.conf import settings
from django.core.mail import send_mail


def normalize_phone(value):
    """বাংলাদেশি নম্বর 01XXXXXXXXX ফরম্যাটে আনে। ভুল হলে None দেয়।"""
    value = (value or "").strip().replace(" ", "").replace("-", "")
    if value.startswith("+880"):
        value = "0" + value[4:]
    elif value.startswith("880"):
        value = "0" + value[3:]
    return value if re.fullmatch(r"01[3-9]\d{8}", value) else None


def generate_code():
    return f"{random.randint(0, 999999):06d}"


def send_phone_otp(user, phone, code):
    send_mail(
        "Phone number change",
        f"Your Hatbodol OTP to change phone number to {phone} is {code}. "
        f"It expires in {settings.OTP_EXPIRY_MINUTES} minutes.",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )