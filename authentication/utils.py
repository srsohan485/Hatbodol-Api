from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from .models import OTP


def create_and_send_otp(user, purpose):
    # শুধু মেয়াদোত্তীর্ণ পুরনো OTP মুছে ফেলি, valid গুলো থাকে
    expiry = timezone.now() - timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    OTP.objects.filter(user=user, purpose=purpose, created_at__lt=expiry).delete()

    otp = OTP.objects.create(user=user, code=OTP.generate_code(), purpose=purpose)
    subject = "Verify your email" if purpose == "verify" else "Reset your password"
    send_mail(
        subject,
        f"Your Hatbodol OTP is {otp.code}. It expires in {settings.OTP_EXPIRY_MINUTES} minutes.",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    return otp


def check_otp(user, code, purpose, consume=True):
    code = str(code).strip()
    expiry = timezone.now() - timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    otp = OTP.objects.filter(
        user=user, purpose=purpose, code=code, is_used=False, created_at__gte=expiry
    ).first()
    if not otp:
        return False
    if consume:
        # সফল হলে ওই user এর ওই purpose এর সব OTP বাতিল
        OTP.objects.filter(user=user, purpose=purpose).update(is_used=True)
    return True


def get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}