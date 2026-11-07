from django.urls import path
from . import views

urlpatterns = [
    path("create/", views.CreateProfileView.as_view()),
    path("me/", views.MyProfileView.as_view()),
    path("me/photo/", views.ProfilePhotoView.as_view()),
    path("<int:user_id>/", views.PublicProfileView.as_view()),
]