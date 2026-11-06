from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path("signup/", views.SignUpView.as_view()),
    path("verify-email/", views.VerifyEmailView.as_view()),
    path("resend-otp/", views.ResendOTPView.as_view()),
    path("signin/", views.SignInView.as_view()),
    path("forgot-password/", views.ForgotPasswordView.as_view()),
    path("verify-reset-otp/", views.VerifyResetOTPView.as_view()),
    path("reset-password/", views.ResetPasswordView.as_view()),
    path("google/", views.GoogleLoginView.as_view()),
    path("token/refresh/", TokenRefreshView.as_view()),
    path("me/", views.MeView.as_view()),
]