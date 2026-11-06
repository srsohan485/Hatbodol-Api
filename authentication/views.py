from django.conf import settings
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializers import *
from .utils import create_and_send_otp, check_otp, get_tokens


def get_user_or_none(email):
    return User.objects.filter(email=email.lower()).first()


class SignUpView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = SignUpSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        create_and_send_otp(user, "verify")
        return Response({"message": "OTP email e pathano hoyeche।", "email": user.email},
                        status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    """Sign up er por OTP diye email verify -> 'Email Verified!' screen"""
    permission_classes = [AllowAny]

    def post(self, request):
        s = VerifyOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = get_user_or_none(s.validated_data["email"])
        if not user or not check_otp(user, s.validated_data["otp"], "verify"):
            return Response({"error": "OTP ভুল বা expired।"}, status=400)
        user.is_email_verified = True
        user.save()
        return Response({"message": "Email Verified!", "email": user.email,
                         "user": UserSerializer(user).data, **get_tokens(user)})


class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = EmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = get_user_or_none(s.validated_data["email"])
        if user:
            purpose = "reset" if user.is_email_verified else "verify"
            create_and_send_otp(user, purpose)
        return Response({"message": "OTP pathano hoyeche (jodi account thake)।"})


class SignInView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = SignInSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.validated_data["user"]
        return Response({"user": UserSerializer(user).data, **get_tokens(user)})


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = EmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = get_user_or_none(s.validated_data["email"])
        if user:
            create_and_send_otp(user, "reset")
        # security: account ache kina ta bole dei na
        return Response({"message": "Email thakle OTP pathano hoyeche।"})


class VerifyResetOTPView(APIView):
    """Enter OTP screen: shudhu check kore, consume kore na"""
    permission_classes = [AllowAny]

    def post(self, request):
        s = VerifyOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = get_user_or_none(s.validated_data["email"])
        if not user or not check_otp(user, s.validated_data["otp"], "reset", consume=False):
            return Response({"error": "OTP ভুল বা expired।"}, status=400)
        return Response({"message": "OTP valid।"})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = ResetPasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        user = get_user_or_none(d["email"])
        if not user or not check_otp(user, d["otp"], "reset"):
            return Response({"error": "OTP ভুল বা expired।"}, status=400)
        user.set_password(d["password"])
        user.save()
        return Response({"message": "Password reset hoyeche।"})


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        s = SocialLoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            info = google_id_token.verify_oauth2_token(
                s.validated_data["id_token"], google_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
        except ValueError:
            return Response({"error": "Invalid Google token।"}, status=400)

        email = info["email"].lower()
        user = User.objects.filter(email=email).first()
        if not user:
            base = email.split("@")[0]
            username, i = base, 1
            while User.objects.filter(username=username).exists():
                username, i = f"{base}{i}", i + 1
            user = User.objects.create_user(username=username, email=email,
                                            is_email_verified=True, auth_provider="google")
            user.set_unusable_password()
            user.save()
        return Response({"user": UserSerializer(user).data, **get_tokens(user)})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)