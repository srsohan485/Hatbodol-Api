from django.urls import path
from . import views
from . import settings_views as sv

urlpatterns = [
    # প্রোফাইল
    path("create/", views.CreateProfileView.as_view()),
    path("me/", views.MyProfileView.as_view()),
    path("me/photo/", views.ProfilePhotoView.as_view()),

    # সেটিংস
    path("settings/", sv.SettingsView.as_view()),
    path("settings/phone/request/", sv.PhoneChangeRequestView.as_view()),
    path("settings/phone/confirm/", sv.PhoneChangeConfirmView.as_view()),
    path("settings/info/", sv.AppInfoView.as_view()),
    path("settings/logout/", sv.LogoutView.as_view()),
    path("settings/delete-account/", sv.DeleteAccountView.as_view()),

    # সবার শেষে রাখো (নইলে "settings/" কে user_id ভেবে গুলিয়ে ফেলতে পারে)
    path("<int:user_id>/", views.PublicProfileView.as_view()),
]