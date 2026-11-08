from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PhoneChangeRequest, Profile, UserSettings
from .utils import generate_code, normalize_phone, send_phone_otp


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = ["language", "notifications_enabled"]


def settings_payload(user):
    s, _ = UserSettings.objects.get_or_create(user=user)
    profile = getattr(user, "profile", None)
    return {
        "language": s.language,
        "notifications_enabled": s.notifications_enabled,
        "email": user.email,
        "area": profile.area if profile else "",
        "phone": profile.phone if profile else "",
        "is_phone_verified": profile.is_phone_verified if profile else False,
    }


class SettingsView(APIView):
    """GET: Settings screen এর সব তথ্য। PATCH: ভাষা / নোটিফিকেশন বদল"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(settings_payload(request.user))

    def patch(self, request):
        obj, _ = UserSettings.objects.get_or_create(user=request.user)
        s = UserSettingsSerializer(obj, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(settings_payload(request.user))


class PhoneChangeRequestView(APIView):
    """ধাপ ১: নতুন নম্বর দিন, OTP যাবে"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "profile", None)
        if not profile:
            return Response({"error": "আগে প্রোফাইল তৈরি করুন।"}, status=400)

        phone = normalize_phone(request.data.get("phone"))
        if not phone:
            return Response({"phone": ["সঠিক বাংলাদেশি ফোন নম্বর দিন (যেমন 01712345678)।"]}, status=400)
        if phone == profile.phone:
            return Response({"phone": ["এটাই আপনার বর্তমান নম্বর।"]}, status=400)
        if Profile.objects.filter(phone=phone).exclude(pk=profile.pk).exists():
            return Response({"phone": ["এই ফোন নম্বর আগে থেকেই ব্যবহার হচ্ছে।"]}, status=400)

        # ৬০ সেকেন্ডের মধ্যে বারবার OTP চাওয়া ঠেকানো
        recent = PhoneChangeRequest.objects.filter(
            user=request.user, created_at__gte=timezone.now() - timedelta(seconds=60)
        ).exists()
        if recent:
            return Response({"error": "১ মিনিট পর আবার চেষ্টা করুন।"}, status=429)

        PhoneChangeRequest.objects.filter(user=request.user).delete()
        req = PhoneChangeRequest.objects.create(
            user=request.user, new_phone=phone, code=generate_code()
        )
        send_phone_otp(request.user, phone, req.code)
        return Response({"message": "OTP পাঠানো হয়েছে।", "phone": phone})


class PhoneChangeConfirmView(APIView):
    """ধাপ ২: OTP দিয়ে নম্বর বদল নিশ্চিত"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "profile", None)
        if not profile:
            return Response({"error": "আগে প্রোফাইল তৈরি করুন।"}, status=400)

        phone = normalize_phone(request.data.get("phone"))
        otp = str(request.data.get("otp", "")).strip()
        req = PhoneChangeRequest.objects.filter(
            user=request.user, new_phone=phone, code=otp, is_used=False
        ).first()
        if not phone or not req or req.is_expired():
            return Response({"error": "OTP ভুল বা expired।"}, status=400)

        if Profile.objects.filter(phone=phone).exclude(pk=profile.pk).exists():
            return Response({"error": "এই নম্বর এখন অন্য কেউ ব্যবহার করছে।"}, status=400)

        profile.phone = phone
        profile.is_phone_verified = False  # SMS দিয়ে যাচাই না হওয়া পর্যন্ত false
        profile.save()
        PhoneChangeRequest.objects.filter(user=request.user).delete()
        return Response({"message": "ফোন নম্বর পরিবর্তন হয়েছে।", **settings_payload(request.user)})


class LogoutView(APIView):
    """লগআউট: refresh token বাতিল"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"refresh": ["refresh token পাঠান।"]}, status=400)
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            return Response({"error": "Token সঠিক নয় বা আগেই বাতিল।"}, status=400)
        return Response({"message": "লগআউট সফল।"})


class DeleteAccountView(APIView):
    """অ্যাকাউন্ট মুছুন (স্থায়ী)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.has_usable_password():
            if not user.check_password(request.data.get("password", "")):
                return Response({"password": ["Password ভুল।"]}, status=400)
        else:  # Google দিয়ে খোলা account, password নেই
            if request.data.get("confirm") != "DELETE":
                return Response({"confirm": ['নিশ্চিত করতে "DELETE" লিখুন।']}, status=400)

        profile = getattr(user, "profile", None)
        if profile and profile.photo:
            profile.photo.delete(save=False)

        user.delete()
        return Response({"message": "অ্যাকাউন্ট মুছে ফেলা হয়েছে।"})


class AppInfoView(APIView):
    """গোপনীয়তা নীতি, সাহায্য ও যোগাযোগ"""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "privacy_policy_url": settings.PRIVACY_POLICY_URL,
            "support_email": settings.SUPPORT_EMAIL,
            "support_phone": settings.SUPPORT_PHONE,
            "tagline": "পুরনোয় - পুরনো জিনিস, নতুন শুরু",
        })